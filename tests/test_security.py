"""Credential boundaries and secret-bearing SDK error tests. Fake keys only."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import logging

import anthropic
import openai
import pytest
import httpx2 as httpx

from src.gateway import (
    AuthenticationError, GatewayConnectionError, RateLimitExceededError, UnifiedLLMGateway,
)

PROVIDERS = [('openai','gpt-4o-mini','OPENAI_API_KEY'),
             ('anthropic','claude-haiku-4-5-20251001','ANTHROPIC_API_KEY')]
FAKE_KEY = 'sk-FAKE-SECRET-FOR-TESTING-ONLY-123456789'


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,model,variable',PROVIDERS)
@pytest.mark.parametrize('value',[None,'','your_key_here','sk-short','sk-your_placeholder_key_123456789',
                                 'sk-bad key with spaces 123456789', 'sk-bad\nheader-123456789012345'])
async def test_missing_or_malformed_key_fails_before_client_creation(monkeypatch,provider,model,variable,value):
    if value is None:
        monkeypatch.delenv(variable,raising=False)
    else:
        monkeypatch.setenv(variable,value)
    constructor=Mock(side_effect=AssertionError('Client must not be created'))
    monkeypatch.setattr('src.gateway.AsyncOpenAI' if provider=='openai' else 'src.gateway.AsyncAnthropic',constructor)
    async with UnifiedLLMGateway() as gateway:
        with pytest.raises(AuthenticationError,match=variable) as caught:
            _=[c async for c in gateway.stream('test',model)]
    constructor.assert_not_called()
    if value:
        assert value not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,model,variable',PROVIDERS)
@pytest.mark.parametrize('error_name,status,expected',[
    ('AuthenticationError',401,AuthenticationError),
    ('RateLimitError',429,RateLimitExceededError),
    ('APIConnectionError',None,GatewayConnectionError),
])
async def test_sdk_errors_are_typed_and_do_not_expose_secrets(caplog,provider,model,variable,error_name,status,expected):
    sdk=openai if provider=='openai' else anthropic
    request=httpx.Request('POST','https://api.example.invalid',headers={'Authorization':f'Bearer {FAKE_KEY}'})
    if status is None:
        original=sdk.APIConnectionError(message=FAKE_KEY,request=request)
    else:
        original=getattr(sdk,error_name)(FAKE_KEY,response=httpx.Response(status,request=request),body={'error':FAKE_KEY})
    create=AsyncMock(side_effect=original)
    client=NS(chat=NS(completions=NS(create=create))) if provider=='openai' else NS(messages=NS(create=create))
    kwargs={'openai_client':client} if provider=='openai' else {'anthropic_client':client}
    with caplog.at_level(logging.DEBUG):
        async with UnifiedLLMGateway(**kwargs) as gateway:
            with pytest.raises(expected) as caught:
                _=[c async for c in gateway.stream('test',model)]
    assert FAKE_KEY not in str(caught.value)
    assert FAKE_KEY not in repr(caught.value)
    assert FAKE_KEY not in caplog.text
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
