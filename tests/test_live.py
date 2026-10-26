"""Opt-in paid integration checks. Never run by default; no output text assertion."""
from pathlib import Path

import pytest
from dotenv import load_dotenv
from src.gateway import UnifiedLLMGateway
from tests.qa_data import TOKEN_PROMPT


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize('model',['gpt-4o-mini','claude-haiku-4-5-20251001'])
async def test_live_stream_usage_and_telemetry(model,record_property):
    load_dotenv(Path(__file__).parent.parent/'.env',override=False)
    async with UnifiedLLMGateway() as gateway:
        chunks = [c async for c in gateway.stream(TOKEN_PROMPT,model,temperature=0,max_tokens=32)]
    assert chunks[-1].is_final and sum(c.is_final for c in chunks)==1
    final=chunks[-1].telemetry
    assert final.usage_source=='provider' and not final.is_estimate
    assert final.total_tokens==final.input_tokens+final.output_tokens
    assert final.input_tokens>0 and final.output_tokens>0
    assert final.total_cost_usd>0 and final.tokens_per_second>0 and final.ttft_ms>0
    if model=='gpt-4o-mini':
        relative_difference=abs(final.input_tokens-final.local_prompt_tokens)/final.input_tokens
        record_property('raw_text_vs_billed_input_difference',relative_difference)
        assert relative_difference<=.10, 'Billed chat input differs by >10%; inspect framing/model/tokenizer rather than adjusting counts.'
    # Anthropic has a different tokenizer. Never compare its counts to tiktoken.
    record_property('input_tokens',final.input_tokens)
    record_property('output_tokens',final.output_tokens)
    record_property('ttft_ms',final.ttft_ms)
    record_property('total_cost_usd',str(final.total_cost_usd))
