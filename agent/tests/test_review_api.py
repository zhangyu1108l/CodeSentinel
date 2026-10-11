"""Tests for POST /api/reviews with mocked LLM layer."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.review_router import get_review_service
from app.llm.llm_service import LLMService
from app.main import app
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskResult,
    Severity,
)
from app.services.request_budget import RequestBudget
from app.services.review_service import ReviewService

client = TestClient(app)
client_no_raise = TestClient(app, raise_server_exceptions=False)

VALID_FINDING = ReviewFinding(
    category=Category.QUALITY,
    severity=Severity.LOW,
    confidence=0.5,
    rule_id="MOCK-001",
    title="Finding title",
    file_path="src/Main.java",
    start_line=1,
    end_line=1,
    description="description",
    reason="reason",
    suggestion="suggestion",
    references=["MOCK"],
)


def make_request_body(**overrides):
    data = {
        "task_id": 1,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "files": [],
    }
    data.update(overrides)
    return data


def override_service(findings=None, error=None):
    llm = MagicMock(spec=LLMService)
    if error is not None:
        llm.generate_findings = AsyncMock(side_effect=error)
    else:
        llm.generate_findings = AsyncMock(return_value=findings or [])
    service = ReviewService(llm_service=llm)
    app.dependency_overrides[get_review_service] = lambda: service


def test_valid_request_returns_200():
    override_service(findings=[VALID_FINDING])
    try:
        response = client.post("/api/reviews", json=make_request_body())
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_response_is_review_task_result():
    override_service(findings=[VALID_FINDING])
    try:
        response = client.post(
            "/api/reviews", json=make_request_body(task_id=99)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == 99
        assert data["status"] == "COMPLETED"
        assert isinstance(data["report"], dict)
        assert isinstance(data["findings"], list)
    finally:
        app.dependency_overrides.clear()


def test_empty_findings_when_llm_returns_none():
    override_service(findings=[])
    try:
        response = client.post("/api/reviews", json=make_request_body())
        assert response.status_code == 200
        assert response.json()["findings"] == []
        assert response.json()["report"]["total_findings"] == 0
    finally:
        app.dependency_overrides.clear()


def test_finding_fields_complete():
    override_service(findings=[VALID_FINDING])
    try:
        response = client.post("/api/reviews", json=make_request_body())
        finding = response.json()["findings"][0]
        for field in (
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
        ):
            assert field in finding
        assert finding["category"] == "QUALITY"
        assert finding["severity"] == "LOW"
        assert 0 <= finding["confidence"] <= 1
    finally:
        app.dependency_overrides.clear()


def test_llm_failure_returns_500():
    from app.llm.exceptions import LLMException

    override_service(error=LLMException("DeepSeek API error: HTTP 500"))
    try:
        response = client_no_raise.post(
            "/api/reviews", json=make_request_body()
        )
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


def test_missing_task_id_returns_422():
    data = make_request_body()
    del data["task_id"]
    response = client.post("/api/reviews", json=data)
    assert response.status_code == 422


def test_missing_repository_returns_422():
    data = make_request_body()
    del data["repository"]
    response = client.post("/api/reviews", json=data)
    assert response.status_code == 422


def test_health_still_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def make_result(status="COMPLETED"):
    return ReviewTaskResult(
        task_id=1,
        status=status,
        report={"summary": "ok", "total_findings": 0, "context": {}},
        findings=[],
    )


def override_service_mock(result):
    service = MagicMock(spec=ReviewService)
    service.review = AsyncMock(return_value=result)
    app.dependency_overrides[get_review_service] = lambda: service
    return service


def test_review_service_is_called_once_with_a_shared_budget():
    service = override_service_mock(make_result())
    try:
        response = client.post("/api/reviews", json=make_request_body())

        assert response.status_code == 200
        assert service.review.await_count == 1
        budget = service.review.call_args.kwargs.get("budget")
        assert isinstance(budget, RequestBudget)
    finally:
        app.dependency_overrides.clear()


def test_degraded_result_is_returned_with_200():
    service = override_service_mock(
        make_result(status="DEGRADED")
    )
    try:
        response = client.post("/api/reviews", json=make_request_body())

        assert response.status_code == 200
        assert response.json()["status"] == "DEGRADED"
        assert service.review.await_count == 1
    finally:
        app.dependency_overrides.clear()


def test_review_workflow_dependency_builds_a_workflow():
    from app.api.review_router import get_review_workflow
    from app.graph.workflow import ReviewWorkflow

    llm = MagicMock(spec=LLMService)
    workflow = get_review_workflow(
        ReviewService(llm_service=llm)
    )

    assert isinstance(workflow, ReviewWorkflow)
