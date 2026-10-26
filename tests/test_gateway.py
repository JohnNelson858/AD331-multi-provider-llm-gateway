"""Step 5 gateway checks: real local tokenizer, mocked provider transport.

No API credentials or paid requests. First use may download tokenizer data.
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
    assert all(isinstance(c, StreamChunk) for c in chunks)
    final = chunks[-1].telemetry
    assert final.ttft_ms > 0 and final.tokens_per_second > 0 and final.total_cost_usd > 0
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


@pytest.mark.asyncio
async def test_fifty_word_prompt_uses_real_tiktoken_and_keeps_provider_count():
    import tiktoken
    from tests.qa_data import TOKEN_PROMPT
    assert len(TOKEN_PROMPT.split()) == 50
    reference = len(tiktoken.get_encoding('o200k_base').encode(TOKEN_PROMPT))
    assert reference == 150  # Fixed prompt/tokenizer regression reference.
    # Deliberately different fixture usage: provider counts must remain authoritative.
    billed_fixture_count = reference + 17
    events = openai_events()
    events[-1].usage.prompt_tokens = billed_fixture_count
    upstream = FakeStream(events)
    client = NS(chat=NS(completions=NS(create=AsyncMock(return_value=upstream))))
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        chunks = [c async for c in gateway.stream(TOKEN_PROMPT, 'gpt-4o-mini')]
    local = chunks[-1].telemetry.local_prompt_tokens
    assert local == reference  # Stronger than assignment's +/-10% for raw text.
    assert abs(local - reference) / reference <= .10
    assert chunks[-1].telemetry.input_tokens == billed_fixture_count
    assert chunks[-1].telemetry.usage_source == 'provider'


@pytest.mark.parametrize('text',[' café 你好 👋\n', '1234567890', 'x = 1\n\tprint(x)', '<|endoftext|>'])
def test_real_tokenizer_handles_unicode_whitespace_code_and_special_strings(text):
    import tiktoken
    from src.gateway import _count_openai_text
    enc = tiktoken.get_encoding('o200k_base')
    ids = enc.encode(text, disallowed_special=())
    assert _count_openai_text(text, 'gpt-4o-mini') == len(ids)
    assert enc.decode(ids) == text


@pytest.mark.asyncio
async def test_ttft_ignores_empty_metadata_and_stops_at_first_text(monkeypatch):
    clock = {'now': 0.0}
    monkeypatch.setattr('src.gateway.time', NS(perf_counter=lambda: clock['now']))
    class TimedStream(FakeStream):
        async def _iterate(self):
            for instant, event in zip([1,4,5,6,7], self.events):
                clock['now'] = instant
                yield event
    upstream = TimedStream(openai_events())
    client = NS(chat=NS(completions=NS(create=AsyncMock(return_value=upstream))))
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        chunks = [c async for c in gateway.stream('test', 'gpt-4o-mini')]
    assert chunks[-1].telemetry.ttft_ms == 4000
    assert chunks[-1].telemetry.elapsed_seconds == 7
    assert chunks[-1].telemetry.tokens_per_second == 5 / 7


@pytest.mark.asyncio
async def test_cancellation_closes_provider_stream_without_final_event():
    text_seen = asyncio.Event()
    class WaitingStream(FakeStream):
        async def _iterate(self):
            yield self.events[1]
            text_seen.set()
            await asyncio.Event().wait()
    upstream = WaitingStream(openai_events())
    client = NS(chat=NS(completions=NS(create=AsyncMock(return_value=upstream))))
    chunks = []
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        async def consume():
            async for chunk in gateway.stream('test','gpt-4o-mini'):
                chunks.append(chunk)
        task = asyncio.create_task(consume())
        await asyncio.wait_for(text_seen.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert upstream.closed
    assert not any(c.is_final for c in chunks)


@pytest.mark.asyncio
async def test_abandoned_generator_closes_provider_stream():
    from contextlib import aclosing
    upstream = FakeStream(openai_events())
    client = NS(chat=NS(completions=NS(create=AsyncMock(return_value=upstream))))
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        async with aclosing(gateway.stream('test','gpt-4o-mini')) as stream:
            await anext(stream)
    assert upstream.closed


@pytest.mark.asyncio
async def test_concurrent_requests_keep_counters_separate_and_reuse_owned_client(monkeypatch):
    streams = []
    async def create(**kwargs):
        count = 21 if kwargs['messages'][0]['content'] == 'first' else 37
        events = openai_events()
        events[-1].usage.prompt_tokens = count
        upstream = FakeStream(events)
        streams.append(upstream)
        return upstream
    client = NS(chat=NS(completions=NS(create=AsyncMock(side_effect=create))),close=AsyncMock())
    from unittest.mock import Mock
    constructor = Mock(return_value=client)
    monkeypatch.setattr('src.gateway.AsyncOpenAI',constructor)
    monkeypatch.setenv('OPENAI_API_KEY','sk-FAKE-ONLY-FOR-TESTS-123456789')
    async with UnifiedLLMGateway() as gateway:
        async def consume(prompt):
            return [c async for c in gateway.stream(prompt,'gpt-4o-mini')]
        first,second = await asyncio.gather(consume('first'),consume('second'))
    constructor.assert_called_once()
    assert first[-1].telemetry.input_tokens == 21
    assert second[-1].telemetry.input_tokens == 37
    assert all(stream.closed for stream in streams)
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_zero_text_output_has_no_ttft_and_still_valid_usage():
    events = openai_events()
    events = [events[0],events[-2],events[-1]]
    events[-1].usage.completion_tokens = 0
    client = NS(chat=NS(completions=NS(create=AsyncMock(return_value=FakeStream(events)))))
    async with UnifiedLLMGateway(openai_client=client) as gateway:
        chunks = [c async for c in gateway.stream('test','gpt-4o-mini')]
    assert chunks[-1].is_final
    assert chunks[-1].telemetry.ttft_ms is None
    assert chunks[-1].telemetry.tokens_per_second == 0


@pytest.mark.asyncio
async def test_anthropic_missing_stop_does_not_fabricate_final():
    upstream = FakeStream([
        NS(type='message_start',message=NS(usage=NS(input_tokens=11,output_tokens=0))),
        NS(type='message_delta',usage=NS(output_tokens=1),delta=NS(stop_reason='end_turn')),
    ])
    client = NS(messages=NS(create=AsyncMock(return_value=upstream)))
    chunks = []
    async with UnifiedLLMGateway(anthropic_client=client) as gateway:
        with pytest.raises(IncompleteStreamError):
            async for chunk in gateway.stream('test','claude-haiku-4-5-20251001'):
                chunks.append(chunk)
    assert upstream.closed
    assert not any(chunk.is_final for chunk in chunks)
