"""Tests for PrContextClient with mocked httpx transport (Phase 6.7.2)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

from app.config.settings import settings
from app.context.pr_context_client import PrContextClient
from app.schemas.pr_context import PrContext

JAVA_RESPONSE = {
    "taskId": 7,
    "owner": "owner",
    "repo": "repo",
    "prNumber": 42,
    "commitSha": "abc123",
    "title": "Add review context",
    "state": "open",
    "baseRef": "main",
    "headRef": "feature/context",
    "files": [
        {
            "path": "src/App.java",
            "previousPath": None,
            "status": "modified",
            "additions": 3,
            "deletions": 1,
            "changes": 4,
            "patch": "@@ patch @@",
            "blobUrl": "https://github.com/owner/repo/blob/abc/src/App.java",
            "content_available": True,
            "content_truncated": False,
            "content_reason": None,
            "content": "class App {}",
        },
        {
            "path": "src/Old.java",
            "previousPath": "src/Legacy.java",
            "status": "removed",
            "additions": 0,
            "deletions": 5,
            "changes": 5,
            "patch": None,
            "blobUrl": "https://github.com/owner/repo/blob/abc/src/Old.java",
            "content_available": False,
            "content_truncated": False,
            "content_reason": "removed",
            "content": None,
        },
    ],
}


def make_client(**overrides):
    params = dict(base_url="http://localhost:8080", timeout=30)
    params.update(overrides)
    return PrContextClient(**params)


def ok_response(payload=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = JAVA_RESPONSE if payload is None else payload
    return resp


class FakeAsyncClient:
    """Replaces httpx.AsyncClient; records calls on shared mock."""

    mock_get = None
    captured = {}
    constructed_timeouts = []

    def __init__(self, timeout=None):
        self.timeout = timeout
        FakeAsyncClient.constructed_timeouts.append(timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        FakeAsyncClient.captured = {"url": url}
        return await FakeAsyncClient.mock_get(url)


@pytest.fixture
def mock_http(monkeypatch):
    FakeAsyncClient.mock_get = AsyncMock(return_value=ok_response())
    FakeAsyncClient.captured = {}
    FakeAsyncClient.constructed_timeouts = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


def http_error(status_code):
    return httpx.HTTPStatusError(
        f"{status_code} error",
        request=httpx.Request("GET", "http://localhost:8080"),
        response=httpx.Response(status_code),
    )


class TestPrContextClient:
    def test_fetches_and_parses_context(self, mock_http):
        context = asyncio.run(make_client().fetch(7))

        assert isinstance(context, PrContext)
        assert context.taskId == 7
        assert context.owner == "owner"
        assert context.prNumber == 42
        assert context.commitSha == "abc123"
        assert len(context.files) == 2

    def test_request_url_contains_task_id(self, mock_http):
        asyncio.run(
            make_client(base_url="http://java:8080").fetch(42)
        )

        assert FakeAsyncClient.captured["url"] == (
            "http://java:8080/api/tasks/42/pr-context"
        )

    def test_base_url_trailing_slash_is_stripped(self, mock_http):
        asyncio.run(
            make_client(base_url="http://java:8080/").fetch(1)
        )

        assert FakeAsyncClient.captured["url"] == (
            "http://java:8080/api/tasks/1/pr-context"
        )

    def test_uses_configured_timeout(self, mock_http):
        asyncio.run(make_client(timeout=17).fetch(1))
        assert 17 in FakeAsyncClient.constructed_timeouts

    def test_defaults_come_from_settings(self):
        client = PrContextClient()
        assert client.base_url == settings.JAVA_SERVICE_URL.rstrip("/")
        assert client.timeout == settings.PR_CONTEXT_TIMEOUT

    def test_multi_file_order_and_content(self, mock_http):
        context = asyncio.run(make_client().fetch(7))

        assert [file.path for file in context.files] == [
            "src/App.java",
            "src/Old.java",
        ]
        assert context.files[0].content == "class App {}"
        assert context.files[0].content_available is True
        assert context.files[1].previousPath == "src/Legacy.java"

    def test_content_null_and_reason_are_kept(self, mock_http):
        context = asyncio.run(make_client().fetch(7))

        removed = context.files[1]
        assert removed.content is None
        assert removed.content_available is False
        assert removed.content_reason == "removed"

    def test_snake_case_fields_are_mapped(self, mock_http):
        payload = {**JAVA_RESPONSE, "files": [dict(JAVA_RESPONSE["files"][0])]}
        payload["files"][0]["content_available"] = True
        payload["files"][0]["content_reason"] = None
        mock_http.mock_get = AsyncMock(return_value=ok_response(payload))

        context = asyncio.run(make_client().fetch(7))

        assert context.files[0].content_available is True
        assert context.files[0].content_reason is None

    def test_empty_files(self, mock_http):
        mock_http.mock_get = AsyncMock(
            return_value=ok_response({**JAVA_RESPONSE, "files": []})
        )
        context = asyncio.run(make_client().fetch(7))
        assert context.files == []

    def test_http_404_is_raised(self, mock_http):
        mock_http.mock_get = AsyncMock(side_effect=http_error(404))
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            asyncio.run(make_client().fetch(99))
        assert exc_info.value.response.status_code == 404

    def test_http_500_is_raised(self, mock_http):
        mock_http.mock_get = AsyncMock(side_effect=http_error(500))
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            asyncio.run(make_client().fetch(7))
        assert exc_info.value.response.status_code == 500

    def test_malformed_body_raises_schema_error(self, mock_http):
        payload = {**JAVA_RESPONSE}
        del payload["taskId"]
        mock_http.mock_get = AsyncMock(return_value=ok_response(payload))

        with pytest.raises(ValidationError):
            asyncio.run(make_client().fetch(7))

    def test_non_json_body_raises(self, mock_http):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.side_effect = ValueError("not json")
        mock_http.mock_get = AsyncMock(return_value=resp)

        with pytest.raises(ValueError):
            asyncio.run(make_client().fetch(7))

    def test_validation_failure_still_raises_after_logging(self, mock_http, caplog):
        payload = {**JAVA_RESPONSE, "files": [{"status": "modified"}]}
        mock_http.mock_get = AsyncMock(return_value=ok_response(payload))

        with pytest.raises(ValidationError):
            asyncio.run(make_client().fetch(7))
        assert "Failed to fetch PR context for task 7" in caplog.text

    def test_client_is_transport_only(self, mock_http):
        # Only the documented GET endpoint may be called.
        asyncio.run(make_client().fetch(7))
        assert FakeAsyncClient.captured["url"].endswith("/pr-context")