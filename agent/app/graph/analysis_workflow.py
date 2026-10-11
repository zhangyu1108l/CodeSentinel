"""Planner driven multi agent analysis workflow (Phase 8.3-8.7).

Graph (Phase 8.7):

    START -> planner -> context -> (agents in plan order) -> validator
          -> reporter -> END

- The planner produces a whitelist constrained AnalysisPlan
  (app.schemas.plan); a planned category without a runnable node in this
  workflow is recorded in skipped_agents instead of being faked.
- The context node (app.graph.analysis_context) fetches the PR context,
  runs the Phase 8.6 static analysis stage on the same shared budget and
  builds the bounded agent payload; every failure degrades explicitly.
- Agent nodes receive the payload; without a usable payload the real
  agents do not call the LLM and never fabricate findings.
- The validator (app.agents.validator) re-verifies agent findings against
  the payload and validates static findings without requiring LLM style
  fields; the reporter (app.agents.reporter) builds the stable
  AnalysisReport from validated findings and recorded execution facts.

Budget (Phase 8.7 policy, app.graph.allocation):

- one ReviewBudgetContext per run; every node derives its timeout from
  the shared remaining time and no node resets the budget;
- planner allowance = min(local cap, remaining / 2): the planner always
  reserves room for at least one downstream agent;
- agent allowance = min(local cap, remaining / pending agent nodes);
- the context node uses the remaining time, and the static stage applies
  its own share policy internally (at most half of what is left);
- nodes never retry and never run in parallel; running out of budget
  stops the run with BUDGET_EXHAUSTED and never reports success.

Node failure semantics:

- planner failure: UNRECOVERABLE (no plan, the run must fail);
- context failure: RECOVERABLE degraded state (agents then skip without
  an LLM call; the report records the reason);
- agent failure: RECOVERABLE, recorded in failed_agents and
  recoverable_errors;
- validator failure: RECOVERABLE with an explicit validation failure
  record; unvalidated findings are never reported;
- reporter failure: UNRECOVERABLE (there is no report).
"""

import asyncio
import logging
from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agents.finding_agent import FindingAgent
from app.agents.finding_aggregator import aggregate_findings
from app.agents.planner import PlannerAgent
from app.agents.reporter import build_analysis_report
from app.agents.validator import Validator
from app.config.settings import settings
from app.graph.allocation import node_allowance
from app.graph.analysis_context import (
    REASON_CONTEXT_UNAVAILABLE,
    AnalysisContextStage,
    context_report_unavailable,
    static_report_unavailable,
)
from app.graph.budget import NodeBudgetExhaustedError, ReviewBudgetContext
from app.graph.routing import STOP_STATUSES, select_next_node
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
from app.schemas.report import AnalysisReport
from app.schemas.review import Category, ReviewFinding, ReviewTaskRequest
from app.services.request_budget import ReviewBudgetExceededError

logger = logging.getLogger("codesentinel-ai.analysis_workflow")

PLANNER_NODE = "planner"
CONTEXT_NODE = "context"
BUG_NODE = "bug"
SECURITY_NODE = "security"
PERFORMANCE_NODE = "performance"
QUALITY_NODE = "quality"
VALIDATOR_NODE = "validator"
REPORTER_NODE = "reporter"

AGENT_NODES: dict[Category, str] = {
    Category.BUG: BUG_NODE,
    Category.SECURITY: SECURITY_NODE,
    Category.PERFORMANCE: PERFORMANCE_NODE,
    Category.QUALITY: QUALITY_NODE,
}
AGENT_CATEGORIES: dict[str, Category] = {
    node_id: category for category, node_id in AGENT_NODES.items()
}

# The planner reserves room for at least one downstream agent.
PLANNER_RESERVED_STAGES = 2

# Local caps derived from existing configuration; every cap is further
# limited by the shared remaining budget at run time. Planner and agent
# nodes are LLM bound, so their node cap is the LLM timeout cap; the
# context node also fetches and runs tools, so its local cap is the whole
# review budget (its internals apply the stricter shares).
PLANNER_NODE_TIME_CAP_SECONDS = settings.DEEPSEEK_TIMEOUT
PLANNER_LLM_CALL_CAP_SECONDS = settings.DEEPSEEK_TIMEOUT
CONTEXT_NODE_TIME_CAP_SECONDS = settings.REVIEW_TOTAL_BUDGET
AGENT_NODE_TIME_CAP_SECONDS = settings.DEEPSEEK_TIMEOUT
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
    report: AnalysisReport | None = None


def _completed_with(state: ReviewGraphState, node_id: str) -> list[str]:
    completed = list(state.get("completed_nodes", []))
    if node_id not in completed:
        completed.append(node_id)
    return completed


def _status_after_node(
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


def _log_allowance(
    node_id: str, stages_left: int, allowance: float
) -> None:
    logger.debug(
        "node=%s stages_left=%d allowance=%.1fs",
        node_id,
        stages_left,
        allowance,
    )


def _route_after_node(state: ReviewGraphState) -> str:
    """Next planned node, the validator tail, or END on a stop status."""
    if state.get("status") in STOP_STATUSES:
        return END
    next_node = select_next_node(state)
    if next_node is not None:
        return next_node
    return VALIDATOR_NODE


def _build_planner_node(
    planner_agent: PlannerAgent,
    runnable_nodes: Mapping[Category, str],
):
    async def planner_node(state: AnalysisGraphState) -> AnalysisGraphState:
        context = state.get("budget")
        if context is None:
            return _stop_state(
                state, PLANNER_NODE, UNRECOVERABLE, "MissingBudgetContext"
            )

        request = state["request"]
        try:
            context.start_node(PLANNER_NODE_TIME_CAP_SECONDS)
        except NodeBudgetExhaustedError as error:
            logger.warning(
                "Planner skipped for task %s: budget exhausted",
                getattr(request, "task_id", "?"),
            )
            return _stop_state(
                state, PLANNER_NODE, BUDGET_EXHAUSTED, type(error).__name__
            )

        allowance = node_allowance(
            context.remaining(),
            PLANNER_RESERVED_STAGES,
            PLANNER_NODE_TIME_CAP_SECONDS,
        )
        _log_allowance(PLANNER_NODE, PLANNER_RESERVED_STAGES, allowance)
        try:
            async with asyncio.timeout(allowance):
                async with asyncio.timeout(
                    min(PLANNER_LLM_CALL_CAP_SECONDS, allowance)
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
        agent_nodes: list[str] = []
        for agent_category in plan.agents:
            node_id = runnable_nodes.get(agent_category)
            if node_id is None:
                skipped.append(agent_category)
            elif node_id not in agent_nodes:
                agent_nodes.append(node_id)
        planned_nodes = [CONTEXT_NODE] + agent_nodes
        logger.info(
            "Planner selected %d agent node(s), skipped=%d",
            len(agent_nodes),
            len(skipped),
        )
        return {
            "plan": plan,
            "planned_nodes": planned_nodes,
            "skipped_agents": skipped,
            "findings": list(state.get("findings", [])),
            "status": PENDING if planned_nodes else COMPLETED,
            "error": None,
            "completed_nodes": _completed_with(state, PLANNER_NODE),
        }

    return planner_node


def _build_context_node(context_stage: AnalysisContextStage):
    async def context_node(state: AnalysisGraphState) -> AnalysisGraphState:
        context = state.get("budget")
        if context is None:
            return _stop_state(
                state, CONTEXT_NODE, UNRECOVERABLE, "MissingBudgetContext"
            )

        request = state["request"]
        try:
            context.start_node(CONTEXT_NODE_TIME_CAP_SECONDS)
        except NodeBudgetExhaustedError as error:
            logger.warning(
                "Context node skipped for task %s: budget exhausted",
                getattr(request, "task_id", "?"),
            )
            return _stop_state(
                state, CONTEXT_NODE, BUDGET_EXHAUSTED, type(error).__name__
            )

        allowance = node_allowance(
            context.remaining(), 1, CONTEXT_NODE_TIME_CAP_SECONDS
        )
        _log_allowance(CONTEXT_NODE, 1, allowance)
        try:
            async with asyncio.timeout(allowance):
                result = await context_stage.prepare(
                    request, context.budget
                )
        except ReviewBudgetExceededError as error:
            return _stop_state(
                state, CONTEXT_NODE, BUDGET_EXHAUSTED, type(error).__name__
            )
        except TimeoutError:
            if context.expired():
                return _stop_state(
                    state, CONTEXT_NODE, BUDGET_EXHAUSTED, "TimeoutError"
                )
            return _context_degraded_state(state, "TimeoutError")
        except Exception as error:
            logger.warning(
                "Context node failed for task %s: %s",
                getattr(request, "task_id", "?"),
                type(error).__name__,
            )
            return _context_degraded_state(state, type(error).__name__)

        status = (
            RECOVERABLE
            if result.context_report.get("degraded")
            else _status_after_node(state, CONTEXT_NODE)
        )
        return {
            "payload": result.payload,
            "context_report": result.context_report,
            "static_report": result.static_report,
            "static_findings": list(result.static_findings),
            "status": status,
            "error": None,
            "completed_nodes": _completed_with(state, CONTEXT_NODE),
        }

    return context_node


def _context_degraded_state(
    state: ReviewGraphState, reason: str
) -> AnalysisGraphState:
    """Degraded context state that does not claim an agent failure."""
    return {
        "payload": None,
        "context_report": context_report_unavailable(reason, True),
        "static_report": static_report_unavailable(
            REASON_CONTEXT_UNAVAILABLE, degraded=True
        ),
        "static_findings": [],
        "status": RECOVERABLE,
        "error": reason,
        "completed_nodes": _completed_with(state, CONTEXT_NODE),
    }


def _build_finding_node(
    node_id: str, category: Category, agent: FindingAgent
):
    async def finding_node(state: AnalysisGraphState) -> AnalysisGraphState:
        context = state.get("budget")
        if context is None:
            return _stop_state(
                state, node_id, UNRECOVERABLE, "MissingBudgetContext"
            )

        request = state["request"]
        try:
            context.start_node(AGENT_NODE_TIME_CAP_SECONDS)
        except NodeBudgetExhaustedError as error:
            logger.warning(
                "Analysis node %s skipped: budget exhausted", node_id
            )
            return _stop_state(
                state, node_id, BUDGET_EXHAUSTED, type(error).__name__
            )

        completed = set(state.get("completed_nodes", []))
        pending = [
            planned
            for planned in state.get("planned_nodes", [])
            if planned in AGENT_CATEGORIES and planned not in completed
        ]
        stages_left = len(pending) or 1
        allowance = node_allowance(
            context.remaining(), stages_left, AGENT_NODE_TIME_CAP_SECONDS
        )
        _log_allowance(node_id, stages_left, allowance)
        try:
            async with asyncio.timeout(allowance):
                async with asyncio.timeout(
                    min(AGENT_LLM_CALL_CAP_SECONDS, allowance)
                ):
                    findings = await agent.analyze(
                        request, context=state.get("payload")
                    )
        except ReviewBudgetExceededError as error:
            return _stop_state(
                state, node_id, BUDGET_EXHAUSTED, type(error).__name__
            )
        except TimeoutError:
            if context.expired():
                return _stop_state(
                    state, node_id, BUDGET_EXHAUSTED, "TimeoutError"
                )
            return _agent_failed_state(state, node_id, category, "TimeoutError")
        except Exception as error:
            logger.warning(
                "Analysis node %s failed for task %s: %s",
                node_id,
                getattr(request, "task_id", "?"),
                type(error).__name__,
            )
            return _agent_failed_state(
                state, node_id, category, type(error).__name__
            )

        executed = list(state.get("executed_agents", []))
        if category not in executed:
            executed.append(category)
        return {
            "findings": list(state.get("findings", [])) + list(findings),
            "executed_agents": executed,
            "status": _status_after_node(state, node_id),
            "error": None,
            "completed_nodes": _completed_with(state, node_id),
        }

    return finding_node


def _agent_failed_state(
    state: ReviewGraphState,
    node_id: str,
    category: Category,
    error_name: str,
) -> AnalysisGraphState:
    update = _recoverable_state(state, node_id, error_name)
    failed = list(state.get("failed_agents", []))
    if category not in failed:
        failed.append(category)
    update["failed_agents"] = failed
    return update


def _build_validator_node(validator: Validator):
    async def validator_node(state: AnalysisGraphState) -> AnalysisGraphState:
        try:
            outcome = validator.validate(
                state.get("payload"),
                list(state.get("findings", [])),
                list(state.get("static_findings", [])),
            )
        except Exception as error:
            name = type(error).__name__
            logger.warning("Validator failed: %s", name)
            update = _recoverable_state(state, VALIDATOR_NODE, name)
            update.update(
                {
                    "validated_findings": [],
                    "validated_static": [],
                    "validation_summary": {"failed": name},
                }
            )
            return update
        return {
            "validated_findings": list(outcome.findings),
            "validated_static": list(outcome.static_findings),
            "validation_summary": outcome.summary(),
            "status": _status_after_node(state, VALIDATOR_NODE),
            "error": None,
            "completed_nodes": _completed_with(state, VALIDATOR_NODE),
        }

    return validator_node


def _build_reporter_node():
    async def reporter_node(state: AnalysisGraphState) -> AnalysisGraphState:
        try:
            aggregation = aggregate_findings(
                list(state.get("validated_findings", [])),
                list(state.get("validated_static", [])),
            )
            planned_agents = [
                AGENT_CATEGORIES[node_id]
                for node_id in state.get("planned_nodes", [])
                if node_id in AGENT_CATEGORIES
            ]
            report = build_analysis_report(
                request=state["request"],
                findings=aggregation.findings,
                duplicates_merged=aggregation.duplicates_merged,
                source_counts=aggregation.source_counts,
                planned_agents=planned_agents,
                executed_agents=list(state.get("executed_agents", [])),
                failed_agents=list(state.get("failed_agents", [])),
                skipped_agents=list(state.get("skipped_agents", [])),
                recoverable_errors=list(
                    state.get("recoverable_errors", [])
                ),
                context_report=state.get("context_report"),
                static_report=state.get("static_report"),
                validation_summary=state.get("validation_summary"),
            )
        except Exception as error:
            name = type(error).__name__
            logger.warning("Reporter failed: %s", name)
            return _stop_state(
                state, REPORTER_NODE, UNRECOVERABLE, name
            )

        return {
            "report": report,
            "status": RECOVERABLE if report.degraded else COMPLETED,
            "error": None,
            "completed_nodes": _completed_with(state, REPORTER_NODE),
        }

    return reporter_node


def create_analysis_graph(
    planner_agent: PlannerAgent,
    finding_agents: Mapping[str, FindingAgent],
    context_stage: AnalysisContextStage = None,
    validator: Validator = None,
):
    """Build and compile the full analysis graph.

    finding_agents maps node ids (AGENT_CATEGORIES keys) to the agents
    that run in this workflow; any other planned category is recorded as
    skipped instead of being dispatched to a missing node.
    """
    for node_id in finding_agents:
        if node_id not in AGENT_CATEGORIES:
            raise ValueError("unknown agent node id: " + str(node_id))
    context_stage = context_stage or AnalysisContextStage()
    validator = validator or Validator()
    runnable_nodes = {
        category: node_id
        for category, node_id in AGENT_NODES.items()
        if node_id in finding_agents
    }

    graph = StateGraph(AnalysisGraphState)
    graph.add_node(
        PLANNER_NODE, _build_planner_node(planner_agent, runnable_nodes)
    )
    graph.add_node(CONTEXT_NODE, _build_context_node(context_stage))
    for node_id, agent in finding_agents.items():
        graph.add_node(
            node_id,
            _build_finding_node(
                node_id, AGENT_CATEGORIES[node_id], agent
            ),
        )
    graph.add_node(VALIDATOR_NODE, _build_validator_node(validator))
    graph.add_node(REPORTER_NODE, _build_reporter_node())

    targets = {
        CONTEXT_NODE: CONTEXT_NODE,
        VALIDATOR_NODE: VALIDATOR_NODE,
        END: END,
    }
    for node_id in finding_agents:
        targets[node_id] = node_id

    graph.add_edge(START, PLANNER_NODE)
    graph.add_conditional_edges(PLANNER_NODE, _route_after_node, targets)
    graph.add_conditional_edges(CONTEXT_NODE, _route_after_node, targets)
    for node_id in finding_agents:
        graph.add_conditional_edges(
            node_id, _route_after_node, targets
        )
    graph.add_edge(VALIDATOR_NODE, REPORTER_NODE)
    graph.add_edge(REPORTER_NODE, END)
    return graph.compile()


class AnalysisWorkflow:
    """Runs the full analysis graph with one shared budget per run."""

    def __init__(
        self,
        planner_agent: PlannerAgent = None,
        finding_agents: Mapping[str, FindingAgent] = None,
        context_stage: AnalysisContextStage = None,
        validator: Validator = None,
        budget_seconds: float = None,
        budget_clock=None,
    ):
        self.planner_agent = planner_agent or PlannerAgent()
        if finding_agents is None:
            finding_agents = {
                node_id: FindingAgent(category)
                for category, node_id in AGENT_NODES.items()
            }
        self.finding_agents = dict(finding_agents)
        self.context_stage = context_stage or AnalysisContextStage()
        self.validator = validator or Validator()
        self._budget_seconds = budget_seconds
        self._budget_clock = budget_clock
        self.graph = create_analysis_graph(
            self.planner_agent,
            self.finding_agents,
            context_stage=self.context_stage,
            validator=self.validator,
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
                "payload": None,
                "context_report": None,
                "static_report": None,
                "static_findings": [],
                "validated_findings": [],
                "validated_static": [],
                "validation_summary": None,
                "executed_agents": [],
                "failed_agents": [],
                "report": None,
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
            findings=list(final_state.get("validated_findings", [])),
            skipped_agents=list(final_state.get("skipped_agents", [])),
            recoverable_errors=list(
                final_state.get("recoverable_errors", [])
            ),
            report=final_state.get("report"),
        )