"""Tests for JavaServiceClient result submission (Phase 9.5.3B2)."""

import logging
from unittest.mock import MagicMock

import httpx
import pytest

from app.schemas.review import ReviewFinding, ReviewTaskResult
from app.worker import java_client as java_client_module
from app.worker.java_client import (
    INTERNAL_TOKEN_HEADER,
    JavaServiceClient,
    ResultSubmitConfigurationError,
)

TOKEN = "SENTINEL-INTERNAL-TOKEN-DO-NOT-LOG"
COMMIT_SHA = "cf2f13fbbb80466f46825fa94558d21c64dec8cf"
BASE_URL = "http://java.local:8080/"


def make_result():
    return ReviewTaskResult(
        task_id=7,
        status="DEGRADED",
        report={"summary": "sensitive report must not be sent"},
        findings=[
            ReviewFinding(
                category="BUG",
                severity="HIGH",
                confidence=0.9,
                rule_id="R-1",
                title="title",
                file_path="src/A.java",
                start_line=1,
                end_line=2,
                description="d",
                reason="r",
                suggestion="s",
                references=["CWE-1"],
            )
        ],
    )


def make_response(status_code, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload if payload is not None else {}
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code} error",
            request=httpx.Request(
                "POST", "http://java.local:8080/api/tasks/7/result"
            ),
            response=httpx.Response(status_code),
        )
    return response


@pytest.fixture
def mock_post(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr(java_client_module.httpx, "post", post)
    return post


def make_client(**overrides):
    kwargs = {
        "base_url": BASE_URL,
        "internal_token": TOKEN,
        "submit_timeout": 17.0,
    }
    kwargs.update(overrides)
    return JavaServiceClient(**kwargs)


class TestSubmitResultSuccess:
    def test_accepts_202_and_returns_reception_body(self, mock_post):
        mock_post.return_value = make_response(
            202,
            {
                "task_id": 7,
                "commit_sha": COMMIT_SHA,
                "duplicate": False,
                "publish_status": "PENDING",
                "received_at": "2026-10-13T21:01:22",
            },
        )

        outcome = make_client().submit_result(7, COMMIT_SHA, make_result())

        assert outcome["status_code"] == 202
        assert outcome["duplicate"] is False
        assert outcome["publish_status"] == "PENDING"

        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == (
            "http://java.local:8080/api/tasks/7/result"
        )
        kwargs = mock_post.call_args.kwargs
        assert kwargs["timeout"] == 17.0
        assert kwargs["headers"] == {INTERNAL_TOKEN_HEADER: TOKEN}

        payload = kwargs["json"]
        assert set(payload.keys()) == {"commit_sha", "status", "findings"}
        assert payload["commit_sha"] == COMMIT_SHA
        assert payload["status"] == "DEGRADED"
        finding = payload["findings"][0]
        assert set(finding.keys()) == {
            "category",
            "severity",
            "confidence",
            "rule_id",
            "title",
            "file_path",
            "start_line",
            "end_line",
            "description",
            "reason",
            "suggestion",
            "references",
        }
        assert finding["category"] == "BUG"
        assert finding["severity"] == "HIGH"
        assert finding["confidence"] == 0.9
        assert finding["start_line"] == 1
        assert finding["end_line"] == 2
        assert finding["references"] == ["CWE-1"]

    def test_accepts_200_duplicate(self, mock_post):
        mock_post.return_value = make_response(
            200,
            {
                "task_id": 7,
                "commit_sha": COMMIT_SHA,
                "duplicate": True,
                "publish_status": "PENDING",
                "received_at": "2026-10-13T21:01:22",
            },
        )

        outcome = make_client().submit_result(7, COMMIT_SHA, make_result())

        assert outcome["status_code"] == 200
        assert outcome["duplicate"] is True

    def test_uses_settings_submit_timeout_by_default(self, mock_post):
        mock_post.return_value = make_response(
            202,
            {"task_id": 7, "duplicate": False, "publish_status": "PENDING"},
        )

        client = JavaServiceClient(base_url=BASE_URL, internal_token=TOKEN)
        client.submit_result(7, COMMIT_SHA, make_result())

        assert mock_post.call_args.kwargs["timeout"] == (
            java_client_module.settings.RESULT_SUBMIT_TIMEOUT
        )


class TestSubmitResultConflict:
    def test_409_returns_conflict_marker_without_claiming_stored(
        self, mock_post, caplog
    ):
        mock_post.return_value = make_response(
            409,
            {
                "error": (
                    "a different result already exists for this task "
                    "and commit"
                )
            },
        )

        with caplog.at_level(
            logging.WARNING, logger="codesentinel-ai.java_client"
        ):
            outcome = make_client().submit_result(
                7, COMMIT_SHA, make_result()
            )

        assert outcome == {"status_code": 409, "conflict": True}
        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "409" in log_text
        assert "was not stored" in log_text
        assert "Submitted review result" not in log_text
        assert TOKEN not in log_text

    def test_409_never_touches_response_body(self, mock_post):
        response = make_response(409, {"error": "conflict body"})
        mock_post.return_value = response

        make_client().submit_result(7, COMMIT_SHA, make_result())

        response.json.assert_not_called()


class TestSubmitResultFailures:
    def test_401_raises_and_logs_status_only(self, mock_post, caplog):
        response = make_response(401)
        mock_post.return_value = response

        with caplog.at_level(
            logging.ERROR, logger="codesentinel-ai.java_client"
        ):
            with pytest.raises(httpx.HTTPStatusError):
                make_client().submit_result(7, COMMIT_SHA, make_result())

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "http_status=401" in log_text
        assert TOKEN not in log_text
        response.json.assert_not_called()

    def test_422_raises(self, mock_post):
        mock_post.return_value = make_response(
            422, {"error": "findings[0] field validation failed"}
        )

        with pytest.raises(httpx.HTTPStatusError):
            make_client().submit_result(7, COMMIT_SHA, make_result())

    def test_500_raises_and_never_logs_response_body(
        self, mock_post, caplog
    ):
        body_sentinel = "SENTINEL-RESPONSE-BODY-DO-NOT-LOG"
        response = make_response(500, {"error": body_sentinel})
        mock_post.return_value = response

        with caplog.at_level(
            logging.ERROR, logger="codesentinel-ai.java_client"
        ):
            with pytest.raises(httpx.HTTPStatusError):
                make_client().submit_result(7, COMMIT_SHA, make_result())

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "http_status=500" in log_text
        assert body_sentinel not in log_text
        response.json.assert_not_called()

    def test_unexpected_2xx_status_raises(self, mock_post):
        mock_post.return_value = make_response(201)

        with pytest.raises(RuntimeError):
            make_client().submit_result(7, COMMIT_SHA, make_result())

    @pytest.mark.parametrize(
        "error",
        [
            httpx.ConnectError("SENTINEL-NETWORK-DETAIL"),
            httpx.TimeoutException("SENTINEL-NETWORK-DETAIL"),
        ],
        ids=["connect_error", "timeout"],
    )
    def test_network_errors_raise_and_log_type_only(
        self, mock_post, caplog, error
    ):
        mock_post.side_effect = error

        with caplog.at_level(
            logging.ERROR, logger="codesentinel-ai.java_client"
        ):
            with pytest.raises(type(error)):
                make_client().submit_result(7, COMMIT_SHA, make_result())

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert type(error).__name__ in log_text
        assert "SENTINEL-NETWORK-DETAIL" not in log_text
        assert TOKEN not in log_text


class TestSubmitResultTokenSafety:
    @pytest.mark.parametrize("token", ["", "   "], ids=["missing", "blank"])
    def test_missing_token_fails_safely_without_request(
        self, mock_post, caplog, token
    ):
        client = make_client(internal_token=token)

        with caplog.at_level(
            logging.ERROR, logger="codesentinel-ai.java_client"
        ):
            with pytest.raises(ResultSubmitConfigurationError):
                client.submit_result(7, COMMIT_SHA, make_result())

        mock_post.assert_not_called()
        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "not configured" in log_text

    def test_token_never_logged_on_success(self, mock_post, caplog):
        mock_post.return_value = make_response(
            202,
            {"task_id": 7, "duplicate": False, "publish_status": "PENDING"},
        )

        with caplog.at_level(
            logging.INFO, logger="codesentinel-ai.java_client"
        ):
            make_client().submit_result(7, COMMIT_SHA, make_result())

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "Submitted review result" in log_text
        assert TOKEN not in log_text