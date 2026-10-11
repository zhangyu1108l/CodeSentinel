"""Tests for AiServiceClient response handling and safe diagnostics."""

import traceback
from unittest.mock import MagicMock

import httpx
import pytest

from app.schemas.review import ReviewTaskRequest
from app.worker import ai_client as ai_client_module
from app.worker.ai_client import AiServiceClient, AiServiceResponseError

SENTINEL = "SENTINEL-AI-RESPONSE-DO-NOT-LOG"


def make_request():
    return ReviewTaskRequest(
        task_id=7,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        files=[],
    )


def make_response(payload=None, error=None):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    if error is not None:
        response.raise_for_status.side_effect = error
    response.json.return_value = payload
    return response


def http_error(status_code=500):
    return httpx.HTTPStatusError(
        f"{status_code} error",
        request=httpx.Request("POST", "http://localhost:8000/api/reviews"),
        response=httpx.Response(status_code),
    )


@pytest.fixture
def mock_post(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr(ai_client_module.httpx, "post", post)
    return post


class TestAiServiceClientDiagnostics:
    def test_schema_failure_raises_sanitized_error(
        self, mock_post, caplog
    ):
        finding = {
            "category": "BUG",
            "severity": "HIGH",
            "confidence": 0.9,
            "rule_id": "R1",
            "title": "title",
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 1,
            "description": SENTINEL,
            "reason": "reason",
            "references": [],
            # "suggestion" is missing: the raw ValidationError preview
            # would embed the whole finding dict, including the sentinel.
        }
        payload = {
            "task_id": 7,
            "status": "COMPLETED",
            "report": {},
            "findings": [finding],
        }
        mock_post.return_value = make_response(payload=payload)

        with caplog.at_level("ERROR", logger="codesentinel-ai.ai_client"):
            with pytest.raises(AiServiceResponseError) as exc_info:
                AiServiceClient().review(make_request())

        message = str(exc_info.value)
        assert message == "AI service returned an invalid review result"
        assert SENTINEL not in message

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "Failed to request review for task 7" in log_text
        assert "invalid response schema" in log_text
        assert "findings.0.suggestion" in log_text
        assert "missing" in log_text
        assert SENTINEL not in log_text
        assert "input_value" not in log_text

        text = "".join(traceback.format_exception(exc_info.value))
        assert SENTINEL not in text
        assert "ValidationError" not in text

    def test_http_status_error_logs_status_and_reraises(
        self, mock_post, caplog
    ):
        mock_post.return_value = make_response(error=http_error(503))

        with caplog.at_level("ERROR", logger="codesentinel-ai.ai_client"):
            with pytest.raises(httpx.HTTPStatusError):
                AiServiceClient().review(make_request())

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "http_status=503" in log_text
        assert SENTINEL not in log_text

    def test_unexpected_error_logs_type_only(self, mock_post, caplog):
        mock_post.side_effect = RuntimeError(f"boom {SENTINEL}")

        with caplog.at_level("ERROR", logger="codesentinel-ai.ai_client"):
            with pytest.raises(RuntimeError):
                AiServiceClient().review(make_request())

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "RuntimeError" in log_text
        assert SENTINEL not in log_text
        assert "boom" not in log_text

    def test_success_path_is_unchanged(self, mock_post):
        payload = {
            "task_id": 7,
            "status": "COMPLETED",
            "report": {"summary": "ok"},
            "findings": [],
        }
        mock_post.return_value = make_response(payload=payload)

        result = AiServiceClient().review(make_request())

        assert result.task_id == 7
        assert result.status == "COMPLETED"
        assert result.findings == []