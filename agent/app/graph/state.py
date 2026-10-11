"""Graph state for review workflows (Phase 8.1/8.2).

The state carries only the review request, the shared budget context, the
produced result and explicit status / error markers (exception type
names). It deliberately does not carry raw exception objects: graph state
may be logged or serialized by later nodes, and raw validation errors can
embed input previews.

Status contract:

- PENDING: run started, nothing terminal happened yet.
- COMPLETED: a successful result exists.
- RECOVERABLE_ERROR: a result exists but the review degraded (for example
  a DEGRADED ReviewTaskResult); the workflow may continue.
- UNRECOVERABLE_ERROR: no usable result; the workflow must stop.
- BUDGET_EXHAUSTED: the shared budget ran out; the workflow must stop and
  must never report success.
"""

from enum import Enum
from typing import TypedDict

from app.agents.context_payload import AgentContextPayload
from app.graph.budget import ReviewBudgetContext
from app.schemas.plan import AnalysisPlan
from app.schemas.report import AnalysisReport
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    ReviewTaskResult,
)
from app.schemas.static_analysis import StaticAnalysisFinding


class ReviewGraphStatus(str, Enum):
    """Explicit run status shared by every graph node."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    RECOVERABLE_ERROR = "RECOVERABLE_ERROR"
    UNRECOVERABLE_ERROR = "UNRECOVERABLE_ERROR"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ReviewGraphState(TypedDict, total=False):
    """State passed between review workflow nodes.

    request: the review request accepted by the graph entry point.
    budget: the shared ReviewBudgetContext of this run; every node uses
        its remaining time instead of a fresh deadline.
    result: the ReviewTaskResult produced by the review node, or None.
    status: explicit ReviewGraphStatus of the run.
    error: sanitized failure marker (exception type name), None on success.
    completed_nodes: node ids that already ran, in completion order.
    planned_nodes: ordered node ids still to be dispatched (conditional
        routing reads this; 8.1/8.2 leave it empty).
    """

    request: ReviewTaskRequest
    budget: ReviewBudgetContext
    result: ReviewTaskResult | None
    status: ReviewGraphStatus
    error: str | None
    completed_nodes: list[str]
    planned_nodes: list[str]


class AnalysisGraphState(ReviewGraphState, total=False):
    """State of the planner driven analysis workflow (Phase 8.7).

    plan: the whitelist constrained AnalysisPlan produced by the planner.
    findings: raw ReviewFinding values accumulated by the analysis nodes.
    skipped_agents: planned categories without a runnable node.
    recoverable_errors: exception type names of failed analysis nodes
        that did not stop the workflow (their remaining nodes may run).
    payload: the bounded agent context payload built by the context node.
    context_report: safe status summary of the context load.
    static_report: safe status summary of the static analysis stage.
    static_findings: raw static findings kept for the validator.
    validated_findings / validated_static: outputs of the validator,
        consumed by the reporter (no unvalidated finding is reported).
    validation_summary: safe validation counters / reason codes.
    executed_agents / failed_agents: per dimension node outcomes.
    report: the final AnalysisReport produced by the reporter node.
    """

    plan: AnalysisPlan | None
    findings: list[ReviewFinding]
    skipped_agents: list[Category]
    recoverable_errors: list[str]
    payload: AgentContextPayload | None
    context_report: dict | None
    static_report: dict | None
    static_findings: list[StaticAnalysisFinding]
    validated_findings: list[ReviewFinding]
    validated_static: list[StaticAnalysisFinding]
    validation_summary: dict | None
    executed_agents: list[Category]
    failed_agents: list[Category]
    report: AnalysisReport | None