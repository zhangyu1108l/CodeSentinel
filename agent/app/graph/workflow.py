"""Minimal LangGraph review workflow (Phase 8.1) with a shared budget
context (Phase 8.2).

One serial node calls the existing ReviewService and returns its
ReviewTaskResult unchanged. The graph creates exactly one
ReviewBudgetContext per run and passes its RequestBudget into
ReviewService, so ReviewService keeps owning the context and LLM caps
while every future node shares the remaining time of the same review
instead of a fresh deadline. The graph adds no second LLM call, no new
timeout default and no retry policy; splitting one budget across several
LLM-calling nodes is an explicit later task.

Failure handling: nodes map outcomes onto explicit ReviewGraphStatus
values (COMPLETED, RECOVERABLE_ERROR, UNRECOVERABLE_ERROR,
BUDGET_EXHAUSTED) and record only exception type names; ReviewWorkflow
re-raises sanitized errors so callers keep a predictable failure path
without leaking exception messages.
"""

import asyncio
import logging

from langgraph.graph import END, START, StateGraph

from app.graph.budget import NodeBudgetExhaustedError, ReviewBudgetContext
from app.graph.state import ReviewGraphStatus, ReviewGraphState
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.request_budget import ReviewBudgetExceededError
from app.services.review_service import ReviewService

logger = logging.getLogger("codesentinel-ai.review_workflow")

REVIEW_NODE = "review"


class WorkflowExecutionError(Exception):
    """The review graph finished without a usable result."""


class WorkflowBudgetExhaustedError(WorkflowExecutionError):
    """The shared review budget was exhausted before a result existed."""


def create_review_graph(review_service: ReviewService):
    """Build and compile the single-node review graph."""

    async def review_node(state: ReviewGraphState) -> ReviewGraphState:
        context = state.get("budget")
        if context is None:
            logger.warning("Review node started without a budget context")
            return {
                "result": None,
                "status": ReviewGraphStatus.UNRECOVERABLE_ERROR,
                "error": "MissingBudgetContext",
            }

        try:
            timeout = context.start_node(context.total_seconds)
        except NodeBudgetExhaustedError as error:
            logger.warning(
                "Review node skipped for task %s: budget exhausted",
                getattr(state.get("request"), "task_id", "?"),
            )
            return {
                "result": None,
                "status": ReviewGraphStatus.BUDGET_EXHAUSTED,
                "error": type(error).__name__,
                "completed_nodes": list(
                    state.get("completed_nodes", [])
                ),
            }

        request = state["request"]
        try:
            async with asyncio.timeout(timeout):
                result = await review_service.review(
                    request, budget=context.budget
                )
        except ReviewBudgetExceededError as error:
            logger.warning(
                "Review node budget exhausted for task %s",
                getattr(request, "task_id", "?"),
            )
            return {
                "result": None,
                "status": ReviewGraphStatus.BUDGET_EXHAUSTED,
                "error": type(error).__name__,
                "completed_nodes": _completed_with(state, REVIEW_NODE),
            }
        except TimeoutError as error:
            status = (
                ReviewGraphStatus.BUDGET_EXHAUSTED
                if context.expired()
                else ReviewGraphStatus.UNRECOVERABLE_ERROR
            )
            return {
                "result": None,
                "status": status,
                "error": type(error).__name__,
                "completed_nodes": _completed_with(state, REVIEW_NODE),
            }
        except Exception as error:
            logger.warning(
                "Review node failed for task %s: %s",
                getattr(request, "task_id", "?"),
                type(error).__name__,
            )
            return {
                "result": None,
                "status": ReviewGraphStatus.UNRECOVERABLE_ERROR,
                "error": type(error).__name__,
                "completed_nodes": _completed_with(state, REVIEW_NODE),
            }

        status = (
            ReviewGraphStatus.RECOVERABLE_ERROR
            if result.status == "DEGRADED"
            else ReviewGraphStatus.COMPLETED
        )
        return {
            "result": result,
            "status": status,
            "error": None,
            "completed_nodes": _completed_with(state, REVIEW_NODE),
        }

    graph = StateGraph(ReviewGraphState)
    graph.add_node(REVIEW_NODE, review_node)
    graph.add_edge(START, REVIEW_NODE)
    graph.add_edge(REVIEW_NODE, END)
    return graph.compile()


def _completed_with(
    state: ReviewGraphState, node_id: str
) -> list[str]:
    completed = list(state.get("completed_nodes", []))
    if node_id not in completed:
        completed.append(node_id)
    return completed


class ReviewWorkflow:
    """Runs the compiled review graph with one shared budget per run."""

    def __init__(
        self,
        review_service: ReviewService = None,
        budget_seconds: float = None,
        budget_clock=None,
    ):
        self.review_service = review_service or ReviewService()
        self._budget_seconds = budget_seconds
        self._budget_clock = budget_clock
        self.graph = create_review_graph(self.review_service)

    def new_budget_context(self) -> ReviewBudgetContext:
        """One fresh shared budget for one run of this workflow."""
        return ReviewBudgetContext.create(
            self._budget_seconds, clock=self._budget_clock
        )

    async def run(self, request: ReviewTaskRequest) -> ReviewTaskResult:
        context = self.new_budget_context()
        final_state = await self.graph.ainvoke(
            {
                "request": request,
                "budget": context,
                "status": ReviewGraphStatus.PENDING,
            }
        )
        status = final_state.get("status")
        if status is ReviewGraphStatus.BUDGET_EXHAUSTED:
            raise WorkflowBudgetExhaustedError(
                "review workflow budget exhausted"
            )
        if status is not ReviewGraphStatus.COMPLETED and (
            status is not ReviewGraphStatus.RECOVERABLE_ERROR
        ):
            raise WorkflowExecutionError(
                f"review workflow failed: {final_state.get('error')}"
            )
        result = final_state.get("result")
        if result is None:
            raise WorkflowExecutionError(
                "review workflow produced no result"
            )
        return result