"""Tests for the planner driven analysis workflow (Phase 8.3-8.7).

Fake planner, agents, context stage and LLM layer only: no real LLM, no
network and no tool execution.
"""

import asyncio
import logging

import pytest

from app.agents.context_payload import AgentContextPayload
from app.graph.analysis_context import ContextStageResult
from app.graph.analysis_workflow import (
    BUG_NODE,
    CONTEXT_NODE,
    PLANNER_NODE,
    REPORTER_NODE,
    VALIDATOR_NODE,
    AnalysisResult,
    AnalysisWorkflow,
    create_analysis_graph,
)
from app.graph.budget import ReviewBudgetContext
from app.graph.state import ReviewGraphStatus
from app.graph.workflow import (
    WorkflowBudgetExhaustedError,
    WorkflowExecutionError,
)
from app.llm.exceptions import LLMResponseError
from app.schemas.plan import AnalysisPlan
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)
from app.services.request_budget import RequestBudget


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


def make_finding(category=Category.BUG, file_path="a.py"):
    return ReviewFinding(
        category=category,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id="R1",
        title="title",
        file_path=file_path,
        start_line=1,
        end_line=1,
        description="description",
        reason="reason",
        suggestion="suggestion",
        references=[],
    )


def make_plan(*agents):
    return AnalysisPlan.model_validate(
        {"tasks": [{"agent": agent.value} for agent in agents]}
    )


def make_payload(available=True, paths=None, line_ranges=None):
    return AgentContextPayload(
        available=available,
        reason=None if available else "context_unavailable",
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        code_section="CODE",
        paths=paths if paths is not None else ["a.py"],
        line_ranges=(
            line_ranges if line_ranges is not None else {"a.py": [(1, 10)]}
        ),
    )


class FakePlanner:
    def __init__(self, plan=None, error=None):
        self.plan_value = plan or make_plan(Category.BUG)
        self.error = error
        self.calls = 0

    async def plan(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.plan_value


class FakeFindingAgent:
    def __init__(self, findings=None, error=None):
        self.findings = list(findings or [])
        self.error = error
        self.calls = 0
        self.contexts = []

    async def analyze(self, request, context=None):
        self.calls += 1
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.findings


class FakeContextStage:
    def __init__(
        self,
        payload=None,
        context_report=None,
        static_report=None,
        static_findings=None,
    ):
        self.payload = payload if payload is not None else make_payload()
        self.context_report = context_report or {
            "available": True,
            "degraded": False,
            "reason": None,
            "file_count": 1,
            "files_with_content": 1,
            "estimated_tokens": 1,
            "truncated": False,
        }
        self.static_report = static_report or {
            "available": False,
            "degraded": False,
            "reason": "not_configured",
            "tools_run": [],
            "findings": 0,
        }
        self.static_findings = list(static_findings or [])
        self.calls = 0
        self.budgets = []

    async def prepare(self, request, budget):
        self.calls += 1
        self.budgets.append(budget)
        return ContextStageResult(
            payload=self.payload,
            context_report=dict(self.context_report),
            static_report=dict(self.static_report),
            static_findings=list(self.static_findings),
        )


def make_workflow(
    planner=None,
    finding_agents=None,
    context_stage=None,
    budget_seconds=None,
    **overrides,
):
    planner = planner or FakePlanner()
    if finding_agents is None:
        finding_agents = {BUG_NODE: FakeFindingAgent([make_finding()])}
    context_stage = context_stage or FakeContextStage()
    workflow = AnalysisWorkflow(
        planner_agent=planner,
        finding_agents=finding_agents,
        context_stage=context_stage,
        budget_seconds=budget_seconds,
        **overrides,
    )
    return workflow, planner, finding_agents, context_stage


class TestAnalysisWorkflow:
    def test_bug_plan_runs_full_pipeline(self):
        workflow, planner, agents, stage = make_workflow()

        result = asyncio.run(workflow.run(make_request()))

        assert isinstance(result, AnalysisResult)
        assert [finding.category for finding in result.findings] == [
            Category.BUG
        ]
        assert result.plan is planner.plan_value
        assert result.skipped_agents == []
        assert result.recoverable_errors == []
        assert result.report is not None
        assert result.report.executed_agents == [Category.BUG]
        assert result.report.finding_count == 1
        assert stage.calls == 1
        assert agents[BUG_NODE].calls == 1

    def test_single_llm_call_per_agent(self):
        workflow, planner, agents, stage = make_workflow()

        asyncio.run(workflow.run(make_request()))

        assert planner.calls == 1
        assert agents[BUG_NODE].calls == 1

    def test_agent_receives_payload_and_shared_budget(self):
        workflow, planner, agents, stage = make_workflow()

        asyncio.run(workflow.run(make_request()))

        assert agents[BUG_NODE].contexts[0] is stage.payload
        assert isinstance(stage.budgets[0], RequestBudget)
        assert stage.budgets[0].seconds == 100

    def test_unimplemented_plan_skips_agent_and_returns_empty(self):
        workflow, planner, agent, stage = make_workflow(
            planner=FakePlanner(make_plan(Category.SECURITY))
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.findings == []
        assert result.skipped_agents == [Category.SECURITY]
        assert agent[BUG_NODE].calls == 0
        assert result.report.skipped_agents == [Category.SECURITY]

    def test_mixed_plan_runs_implemented_and_skips_the_rest(self):
        workflow, planner, agents, stage = make_workflow(
            planner=FakePlanner(
                make_plan(Category.SECURITY, Category.BUG)
            )
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.skipped_agents == [Category.SECURITY]
        assert agents[BUG_NODE].calls == 1
        assert len(result.findings) == 1

    def test_planner_failure_is_unrecoverable_and_sanitized(self):
        workflow, planner, agents, stage = make_workflow(
            planner=FakePlanner(error=LLMResponseError("bad plan"))
        )

        with pytest.raises(WorkflowExecutionError) as exc_info:
            asyncio.run(workflow.run(make_request()))

        message = str(exc_info.value)
        assert "LLMResponseError" in message
        assert "bad plan" not in message
        assert agents[BUG_NODE].calls == 0
        assert stage.calls == 0

    def test_budget_exhausted_before_planner_stops_run(self):
        workflow, planner, agents, stage = make_workflow(
            budget_seconds=1e-9
        )

        with pytest.raises(WorkflowBudgetExhaustedError):
            asyncio.run(workflow.run(make_request()))

        assert planner.calls == 0
        assert agents[BUG_NODE].calls == 0
        assert stage.calls == 0

    def test_agent_failure_is_recoverable_and_does_not_raise(self):
        workflow, planner, agents, stage = make_workflow(
            finding_agents={
                BUG_NODE: FakeFindingAgent(error=RuntimeError("boom"))
            }
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.findings == []
        assert result.recoverable_errors == ["RuntimeError"]
        assert result.report.degraded is True
        assert result.report.failed_agents == [Category.BUG]

    def test_agent_timeout_is_recoverable_when_budget_remains(self):
        workflow, planner, agents, stage = make_workflow(
            finding_agents={
                BUG_NODE: FakeFindingAgent(
                    error=asyncio.TimeoutError()
                )
            }
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.report.failed_agents == [Category.BUG]
        assert "TimeoutError" in result.recoverable_errors

    def test_result_keeps_plan_when_all_agents_are_skipped(self):
        workflow, planner, agent, stage = make_workflow(
            planner=FakePlanner(make_plan(Category.QUALITY))
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.plan.agents == [Category.QUALITY]
        assert result.skipped_agents == [Category.QUALITY]

    def test_graph_state_exposes_full_pipeline(self):
        planner = FakePlanner()
        agent = FakeFindingAgent([make_finding()])
        stage = FakeContextStage()
        graph = create_analysis_graph(
            planner, {BUG_NODE: agent}, context_stage=stage
        )
        context = ReviewBudgetContext.create(seconds=5)

        state = asyncio.run(
            graph.ainvoke(
                {
                    "request": make_request(),
                    "budget": context,
                    "status": ReviewGraphStatus.PENDING,
                    "findings": [],
                    "skipped_agents": [],
                    "recoverable_errors": [],
                    "planned_nodes": [],
                    "completed_nodes": [],
                }
            )
        )

        assert state["status"] is ReviewGraphStatus.COMPLETED
        assert state["completed_nodes"] == [
            PLANNER_NODE,
            CONTEXT_NODE,
            BUG_NODE,
            VALIDATOR_NODE,
            REPORTER_NODE,
        ]
        assert [finding.category for finding in state["findings"]] == [
            Category.BUG
        ]
        assert state["report"] is not None
        assert state["report"].finding_count == 1

    def test_allowances_are_logged_from_the_shared_budget(self, caplog):
        caplog.set_level(logging.DEBUG)
        workflow, planner, agents, stage = make_workflow(
            budget_seconds=100, budget_clock=lambda: 0.0
        )

        asyncio.run(workflow.run(make_request()))

        assert (
            "node=planner stages_left=2 allowance=50.0s" in caplog.text
        )
        assert "node=bug stages_left=1 allowance=60.0s" in caplog.text

    def test_budget_exhausted_mid_run_stops_without_results(self):
        class SlowContextStage(FakeContextStage):
            async def prepare(self, request, budget):
                self.calls += 1
                self.budgets.append(budget)
                await asyncio.sleep(0.2)
                return await super().prepare(request, budget)

        stage = SlowContextStage()
        workflow, planner, agents, _ = make_workflow(
            context_stage=stage, budget_seconds=0.1
        )

        with pytest.raises(WorkflowBudgetExhaustedError):
            asyncio.run(workflow.run(make_request()))

        assert agents[BUG_NODE].calls == 0