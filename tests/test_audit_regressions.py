"""Step 3 regressions reproduced against baseline commit 6d77821.

No paid requests. These supplement the Step 2 smoke checks, not live QA.
"""

from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from anthropic.types import RawMessageDeltaEvent, Usage

from src.gateway import GatewayProviderError, UnifiedLLMGateway
from tests.test_gateway import FakeStream


@pytest.mark.asyncio
async def test_anthropic_final_input_and_cache_counts_replace_start_values():
    initial = Usage(input_tokens=11, output_tokens=0,
                    cache_read_input_tokens=0, cache_creation_input_tokens=0)
    update = RawMessageDeltaEvent.model_validate({
        "type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"input_tokens": 20, "cache_read_input_tokens": 5,
                  "cache_creation_input_tokens": 0, "output_tokens": 5},
    })
    upstream = FakeStream([
        NS(type="message_start", message=NS(usage=initial)),
        NS(type="content_block_delta", delta=NS(type="text_delta", text="Hello")),
        update, NS(type="message_stop"),
    ])
    client = NS(messages=NS(create=AsyncMock(return_value=upstream)))
    async with UnifiedLLMGateway(anthropic_client=client) as gateway:
        chunks = [c async for c in gateway.stream("test", "claude-haiku-4-5-20251001")]
    final = chunks[-1].telemetry
    assert final.input_tokens == 25  # 20 uncached + 5 cached, counted once.
    assert final.cached_input_tokens == 5
    assert final.total_tokens == 30
    assert final.total_cost_usd == Decimal("0.0000455")


@pytest.mark.asyncio
async def test_anthropic_start_usage_is_labeled_as_partial_provider_usage():
    upstream = FakeStream([
        NS(type="message_start", message=NS(usage=Usage(input_tokens=11, output_tokens=0))),
        NS(type="content_block_delta", delta=NS(type="text_delta", text="Hi")),
        RawMessageDeltaEvent.model_validate({"type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 1}}),
        NS(type="message_stop"),
    ])
    client = NS(messages=NS(create=AsyncMock(return_value=upstream)))
    async with UnifiedLLMGateway(anthropic_client=client) as gateway:
        chunks = [c async for c in gateway.stream("test", "claude-haiku-4-5-20251001")]
    assert chunks[0].telemetry.usage_source == "provider_partial"
    assert chunks[0].telemetry.input_tokens == 11
    assert chunks[-1].telemetry.usage_source == "provider"


@pytest.mark.asyncio
async def test_sanitized_error_does_not_retain_secret_in_exception_chain():
    fake_secret = "FAKE-SECRET-FOR-TESTING-ONLY"
    client = NS(messages=NS(create=AsyncMock(side_effect=RuntimeError(fake_secret))))
    async with UnifiedLLMGateway(anthropic_client=client) as gateway:
        with pytest.raises(GatewayProviderError) as caught:
            _ = [c async for c in gateway.stream("test", "claude-haiku-4-5-20251001")]
    exc = caught.value
    assert fake_secret not in str(exc)
    assert fake_secret not in repr(exc)
    assert exc.__context__ is None
    assert exc.__cause__ is None


@pytest.mark.asyncio
async def test_shutdown_attempts_both_owned_clients_after_first_close_fails():
    first = NS(close=AsyncMock(side_effect=RuntimeError("FAKE-CLOSE-SECRET")))
    second = NS(close=AsyncMock())
    gateway = UnifiedLLMGateway()
    # Simulate already-created, gateway-owned pooled clients.
    gateway._openai = first
    gateway._anthropic = second
    with pytest.raises(GatewayProviderError) as caught:
        await gateway.aclose()
    assert "FAKE-CLOSE-SECRET" not in str(caught.value)
    second.close.assert_awaited_once()
    assert caught.value.__context__ is None


@pytest.mark.asyncio
async def test_shutdown_is_idempotent_and_respects_injected_client_ownership():
    owned = NS(close=AsyncMock())
    borrowed = NS(close=AsyncMock())
    gateway = UnifiedLLMGateway(anthropic_client=borrowed)
    gateway._openai = owned
    await gateway.aclose()
    await gateway.aclose()
    owned.close.assert_awaited_once()
    borrowed.close.assert_not_awaited()
