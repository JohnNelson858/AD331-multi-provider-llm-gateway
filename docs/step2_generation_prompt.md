# Step 2 generation prompt record

## Actual user instruction

> Proceed with Step 2.

The assistant generated the initial code in the same conversation containing
John's full assignment and the sample prompt below. No separate model or
second assistant was invoked. The block below reproduces the sample supplied
in the assignment, rather than claiming John submitted a new standalone prompt.

## Supplied assignment sample prompt

```text
You are an expert Python AI Infrastructure Engineer. I need an asynchronous, streaming multi-provider SDK wrapper supporting both OpenAI (e.g., gpt-4o-mini, gpt-4o) and Anthropic (e.g., claude-3-5-sonnet, claude-3-5-haiku).

Requirements:
1. Environment: Python 3.11+, typed with Pydantic v2.
2. Architecture:
   - A unified class `UnifiedLLMGateway` with an async generator method:
     `async def stream(self, prompt: str, model: str, temperature: float = 0.7) -> AsyncGenerator[StreamChunk, None]:`
   - Use official async clients (`AsyncOpenAI` and `AsyncAnthropic`).
3. Normalization:
   - Define a Pydantic schema `StreamChunk` containing:
     - `delta_text: str` (the new text token)
     - `provider: str` (e.g., "openai" or "anthropic")
     - `model: str`
     - `is_final: bool`
     - `telemetry: Optional[ChunkTelemetry]`
   - Normalize streaming events so that differences in chunk structure between OpenAI and Anthropic are completely hidden from the consumer.
4. Token & Cost Telemetry:
   - Include a static pricing dictionary with USD rates per 1,000,000 input and output tokens for supported models.
   - For OpenAI: enable stream usage tracking (`stream_options={"include_usage": True}`) and use tiktoken for prompt token verification.
   - For Anthropic: capture `message_start` for input tokens and accumulate output tokens from stream events.
   - On the final chunk (`is_final=True`), provide exact input tokens, output tokens, total latency (seconds), Time-to-First-Token (TTFT), tokens per second, and calculated total request cost ($USD).
5. Error Handling:
   - Handle rate limits, invalid API keys, and connection errors by raising typed, custom domain exceptions (e.g., `GatewayProviderError`, `RateLimitExceededError`).
   - Do not leak raw API keys or unhandled stack traces in logs or outputs.

Provide clean, production-ready code split into `schemas.py`, `pricing.py`, and `gateway.py`.
```

## Generation decisions and boundaries

- This output is an initial prototype awaiting the student's Step 3 manual
  audit, not a claim that the sample's production-readiness goal is achieved.
- Text fragments are not necessarily individual tokens. Re-tokenize joined
  OpenAI text for interim estimates and replace estimates with provider totals.
- Anthropic output counts are cumulative and must replace prior snapshots.
- Use `Decimal` for money; six displayed decimal places are not micro-cent
  accounting. One micro-cent is $0.00000001, smaller than one micro-dollar.
- Use `gpt-4o-mini` from the assignment and the documented pinned Claude Haiku
  4.5 model. Model access is not verified. OpenAI marks the former deprecated.
- Provider SDK methods were inspected in the installed environment. Anthropic
  SDK 2.3 lacks a named temperature argument, so the prototype uses `extra_body`.
  Server acceptance still requires a later live integration check.
- No real keys were requested, added to files, or used for paid requests.
- Add a terminal demo and five offline smoke tests as basic draft verification.
  Defer the web interface, full QA, and deployment to their assignment steps.

## Primary references

- https://developers.openai.com/api/docs/models/gpt-4o-mini
- https://platform.claude.com/docs/en/models/haiku-4-5/overview
- https://platform.claude.com/docs/en/about-claude/pricing
- https://platform.claude.com/docs/en/build-with-claude/streaming

Pricing was checked on 2026-10-25. Final usage authority means provider-reported
counts for the completed request, not a guaranteed match to an invoice under
every service tier, cache configuration, or contract.
