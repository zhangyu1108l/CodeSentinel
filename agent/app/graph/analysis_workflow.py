"""Planner driven analysis workflow (Phase 8.3).

Graph: START -> planner -> (conditional) -> bug -> (conditional) -> END.

- The planner produces a whitelist constrained AnalysisPlan
  (app.schemas.plan): only code-defined Category values, no extra fields,
  no executable content.
- Routing uses the pure helpers in app.graph.routing; a planned agent
  without an implementation is recorded in skipped_agents instead of
  being faked.
- Every node shares one ReviewBudgetContext (Phase 8.2): the node timeout
  and the LLM call timeout both come from the remaining time of the same
  review. LLM calls are bounded: one planner call plus at most one call
  per implemented planned agent; there are no retries.
"""

import asyncio
import logging
from collections.abc import Mapping

from langgraph.graph import START, StateGraph
from pydantic import BaseModel, Field

from app.agents.finding_agent import FindingAgent
from app.agents.planner import PlannerAgent
from app.config.settings import settings
from app.graph.budget import NodeBudgetExhaustedError, ReviewBudgetContext
from app.graph.routing import route_next
from app.graph.state import (
    AnalysisGraphState,
    ReviewGraphState,
    ReviewGraphStatus,
)
from app.graph.workflow import (
    WorkflowBudgetExhaustedError,
    WorkflowExecutionError,
)
from app.schemas.plan import AnalysisPlan
from app.schemas.review import Category, ReviewFinding, ReviewTaskRequest
from app.services.request_budget import ReviewBudgetExceededError

logger = logging.getLogger("codesentinel-ai.analysis_workflow")

PLANNER_NODE = "planner"
BUG_NODE = "bug"

AGENT_NODES: dict[Category, str] = {Category.BUG: BUG_NODE}

# Local caps derived from existing configuration; every cap is further
# limited by the shared remaining budget at run time.
PLANNER_NODE_TIME_CAP_SECONDS = settings.REVIEW_TOTAL_BUDGET
PLANNER_LLM_CALL_CAP_SECONDS = settings.DEEPSEEK_TIMEOUT
AGENT_NODE_TIME_CAP_SECONDS = settings.REVIEW_TOTAL_BUDGET
AGENT_LLM_CALL_CAP_SECONDS = settings.DEEPSEEK_TIMEOUT

PENDING = ReviewGraphStatus.PENDING
COMPLETED = ReviewGraphStatus.COMPLETED
RECOVERABLE = ReviewGraphStatus.RECOVERABLE_ERROR
UNRECOVERABLE = ReviewGraphStatus.UNRECOVERABLE_ERROR
BUDGET_EXHAUSTED = ReviewGraphStatus.BUDGET_EXHAUSTED


class AnalysisResult(BaseModel):
    """Outcome of one analysis workflow run (internal graph contract)."""

    plan: AnalysisPlan | None = None
    findings: list[ReviewFinding] = Field(default_factory=list)
    skipped_agents: list[Category] = Field(default_factory=list)
    recoverable_errors: list[str] = Field(default_factory=list)


def _completed_with(state: ReviewGraphState, node_id: str) -> list[str]:
    completed = list(state.get("completed_nodes", []))
    if node_id not in completed:
        completed.append(node_id)
    return completed


def _status_after_agent(
    state: ReviewGraphState, node_id: str
) -> ReviewGraphStatus:
    if state.get("status") is RECOVERABLE:
        return RECOVERABLE
    planned = set(state.get("planned_nodes", []))
    completed = set(_completed_with(state, node_id))
    if planned and not planned.issubset(completed):
        return PENDING
    return COMPLETED


def _stop_state(
    state: ReviewGraphState,
    node_id: str,
    status: ReviewGraphStatus,
    error_name: str,
) -> AnalysisGraphState:
    return {
        "status": status,
        "error": error_name,
        "completed_nodes": _completed_with(state, node_id),
    }


def _recoverable_state(
    state: ReviewGraphState, node_id: str, error_name: str
) -> AnalysisGraphState:
    return {
        "status": RECOVERABLE,
        "error": error_name,
        "recoverable_errors": list(
            state.get("recoverable_errors", [])
        )
        + [error_name],
        "completed_nodes": _completed_with(state, node_id),
    }


def _build_planner_node(planner_agent: PlannerAgent):
    async def planner_node(state: AnalysisGraphState) -> AnalysisGraphState:
        context = state.get("budget")
        if context is None:
            return _stop_state(
                state, PLANNER_NODE, UNRECOVERABLE, "MissingBudgetContext"
            )

        request = state["request"]
        try:
            node_timeout = context.start_node(PLANNER_NODE_TIME_CAP_SECONDS)
        except NodeBudgetExhaustedError as error:
            logger.warning(
                "Planner skipped for task %s: budget exhausted",
                getattr(request, "task_id", "?"),
            )
            return _stop_state(
                state, PLANNER_NODE, BUDGET_EXHAUSTED, type(error).__name__
            )

        try:
            async with asyncio.timeout(node_timeout):
                async with asyncio.timeout(
                    context.llm_timeout(PLANNER_LLM_CALL_CAP_SECONDS)
                ):
                    plan = await planner_agent.plan(request)
        except ReviewBudgetExceededError as error:
            return _stop_state(
                state, PLANNER_NODE, BUDGET_EXHAUSTED, type(error).__name__
            )
        except TimeoutError:
            if context.expired():
                return _stop_state(
                    state, PLANNER_NODE, BUDGET_EXHAUSTED, "TimeoutError"
                )
            return _stop_state(
                state, PLANNER_NODE, UNRECOVERABLE, "TimeoutError"
            )
        except Exception as error:
            logger.warning(
                "Planner failed for task %s: %s",
                getattr(request, "task_id", "?"),
                type(error).__name__,
            )
            return _stop_state(
                state,
                PLANNER_NODE,
                UNRECOVERABLE,
                type(error).__name__,
            )

        skipped = list(state.get("skipped_agents", []))
        planned_nodes: list[str] = []
        for agent_category in plan.agents:
            node_id = AGENT_NODES.get(agent_category)
            if node_id is None:
                skipped.append(agent_category)
            elif node_id not in planned_nodes:
                planned_nodes.append(node_id)
        logger.info(
            "Planner selected %d agent node(s), skipped=%d",
            len(planned_nodes),
            len(skipped),
        )
        return {
            "plan": plan,
            "planned_nodes": planned_nodes,
            "skipped_agents": skipped,
            "findings": list(state.get("findings", [])),
            "status": COMPLETED if not planned_nodes else PENDING,
            "error": None,
            "completed_nodes": _completed_with(state, PLANNER_NODE),
        }

    return planner_node


def _build_finding_node(node_id: str, agent: FindingAgent):
    async def finding_node(state: AnalysisGraphState) -> AnalysisGraphState:
        context = state.get("budget")
        if context is None:
            return _stop_state(
                state, node_id, UNRECOVERABLE, "MissingBudgetContext"
            )

        request = state["request"]
        try:
            node_timeout = context.start_node(AGENT_NODE_TIME_CAP_SECONDS)
        except NodeBudgetExhaustedError as error:
            logger.warning(
                "Analysis node %s skipped: budget exhausted", node_id
            )
            return _stop_state(
                state, node_id, BUDGET_EXHAUSTED, type(error).__name__
            )

        try:
            async with asyncio.timeout(node_timeout):
                async with asyncio.timeout(
                    context.llm_timeout(AGENT_LLM_CALL_CAP_SECONDS)
                ):
                    findings = await agent.analyze(request)
        except ReviewBudgetExceededError as error:
            return _stop_state(
                state, node_id, BUDGET_EXHAUSTED, type(error).__name__
            )
        except TimeoutError:
            if context.expired():
                return _stop_state(
                    state, node_id, BUDGET_EXHAUSTED, "TimeoutError"
                )
            return _recoverable_state(state, node_id, "TimeoutError")
        except Exception as error:
            logger.warning(
                "Analysis node %s failed for task %s: %s",
                node_id,
                getattr(request, "task_id", "?"),
                type(error).__name__,
            )
            return _recoverable_state(
                state, node_id, type(error).__name__
            )

        return {
            "findings": list(state.get("findings", [])) + list(findings),
            "status": _status_after_agent(state, node_id),
            "error": None,
            "completed_nodes": _completed_with(state, node_id),
        }

    return finding_node


def create_analysis_graph(
    planner_agent: PlannerAgent,
    finding_agents: Mapping[str, FindingAgent],
):
    """Build and compile the planner driven analysis graph."""
    graph = StateGraph(AnalysisGraphState)
    graph.add_node(PLANNER_NODE, _build_planner_node(planner_agent))
    for node_id, agent in finding_agents.items():
        graph.add_node(node_id, _build_finding_node(node_id, agent))

    graph.add_edge(START, PLANNER_NODE)
    graph.add_conditional_edges(PLANNER_NODE, route_next)
    for node_id in finding_agents:
        graph.add_conditional_edges(node_id, route_next)
    return graph.compile()


class AnalysisWorkflow:
    """Runs the planner driven graph with one shared budget per run."""

    def __init__(
        self,
        planner_agent: PlannerAgent = None,
        finding_agents: Mapping[str, FindingAgent] = None,
        budget_seconds: float = None,
        budget_clock=None,
    ):
        self.planner_agent = planner_agent or PlannerAgent()
        if finding_agents is None:
            finding_agents = {BUG_NODE: FindingAgent(Category.BUG)}
        self.finding_agents = dict(finding_agents)
        self._budget_seconds = budget_seconds
        self._budget_clock = budget_clock
        self.graph = create_analysis_graph(
            self.planner_agent, self.finding_agents
        )

    def new_budget_context(self) -> ReviewBudgetContext:
        """One fresh shared budget for one run of this workflow."""
        return ReviewBudgetContext.create(
            self._budget_seconds, clock=self._budget_clock
        )

    async def run(self, request: ReviewTaskRequest) -> AnalysisResult:
        context = self.new_budget_context()
        final_state = await self.graph.ainvoke(
            {
                "request": request,
                "budget": context,
                "status": ReviewGraphStatus.PENDING,
                "findings": [],
                "skipped_agents": [],
                "recoverable_errors": [],
                "planned_nodes": [],
                "completed_nodes": [],
            }
        )
        status = final_state.get("status")
        if status is BUDGET_EXHAUSTED:
            raise WorkflowBudgetExhaustedError(
                "analysis workflow budget exhausted"
            )
        if status is not COMPLETED and status is not RECOVERABLE:
            raise WorkflowExecutionError(
                f"analysis workflow failed: {final_state.get('error')}"
            )
        return AnalysisResult(
            plan=final_state.get("plan"),
            findings=list(final_state.get("findings", [])),
            skipped_agents=list(final_state.get("skipped_agents", [])),
            recoverable_errors=list(
                final_state.get("recoverable_errors", [])
            ),
        )