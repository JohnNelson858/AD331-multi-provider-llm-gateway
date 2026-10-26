"""Async text-streaming gateway with Step 3 audit fixes."""

import asyncio
import os
import time
from collections.abc import AsyncGenerator
import anthropic
import openai
import tiktoken
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from .pricing import MODEL_PRICING, calculate_cost
from .schemas import ChunkTelemetry, Provider, StreamChunk


class GatewayProviderError(Exception):
    """Safe public domain error, without an SDK response body."""


class AuthenticationError(GatewayProviderError):
    """Missing, malformed, or rejected credentials."""


class RateLimitExceededError(GatewayProviderError):
    """Provider rate or quota limit."""


class GatewayConnectionError(GatewayProviderError):
    """Connection or timeout failure."""


class IncompleteStreamError(GatewayProviderError):
    """Missing finish marker or authoritative usage."""


class GatewayInputError(GatewayProviderError):
    """Unsupported model or invalid input."""


def _api_key(provider: Provider) -> str:
    name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    key = os.environ.get(name, "").strip()
    if not key or not key.startswith("sk-") or len(key) < 20 or "your_" in key:
        raise AuthenticationError(f"Set a valid {name} in your local environment.")
    return key


def _count_openai_text(text: str, model: str) -> int:
    """Run in a worker thread, including any initial tokenizer download."""
    return len(tiktoken.encoding_for_model(model).encode(text, disallowed_special=()))


class UnifiedLLMGateway:
    """One gateway per application event loop; close at shutdown.

    Injected clients stay caller-owned. Lazily-created clients are pooled and
    gateway-owned. Each request keeps its own counters for concurrent use.
    Only a single user text prompt is supported in this initial version.
    """

    def __init__(self, *, openai_client: AsyncOpenAI | None = None,
                 anthropic_client: AsyncAnthropic | None = None) -> None:
        self._openai = openai_client
        self._anthropic = anthropic_client
        self._own_openai = openai_client is None
        self._own_anthropic = anthropic_client is None
        self._closed = False

    async def __aenter__(self) -> "UnifiedLLMGateway":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        clients = []
        if self._own_openai and self._openai is not None:
            clients.append(self._openai)
        if self._own_anthropic and self._anthropic is not None:
            clients.append(self._anthropic)
        results = await asyncio.gather(*(client.close() for client in clients),
                                       return_exceptions=True)
        if any(isinstance(result, BaseException) for result in results):
            raise GatewayProviderError("One or more provider clients could not close cleanly.")

    async def stream(self, prompt: str, model: str, temperature: float = 0.7,
                     *, max_tokens: int = 512) -> AsyncGenerator[StreamChunk, None]:
        """Yield deltas, then one final event on success.

        TTFT ends at the first non-empty text delta. Failure or cancellation
        does not emit a successful final event. Close abandoned generators
        with contextlib.aclosing(). Throughput uses total request duration.
        """
        if self._closed:
            raise GatewayInputError("The gateway is closed.")
        if model not in MODEL_PRICING:
            raise GatewayInputError("Choose a model from MODEL_PRICING.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise GatewayInputError("The prompt must contain text.")
        if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
            raise GatewayInputError("Temperature must be between zero and one.")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 4096:
            raise GatewayInputError("max_tokens must be an integer from 1 to 4096.")
        provider = MODEL_PRICING[model].provider
        start = time.perf_counter()
        first_text: float | None = None
        local_prompt: int | None = None
        prompt_tokens: int | None = None
        output_tokens: int | None = None
        cache_read = cache_write = 0
        stop_reason: str | None = None
        text = ""
        got_usage = ended = False
        partial_usage = False
        uncached_input: int | None = None

        def snapshot(final: bool) -> ChunkTelemetry:
            elapsed = time.perf_counter() - start
            total = None if prompt_tokens is None or output_tokens is None else prompt_tokens + output_tokens
            source = ("provider" if got_usage else "provider_partial" if partial_usage
                      else "local_estimate" if local_prompt is not None else "unavailable")
            cost = None
            if prompt_tokens is not None and output_tokens is not None:
                cost = calculate_cost(model, prompt_tokens, output_tokens,
                                      cache_read_tokens=cache_read, cache_write_tokens=cache_write)
            return ChunkTelemetry(
                input_tokens=prompt_tokens, output_tokens=output_tokens, total_tokens=total,
                local_prompt_tokens=local_prompt, usage_source=source, is_estimate=not final,
                elapsed_seconds=elapsed,
                ttft_ms=None if first_text is None else (first_text - start) * 1000,
                tokens_per_second=None if output_tokens is None else output_tokens / max(elapsed, 1e-9),
                total_cost_usd=cost, cached_input_tokens=cache_read,
                cache_write_input_tokens=cache_write, stop_reason=stop_reason,
            )

        def apply_anthropic_usage(usage: object) -> None:
            # Every supplied field is cumulative. Missing fields retain the
            # earlier value; an explicit zero must still replace that value.
            nonlocal uncached_input, prompt_tokens, output_tokens, cache_read, cache_write
            for field in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                          "cache_creation_input_tokens"):
                value = getattr(usage, field, None)
                if value is None:
                    continue
                if field == "input_tokens":
                    uncached_input = value
                elif field == "output_tokens":
                    output_tokens = value
                elif field == "cache_read_input_tokens":
                    cache_read = value
                else:
                    cache_write = value
            if uncached_input is not None:
                prompt_tokens = uncached_input + cache_read + cache_write

        safe_error: GatewayProviderError | None = None
        try:
            if provider == "openai":
                if self._openai is None:
                    self._openai = AsyncOpenAI(api_key=_api_key(provider), timeout=60.0, max_retries=0)
                local_prompt = await asyncio.to_thread(_count_openai_text, prompt, model)
                prompt_tokens = local_prompt
                upstream = await self._openai.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}],
                    temperature=temperature, max_completion_tokens=max_tokens,
                    stream=True, stream_options={"include_usage": True},
                )
                async with upstream:
                    async for event in upstream:
                        # The usage-only tail can have an empty choices array.
                        if event.usage is not None:
                            prompt_tokens = event.usage.prompt_tokens
                            output_tokens = event.usage.completion_tokens
                            details = event.usage.prompt_tokens_details
                            cache_read = 0 if details is None else (details.cached_tokens or 0)
                            got_usage = True
                        delta = ""
                        if event.choices:
                            choice = event.choices[0]
                            delta = choice.delta.content or ""
                            if choice.finish_reason is not None:
                                stop_reason = choice.finish_reason
                                ended = True
                        if delta:
                            if first_text is None:
                                first_text = time.perf_counter()
                            text += delta
                            if not got_usage:
                                output_tokens = await asyncio.to_thread(_count_openai_text, text, model)
                        if delta or event.usage is not None:
                            yield StreamChunk(provider=provider, model=model, delta_text=delta,
                                              telemetry=snapshot(False))
            else:
                if self._anthropic is None:
                    self._anthropic = AsyncAnthropic(api_key=_api_key(provider), timeout=60.0, max_retries=0)
                # SDK 2.3 omits the named temperature parameter. Pass the legacy
                # Haiku 4.5 request field using the documented extra_body option.
                upstream = await self._anthropic.messages.create(
                    model=model, messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens, stream=True,
                    extra_body={"temperature": temperature},
                )
                async with upstream:
                    async for event in upstream:
                        delta = ""
                        if event.type == "message_start":
                            apply_anthropic_usage(event.message.usage)
                            partial_usage = True
                        elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                            delta = event.delta.text
                            if delta and first_text is None:
                                first_text = time.perf_counter()
                        elif event.type == "message_delta":
                            apply_anthropic_usage(event.usage)
                            stop_reason = event.delta.stop_reason or stop_reason
                            got_usage = True
                        elif event.type == "message_stop":
                            ended = True
                        if delta or event.type in ("message_start", "message_delta"):
                            yield StreamChunk(provider=provider, model=model, delta_text=delta,
                                              telemetry=snapshot(False))
            if not ended or not got_usage or prompt_tokens is None or output_tokens is None:
                raise IncompleteStreamError("The stream ended without complete provider usage and finish metadata.")
            yield StreamChunk(provider=provider, model=model, is_final=True, telemetry=snapshot(True))
        except GatewayProviderError:
            raise
        except (openai.AuthenticationError, anthropic.AuthenticationError):
            safe_error = AuthenticationError("The provider rejected the API credentials.")
        except (openai.RateLimitError, anthropic.RateLimitError):
            safe_error = RateLimitExceededError("Provider rate or quota limit reached. Try again later.")
        except (openai.APIConnectionError, anthropic.APIConnectionError):
            safe_error = GatewayConnectionError("Cannot reach the provider. Check connectivity and try again.")
        except Exception:
            safe_error = GatewayProviderError("The provider request could not be completed.")
        # Raise after leaving the SDK handler so the original SDK exception is
        # not retained in __context__ for downstream exception serializers.
        if safe_error is not None:
            raise safe_error


LLMGateway = UnifiedLLMGateway
