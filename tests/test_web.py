"""Step 4 local web contract checks; no real provider requests."""
import json
from decimal import Decimal

from fastapi.testclient import TestClient

from src.app import create_app
from src.gateway import AuthenticationError
from src.schemas import ChunkTelemetry, StreamChunk


class FakeGateway:
    def __init__(self):
        self.closed = False
        self.stream_closed = False
        self.calls = []

    async def aclose(self):
        self.closed = True

    async def stream(self, prompt, model, temperature, *, max_tokens):
        self.calls.append((prompt, model, temperature, max_tokens))
        provider = 'openai' if model.startswith('gpt') else 'anthropic'
        try:
            if prompt == 'fail':
                raise AuthenticationError('FAKE-SECRET-DO-NOT-EXPOSE')
            t = ChunkTelemetry(input_tokens=11, output_tokens=5, total_tokens=16,
                               usage_source='provider', is_estimate=False,
                               elapsed_seconds=1.0, ttft_ms=20.0, tokens_per_second=5,
                               total_cost_usd=Decimal('0.00000465'), stop_reason='stop')
            yield StreamChunk(provider=provider, model=model, delta_text='<script>unsafe()</script>\nHello', telemetry=t)
            yield StreamChunk(provider=provider, model=model, is_final=True, telemetry=t)
        finally:
            self.stream_closed = True


def body(**changes):
    return {'provider': 'openai', 'model': 'gpt-4o-mini', 'prompt': 'test',
            'temperature': 0.7, 'max_tokens': 512, **changes}


def events(response):
    return [(frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:]))
            for frame in response.text.strip().split('\n\n')]


def test_page_models_and_gateway_lifetime():
    gateway = FakeGateway()
    with TestClient(create_app(lambda: gateway)) as client:
        page = client.get('/')
        assert page.status_code == 200
        assert 'Live telemetry' in page.text
        assert "script-src 'self'" in page.headers['content-security-policy']
        assert {m['provider'] for m in client.get('/api/models').json()} == {'openai','anthropic'}
        assert not gateway.closed
    assert gateway.closed


def test_sse_normalizes_text_formats_decimal_and_reuses_gateway():
    gateway = FakeGateway()
    with TestClient(create_app(lambda: gateway)) as client:
        for provider, model in [('openai','gpt-4o-mini'),('anthropic','claude-haiku-4-5-20251001')]:
            response = client.post('/api/stream', json=body(provider=provider, model=model))
            assert response.headers['content-type'].startswith('text/event-stream')
            assert response.headers['cache-control'] == 'no-store'
            chunks = events(response)
            assert [e for e, _ in chunks] == ['chunk','chunk']
            assert chunks[0][1]['delta_text'] == '<script>unsafe()</script>\nHello'
            assert chunks[-1][1]['is_final']
            assert chunks[-1][1]['display_cost_usd'] == '0.000005'
            assert chunks[-1][1]['telemetry']['total_cost_usd'] == '0.00000465'
        assert len(gateway.calls) == 2
        assert gateway.stream_closed


def test_provider_error_is_sanitized_and_not_a_successful_final():
    with TestClient(create_app(FakeGateway)) as client:
        response = client.post('/api/stream', json=body(prompt='fail'))
        frames = events(response)
        assert len(frames) == 1 and frames[0][0] == 'error'
        assert frames[0][1]['type'] == 'AuthenticationError'
        assert 'FAKE-SECRET' not in response.text


def test_invalid_requests_do_not_echo_prompt_or_call_gateway():
    gateway = FakeGateway()
    with TestClient(create_app(lambda: gateway)) as client:
        for changes in [dict(provider='anthropic'),dict(temperature=2),dict(prompt=' '),
                        dict(max_tokens=True),dict(prompt='x'*16001)]:
            response = client.post('/api/stream', json=body(**changes))
            assert response.status_code == 422
            assert 'input' not in response.json()
        assert not gateway.calls


def test_cross_origin_request_is_rejected_before_provider_call():
    gateway = FakeGateway()
    with TestClient(create_app(lambda: gateway)) as client:
        response = client.post('/api/stream', json=body(), headers={'Origin':'https://unrelated.example'})
        assert response.status_code == 403
        assert not gateway.calls


def test_host_header_is_restricted():
    with TestClient(create_app(FakeGateway)) as client:
        assert client.get('/', headers={'host':'unrelated.example'}).status_code == 400
