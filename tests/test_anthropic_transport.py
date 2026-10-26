"""Real Anthropic SDK + local HTTP mock: no provider calls or real keys."""
import json

import anthropic
import httpx2 as httpx
import pytest

from src.gateway import UnifiedLLMGateway


@pytest.mark.asyncio
async def test_haiku_temperature_uses_compatible_api_version():
    captured = []
    def handle(request):
        body = json.loads(request.content)
        version = request.headers['anthropic-version']
        captured.append((version, body))
        # Match the documented breaking change instead of accepting any request.
        if version == '2026-10-21' and 'temperature' in body:
            return httpx.Response(400, json={'type': 'error', 'error': {
                'type': 'invalid_request_error', 'message': 'temperature is not supported'}})
        events = [
            ('message_start', {'type': 'message_start', 'message': {
                'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'content': [],
                'model': 'claude-haiku-4-5-20251001', 'stop_reason': None,
                'stop_sequence': None, 'usage': {'input_tokens': 11, 'output_tokens': 0}}}),
            ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                'delta': {'type': 'text_delta', 'text': 'Hello world'}}),
            ('message_delta', {'type': 'message_delta', 'delta': {
                'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 5}}),
            ('message_stop', {'type': 'message_stop'}),
        ]
        stream = ''.join(f'event: {name}\ndata: {json.dumps(data)}\n\n' for name, data in events)
        return httpx.Response(200, text=stream, headers={'content-type': 'text/event-stream'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        async with anthropic.AsyncAnthropic(api_key='sk-ant-FAKE-TEST-ONLY-123456789',
                                            http_client=http_client, max_retries=0) as client:
            async with UnifiedLLMGateway(anthropic_client=client) as gateway:
                chunks = [c async for c in gateway.stream('test', 'claude-haiku-4-5-20251001', .7)]
    assert captured[0][0] == '2023-06-01'
    assert captured[0][1]['temperature'] == .7
    assert captured[0][1]['stream'] is True
    assert ''.join(c.delta_text for c in chunks) == 'Hello world'
    assert chunks[-1].is_final
    assert chunks[-1].telemetry.input_tokens == 11
    assert chunks[-1].telemetry.output_tokens == 5
