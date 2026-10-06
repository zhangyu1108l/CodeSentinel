"""Tests for DeepSeekClient with mocked httpx transport."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.llm.deepseek_client import DeepSeekClient
from app.llm.exceptions import LLMConfigError, LLMException

MESSAGES = [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "user prompt"},
]


def make_client(api_key="test-key", **overrides):
    params = dict(
        base_url="https://api.deepseek.com",
        api_key=api_key,
        model="deepseek-chat",
        timeout=60,
        temperature=0.1,
    )
    params.update(overrides)
    return DeepSeekClient(**params)


def ok_response(content='{"findings": []}'):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


class FakeAsyncClient:
    """Replaces httpx.AsyncClient; records calls on shared mock."""

    mock_post = None
    captured = {}
    constructed_timeouts = []

    def __init__(self, timeout=None):
        self.timeout = timeout
        FakeAsyncClient.constructed_timeouts.append(timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        FakeAsyncClient.captured = {"url": url, "json": json, "headers": headers}
        return await FakeAsyncClient.mock_post(url, json=json, headers=headers)


@pytest.fixture
def mock_http(monkeypatch):
    FakeAsyncClient.mock_post = AsyncMock(return_value=ok_response())
    FakeAsyncClient.captured = {}
    FakeAsyncClient.constructed_timeouts = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


class TestDeepSeekClient:
    def test_missing_api_key_raises_config_error(self):
        client = make_client(api_key="")
        with pytest.raises(LLMConfigError):
            asyncio.run(client.chat(MESSAGES))

    def test_successful_call_returns_content(self, mock_http):
        client = make_client()
        content = asyncio.run(client.chat(MESSAGES))
        assert content == '{"findings": []}'

    def test_request_url_and_authorization(self, mock_http):
        client = make_client(api_key="secret-key")
        asyncio.run(client.chat(MESSAGES))

        captured = FakeAsyncClient.captured
        assert captured["url"] == "https://api.deepseek.com/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer secret-key"

    def test_request_payload_fields(self, mock_http):
        client = make_client()
        asyncio.run(client.chat(MESSAGES))

        payload = FakeAsyncClient.captured["json"]
        assert payload["model"] == "deepseek-chat"
        assert payload["messages"] == MESSAGES
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["temperature"] == 0.1

    def test_base_url_trailing_slash_is_stripped(self, mock_http):
        client = make_client(base_url="https://api.deepseek.com/")
        asyncio.run(client.chat(MESSAGES))
        assert FakeAsyncClient.captured["url"] == (
            "https://api.deepseek.com/chat/completions"
        )

    def test_timeout_raises_llm_exception(self, mock_http):
        mock_http.mock_post = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = make_client()
        with pytest.raises(LLMException, match="timed out"):
            asyncio.run(client.chat(MESSAGES))

    def test_http_4xx_raises_llm_exception(self, mock_http):
        error = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=httpx.Request("POST", "https://api.deepseek.com"),
            response=httpx.Response(401),
        )
        mock_http.mock_post = AsyncMock(side_effect=error)
        client = make_client()
        with pytest.raises(LLMException, match="HTTP 401"):
            asyncio.run(client.chat(MESSAGES))

    def test_http_5xx_raises_llm_exception(self, mock_http):
        error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("POST", "https://api.deepseek.com"),
            response=httpx.Response(500),
        )
        mock_http.mock_post = AsyncMock(side_effect=error)
        client = make_client()
        with pytest.raises(LLMException, match="HTTP 500"):
            asyncio.run(client.chat(MESSAGES))

    def test_rate_limit_429_raises_llm_exception(self, mock_http):
        error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("POST", "https://api.deepseek.com"),
            response=httpx.Response(429),
        )
        mock_http.mock_post = AsyncMock(side_effect=error)
        client = make_client()
        with pytest.raises(LLMException, match="HTTP 429"):
            asyncio.run(client.chat(MESSAGES))

    def test_empty_content_raises_llm_exception(self, mock_http):
        mock_http.mock_post = AsyncMock(
            return_value=ok_response(content="")
        )
        client = make_client()
        with pytest.raises(LLMException, match="empty message content"):
            asyncio.run(client.chat(MESSAGES))

    def test_malformed_response_body_raises_llm_exception(self, mock_http):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"unexpected": "shape"}
        mock_http.mock_post = AsyncMock(return_value=resp)
        client = make_client()
        with pytest.raises(LLMException):
            asyncio.run(client.chat(MESSAGES))

    def test_uses_configured_timeout(self, mock_http):
        client = make_client(timeout=33)
        asyncio.run(client.chat(MESSAGES))
        assert 33 in FakeAsyncClient.constructed_timeouts
