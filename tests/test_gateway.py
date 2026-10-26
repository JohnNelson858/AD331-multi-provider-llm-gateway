"""Initial offline smoke checks, not the complete Step 5 QA suite.

SDK-shaped mocks exercise gateway control flow without keys or paid requests.
The tokenizer is stubbed here; real tokenizer validation remains for Step 5.
"""

import asyncio
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from src.gateway import AuthenticationError, IncompleteStreamError, UnifiedLLMGateway
from src.pricing import calculate_cost
from src.schemas import StreamChunk


class FakeStream:
    def __init__(self, events):
        self.events = events
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        self.closed = True

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for event in self.events:
            await asyncio.sleep(0)
            yield event


@pytest.fixture(autouse=True)
def offline_tokenizer(monkeypatch):
    monkeypatch.setattr("src.gateway._count_openai_text", lambda text, model: len(text.split()))


def openai_events(with_usage=True):
    def chunk(text=None, finish=None):
        return NS(usage=None, choices=[NS(delta=NS(content=text), finish_reason=finish)])
    events = [chunk(), chunk("Hello "), chunk("world"), chunk(finish="stop")]
    if with_usage:
        events.append(NS(choices=[], usage=NS(prompt_tokens=11, completion_tokens=5,
                                             prompt_tokens_details=NS(cached_tokens=0))))
    return events


@pytest.mark.asyncio
async def test_openai_empty_choice_usage_tail():
    upstream = FakeStream(openai_events())
    create = AsyncMock(return_value=upstream)
    client = NS(chat=NS(completions=NS(create=create)))
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        chunks = [c async for c in gateway.stream("test prompt", "gpt-4o-mini")]
    assert all(isinstance(c, StreamChunk) for c in chunks)
    assert "".join(c.delta_text for c in chunks) == "Hello world"
    assert sum(c.is_final for c in chunks) == 1
    final = chunks[-1].telemetry
    assert (final.input_tokens, final.output_tokens, final.total_tokens) == (11, 5, 16)
    assert final.usage_source == "provider" and not final.is_estimate
    assert final.local_prompt_tokens == 2
    assert final.ttft_ms > 0 and final.tokens_per_second > 0
    assert final.total_cost_usd == Decimal("0.00000465")
    assert upstream.closed
    assert create.await_args.kwargs["stream_options"] == {"include_usage": True}
    assert StreamChunk.model_validate_json(chunks[-1].model_dump_json()) == chunks[-1]


@pytest.mark.asyncio
async def test_anthropic_cumulative_output_is_not_summed():
    upstream = FakeStream([
        NS(type="message_start", message=NS(usage=NS(input_tokens=11, output_tokens=0,
            cache_read_input_tokens=0, cache_creation_input_tokens=0))),
        NS(type="content_block_delta", delta=NS(type="text_delta", text="Hello ")),
        NS(type="message_delta", delta=NS(stop_reason=None), usage=NS(output_tokens=3)),
        NS(type="content_block_delta", delta=NS(type="text_delta", text="world")),
        NS(type="message_delta", delta=NS(stop_reason="end_turn"), usage=NS(output_tokens=5)),
        NS(type="message_stop"),
    ])
    create = AsyncMock(return_value=upstream)
    async with UnifiedLLMGateway(anthropic_client=NS(messages=NS(create=create))) as gateway:
        chunks = [c async for c in gateway.stream("test prompt", "claude-haiku-4-5-20251001")]
    assert "".join(c.delta_text for c in chunks) == "Hello world"
    final = chunks[-1].telemetry
    assert chunks[-1].is_final and not final.is_estimate
    assert (final.input_tokens, final.output_tokens, final.total_tokens) == (11, 5, 16)
    assert final.total_cost_usd == Decimal("0.000036")
    assert final.local_prompt_tokens is None
    assert final.stop_reason == "end_turn" and upstream.closed


@pytest.mark.asyncio
async def test_missing_usage_does_not_fabricate_success():
    upstream = FakeStream(openai_events(with_usage=False))
    client = NS(chat=NS(completions=NS(create=AsyncMock(return_value=upstream))))
    chunks = []
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        with pytest.raises(IncompleteStreamError):
            async for c in gateway.stream("test prompt", "gpt-4o-mini"):
                chunks.append(c)
    assert not any(c.is_final for c in chunks)
    assert upstream.closed


@pytest.mark.asyncio
async def test_missing_key_raises_domain_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async with UnifiedLLMGateway() as gateway:
        with pytest.raises(AuthenticationError, match="OPENAI_API_KEY"):
            _ = [c async for c in gateway.stream("test prompt", "gpt-4o-mini")]


def test_cost_preserves_sub_microdollar_precision():
    assert calculate_cost("gpt-4o-mini", 1, 1) == Decimal("0.00000075")
