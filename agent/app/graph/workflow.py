"""Minimal LangGraph review workflow (Phase 8.1).

A single serial node calls the existing ReviewService and returns its
ReviewTaskResult unchanged. Budgeting stays exactly where it already is:
ReviewService owns the request budget (context and LLM stages), and the
graph adds no second LLM call, no new timeout and no retry policy.
Splitting one budget across multiple nodes is an explicit later task.

Failure handling: the node records only the exception type name in the
state, and ReviewWorkflow.run re-raises a sanitized
WorkflowExecutionError so callers keep a predictable failure path
without leaking exception messages (which can embed input previews).
"""

import logging

from langgraph.graph import END, START, StateGraph

from app.graph.state import ReviewGraphState
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.review_service import ReviewService

logger = logging.getLogger("codesentinel-ai.review_workflow")

REVIEW_NODE = "review"


class WorkflowExecutionError(Exception):
    """The review graph finished without a result."""


def create_review_graph(review_service: ReviewService):
    """Build and compile the single-node review graph."""

    async def review_node(state: ReviewGraphState) -> ReviewGraphState:
        request = state["request"]
        try:
            result = await review_service.review(request)
        except Exception as error:
            logger.warning(
                "Review node failed for task %s: %s",
                getattr(request, "task_id", "?"),
                type(error).__name__,
            )
            return {"result": None, "error": type(error).__name__}
        return {"result": result, "error": None}

    graph = StateGraph(ReviewGraphState)
    graph.add_node(REVIEW_NODE, review_node)
    graph.add_edge(START, REVIEW_NODE)
    graph.add_edge(REVIEW_NODE, END)
    return graph.compile()


class ReviewWorkflow:
    """Runs the compiled review graph for one request."""

    def __init__(self, review_service: ReviewService = None):
        self.review_service = review_service or ReviewService()
        self.graph = create_review_graph(self.review_service)

    async def run(self, request: ReviewTaskRequest) -> ReviewTaskResult:
        final_state = await self.graph.ainvoke({"request": request})
        error = final_state.get("error")
        if error is not None:
            raise WorkflowExecutionError(
                f"review workflow failed: {error}"
            )
        result = final_state.get("result")
        if result is None:
            raise WorkflowExecutionError(
                "review workflow produced no result"
            )
        return result