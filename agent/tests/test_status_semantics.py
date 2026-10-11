"""Table driven status semantics tests (Phase 8.8).

One table covers the production HTTP contract of `/api/reviews` and one
covers the worker reaction to it. Both are derived from the current code,
not from new policy:

- COMPLETED -> HTTP 200; worker marks the task COMPLETED.
- DEGRADED  -> HTTP 200; worker marks the task COMPLETED (degrades are
  not failures by current design).
- LLM failure or budget exhaustion -> HTTP 500; worker reports failure
  and Java decides retry / FAILED (retry_count < maxRetries re-enqueues).
- invalid request body -> HTTP 422, no service call.

Ambiguity recorded (not changed here): in the production ReviewService a
degraded static analysis stage does not change ReviewTaskResult.status;
that behaviour is tested in test_review_service_static_analysis.py and
flagged in DEVELOPMENT_STATUS.md as a decision needed before switching.
"""

import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from redis import Redis

from app.api.review_router import get_review_service
from app.llm.exceptions import LLMException
from app.main import app
from app.schemas.review import ReviewTaskResult
from app.services.request_budget import ReviewBudgetExceededError
from app.worker.consumer import RedisTaskConsumer
from app.worker.handler import TaskHandler
from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage
from app.worker.ai_client import AiServiceClient

client = TestClient(app)
client_no_raise = TestClient(app, raise_server_exceptions=False)

QUEUE_KEY = "codesentinel:review:tasks"

REQUEST_BODY = {
    "task_id": 1,
    "repository": "owner/repo",
    "pr_number": 42,
    "commit_sha": "abc123",
    "files": [],
}


def make_result(status="COMPLETED"):
    return ReviewTaskResult(
        task_id=1,
        status=status,
        report={"summary": "ok", "total_findings": 0, "context": {}},
        findings=[],
    )


def override_service(result=None, error=None):
    service = MagicMock()
    if error is not None:
        service.review = AsyncMock(side_effect=error)
    else:
        service.review = AsyncMock(
            return_value=result if result is not None else make_result()
        )
    app.dependency_overrides[get_review_service] = lambda: service
    return service


HTTP_CASES = [
    {
        "id": "completed",
        "error": None,
        "result": make_result("COMPLETED"),
        "http_status": 200,
        "body_status": "COMPLETED",
    },
    {
        "id": "degraded",
        "error": None,
        "result": make_result("DEGRADED"),
        "http_status": 200,
        "body_status": "DEGRADED",
    },
    {
        "id": "llm_error",
        "error": LLMException("DeepSeek API error: HTTP 500"),
        "result": None,
        "http_status": 500,
        "body_status": None,
    },
    {
        "id": "budget_exceeded",
        "error": ReviewBudgetExceededError("budget spent"),
        "result": None,
        "http_status": 500,
        "body_status": None,
    },
]


class TestHttpStatusTable:
    @pytest.mark.parametrize("case", HTTP_CASES, ids=lambda c: c["id"])
    def test_status_table(self, case):
        service = override_service(
            result=case["result"], error=case["error"]
        )
        try:
            response = client_no_raise.post(
                "/api/reviews", json=REQUEST_BODY
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == case["http_status"]
        if case["body_status"] is not None:
            assert response.json()["status"] == case["body_status"]
        # Every accepted request runs exactly one review chain.
        assert service.review.await_count == 1

    def test_invalid_request_is_422_without_service_call(self):
        service = override_service()
        try:
            response = client.post(
                "/api/reviews",
                json={"repository": "owner/repo"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 422
        assert service.review.await_count == 0


def make_message_bytes():
    return json.dumps(
        {
            "taskId": 1,
            "owner": "owner",
            "repo": "repo",
            "prNumber": 42,
            "commitSha": "abc123",
        }
    ).encode("utf-8")


def make_mapped_incomplete_result():
    """A mapped result whose mapping was incomplete (Phase 8.9)."""
    from app.agents.reporter import to_review_task_result
    from app.schemas.report import (
        AnalysisFinding,
        AnalysisReport,
        FindingSource,
        ReportStatus,
    )
    from app.schemas.review import Category, Severity

    finding = AnalysisFinding(
        sources=[FindingSource.AGENT],
        category=Category.BUG,
        severity=Severity.HIGH,
        rule_id="R1",
        message="missing title on purpose",
        file_path="a.py",
        start_line=1,
        end_line=1,
    )
    report = AnalysisReport(
        task_id=1,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        status=ReportStatus.COMPLETED,
        degraded=False,
        findings=[finding],
        finding_count=1,
        severity_counts={severity.value: 0 for severity in Severity},
    )
    return to_review_task_result(report)


def make_worker(ai_result=None, ai_error=None):
    java = MagicMock(spec=JavaServiceClient)
    ai = MagicMock(spec=AiServiceClient)
    if ai_error is not None:
        ai.review = MagicMock(side_effect=ai_error)
    else:
        ai.review = MagicMock(
            return_value=ai_result
            if ai_result is not None
            else make_result()
        )
    handler = TaskHandler(java_client=java, ai_client=ai)
    return handler, java, ai


WORKER_CASES = [
    {"id": "completed", "result": make_result("COMPLETED")},
    {"id": "degraded", "result": make_result("DEGRADED")},
]


class TestWorkerStatusTable:
    @pytest.mark.parametrize(
        "case", WORKER_CASES, ids=lambda c: c["id"]
    )
    def test_success_and_degraded_mark_completed(self, case):
        handler, java, ai = make_worker(ai_result=case["result"])
        message = TaskMessage(
            taskId=1,
            owner="owner",
            repo="repo",
            prNumber=42,
            commitSha="abc123",
        )

        handler.handle(message)

        java.mark_running.assert_called_once_with(1)
        java.mark_completed.assert_called_once_with(1)
        java.report_failure.assert_not_called()

    def test_failure_reports_to_java_and_java_decides_retry(self):
        handler, java, ai = make_worker(
            ai_error=LLMException("boom")
        )
        java.report_failure.return_value = {
            "retry": True,
            "taskId": 1,
            "retryCount": 1,
            "status": "PENDING",
        }
        redis = MagicMock(spec=Redis)
        consumer = RedisTaskConsumer(
            redis_client=redis,
            queue_key=QUEUE_KEY,
            handler=handler,
            java_client=java,
        )

        consumer._process_message(make_message_bytes())

        java.mark_completed.assert_not_called()
        java.report_failure.assert_called_once()
        redis.rpush.assert_called_once()

    def test_failure_stops_when_java_exhausts_retries(self):
        handler, java, ai = make_worker(
            ai_error=LLMException("boom")
        )
        java.report_failure.return_value = {
            "retry": False,
            "taskId": 1,
            "retryCount": 3,
            "status": "FAILED",
        }
        redis = MagicMock(spec=Redis)
        consumer = RedisTaskConsumer(
            redis_client=redis,
            queue_key=QUEUE_KEY,
            handler=handler,
            java_client=java,
        )

        consumer._process_message(make_message_bytes())

        java.report_failure.assert_called_once()
        redis.rpush.assert_not_called()

    def test_mapping_incomplete_degraded_result_is_not_retried(self):
        """Decision A/E: DEGRADED from an incomplete mapping completes.

        The worker only treats exceptions / HTTP errors as failures; a
        mapping-incomplete result is marked DEGRADED by the mapper and
        still marks the task COMPLETED.
        """
        mapped = make_mapped_incomplete_result()
        assert mapped.status == "DEGRADED"
        assert mapped.report["mapping_complete"] is False

        handler, java, ai = make_worker(ai_result=mapped)
        message = TaskMessage(
            taskId=1,
            owner="owner",
            repo="repo",
            prNumber=42,
            commitSha="abc123",
        )

        handler.handle(message)

        java.mark_running.assert_called_once_with(1)
        java.mark_completed.assert_called_once_with(1)
        java.report_failure.assert_not_called()