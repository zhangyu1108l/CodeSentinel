"""Tests for the minimal LangGraph review workflow (Phase 8.1/8.2)."""

import asyncio

import pytest

from app.graph.budget import ReviewBudgetContext
from app.graph.state import ReviewGraphStatus
from app.graph.workflow import (
    ReviewWorkflow,
    WorkflowBudgetExhaustedError,
    WorkflowExecutionError,
    create_review_graph,
)
from app.llm.exceptions import LLMException
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.request_budget import (
    RequestBudget,
    ReviewBudgetExceededError,
)
from app.services.review_service import ReviewService


def make_request():
    return ReviewTaskRequest(
        task_id=7,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        files=[],
    )


def make_result(status="COMPLETED"):
    return ReviewTaskResult(
        task_id=7,
        status=status,
        report={"summary": "ok", "total_findings": 0, "context": {}},
        findings=[],
    )


class FakeReviewService:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else make_result()
        self.error = error
        self.calls = []
        self.budgets = []

    async def review(self, request, budget=None):
        self.calls.append(request)
        self.budgets.append(budget)
        if self.error is not None:
            raise self.error
        return self.result


def run_graph(service, budget_seconds=None):
    graph = create_review_graph(service)
    context = ReviewBudgetContext.create(seconds=budget_seconds)
    state = asyncio.run(
        graph.ainvoke(
            {
                "request": make_request(),
                "budget": context,
                "status": ReviewGraphStatus.PENDING,
            }
        )
    )
    return state, context


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

    def test_each_run_creates_one_fresh_shared_budget(self):
        service = FakeReviewService()
        workflow = ReviewWorkflow(review_service=service, budget_seconds=5)

        asyncio.run(workflow.run(make_request()))
        asyncio.run(workflow.run(make_request()))

        assert len(service.budgets) == 2
        assert service.budgets[0] is not service.budgets[1]
        for budget in service.budgets:
            assert isinstance(budget, RequestBudget)
            assert budget.seconds == 5

    def test_graph_passes_the_shared_budget_instance_to_service(self):
        service = FakeReviewService()

        state, context = run_graph(service, budget_seconds=9)

        assert service.budgets[0] is context.budget
        assert state["status"] is ReviewGraphStatus.COMPLETED

    def test_graph_state_carries_request_result_and_status(self):
        service = FakeReviewService()

        state, context = run_graph(service)

        assert state["request"].task_id == 7
        assert state["result"] is service.result
        assert state["status"] is ReviewGraphStatus.COMPLETED
        assert state["error"] is None
        assert state["completed_nodes"] == ["review"]

    def test_degraded_result_maps_to_recoverable_status(self):
        service = FakeReviewService(result=make_result(status="DEGRADED"))

        state, _ = run_graph(service)

        assert state["status"] is ReviewGraphStatus.RECOVERABLE_ERROR
        assert state["result"] is service.result

    def test_workflow_returns_degraded_result_without_raising(self):
        service = FakeReviewService(result=make_result(status="DEGRADED"))
        workflow = ReviewWorkflow(review_service=service)

        result = asyncio.run(workflow.run(make_request()))

        assert result is service.result

    def test_failed_node_records_unrecoverable_status(self):
        service = FakeReviewService(error=LLMException("DeepSeek down"))

        state, _ = run_graph(service)

        assert state["result"] is None
        assert state["status"] is ReviewGraphStatus.UNRECOVERABLE_ERROR
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

    def test_budget_exceeded_error_maps_to_budget_status(self):
        service = FakeReviewService(
            error=ReviewBudgetExceededError("spent")
        )

        state, _ = run_graph(service)

        assert state["result"] is None
        assert state["status"] is ReviewGraphStatus.BUDGET_EXHAUSTED
        assert state["error"] == "ReviewBudgetExceededError"

    def test_budget_exhausted_before_node_skips_the_service(self):
        service = FakeReviewService()

        state, _ = run_graph(service, budget_seconds=1e-9)

        assert state["status"] is ReviewGraphStatus.BUDGET_EXHAUSTED
        assert state["result"] is None
        assert service.calls == []

    def test_workflow_raises_dedicated_error_when_budget_exhausted(self):
        service = FakeReviewService(
            error=ReviewBudgetExceededError("spent")
        )
        workflow = ReviewWorkflow(review_service=service)

        with pytest.raises(WorkflowBudgetExhaustedError):
            asyncio.run(workflow.run(make_request()))

    def test_missing_budget_context_is_unrecoverable(self):
        service = FakeReviewService()
        graph = create_review_graph(service)

        state = asyncio.run(graph.ainvoke({"request": make_request()}))

        assert state["status"] is ReviewGraphStatus.UNRECOVERABLE_ERROR
        assert state["error"] == "MissingBudgetContext"
        assert service.calls == []

    def test_default_service_is_a_review_service(self):
        workflow = ReviewWorkflow()
        assert isinstance(workflow.review_service, ReviewService)