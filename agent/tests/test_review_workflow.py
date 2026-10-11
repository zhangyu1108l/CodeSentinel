"""Tests for the minimal LangGraph review workflow (Phase 8.1)."""

import asyncio

import pytest

from app.graph.workflow import (
    ReviewWorkflow,
    WorkflowExecutionError,
    create_review_graph,
)
from app.llm.exceptions import LLMException
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.review_service import ReviewService


def make_request():
    return ReviewTaskRequest(
        task_id=7,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        files=[],
    )


def make_result():
    return ReviewTaskResult(
        task_id=7,
        status="COMPLETED",
        report={"summary": "ok", "total_findings": 0, "context": {}},
        findings=[],
    )


class FakeReviewService:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else make_result()
        self.error = error
        self.calls = []

    async def review(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class TestReviewWorkflow:
    def test_workflow_returns_review_service_result(self):
        service = FakeReviewService()
        workflow = ReviewWorkflow(review_service=service)

        result = asyncio.run(workflow.run(make_request()))

        assert result is service.result

    def test_single_review_call_per_run(self):
        service = FakeReviewService()
        workflow = ReviewWorkflow(review_service=service)

        request = make_request()
        asyncio.run(workflow.run(request))

        assert len(service.calls) == 1
        assert service.calls[0] is request

    def test_graph_state_carries_request_result_and_no_error(self):
        service = FakeReviewService()
        graph = create_review_graph(service)
        request = make_request()

        state = asyncio.run(graph.ainvoke({"request": request}))

        assert state["request"] is request
        assert state["result"] is service.result
        assert state["error"] is None

    def test_failed_node_records_sanitized_error_state(self):
        service = FakeReviewService(error=LLMException("DeepSeek down"))
        graph = create_review_graph(service)

        state = asyncio.run(graph.ainvoke({"request": make_request()}))

        assert state["result"] is None
        assert state["error"] == "LLMException"

    def test_workflow_failure_is_predictable_and_message_free(self):
        service = FakeReviewService(error=LLMException("DeepSeek down"))
        workflow = ReviewWorkflow(review_service=service)

        with pytest.raises(WorkflowExecutionError) as exc_info:
            asyncio.run(workflow.run(make_request()))

        message = str(exc_info.value)
        assert "LLMException" in message
        assert "DeepSeek down" not in message
        assert exc_info.value.__cause__ is None

    def test_default_service_is_a_review_service(self):
        workflow = ReviewWorkflow()
        assert isinstance(workflow.review_service, ReviewService)