"""Tests for the planner driven analysis workflow (Phase 8.3)."""

import asyncio

import pytest

from app.graph.analysis_workflow import (
    BUG_NODE,
    PLANNER_NODE,
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


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


def make_finding():
    return ReviewFinding(
        category=Category.BUG,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id="R1",
        title="title",
        file_path="a.py",
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

    async def analyze(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.findings


def make_workflow(planner=None, bug_agent=None, budget_seconds=None):
    planner = planner or FakePlanner()
    bug_agent = bug_agent or FakeFindingAgent([make_finding()])
    workflow = AnalysisWorkflow(
        planner_agent=planner,
        finding_agents={BUG_NODE: bug_agent},
        budget_seconds=budget_seconds,
    )
    return workflow, planner, bug_agent


class TestAnalysisWorkflow:
    def test_bug_plan_runs_bug_node_and_returns_findings(self):
        workflow, planner, agent = make_workflow()

        result = asyncio.run(workflow.run(make_request()))

        assert isinstance(result, AnalysisResult)
        assert [finding.category for finding in result.findings] == [
            Category.BUG
        ]
        assert result.plan is planner.plan_value
        assert result.skipped_agents == []
        assert result.recoverable_errors == []

    def test_single_llm_call_per_agent(self):
        workflow, planner, agent = make_workflow()

        asyncio.run(workflow.run(make_request()))

        assert planner.calls == 1
        assert agent.calls == 1

    def test_unimplemented_plan_skips_agent_and_returns_empty(self):
        workflow, planner, agent = make_workflow(
            planner=FakePlanner(make_plan(Category.SECURITY))
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.findings == []
        assert result.skipped_agents == [Category.SECURITY]
        assert agent.calls == 0

    def test_mixed_plan_runs_implemented_and_skips_the_rest(self):
        workflow, planner, agent = make_workflow(
            planner=FakePlanner(
                make_plan(Category.SECURITY, Category.BUG)
            )
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.skipped_agents == [Category.SECURITY]
        assert agent.calls == 1
        assert len(result.findings) == 1

    def test_planner_failure_is_unrecoverable_and_sanitized(self):
        workflow, planner, agent = make_workflow(
            planner=FakePlanner(error=LLMResponseError("bad plan"))
        )

        with pytest.raises(WorkflowExecutionError) as exc_info:
            asyncio.run(workflow.run(make_request()))

        message = str(exc_info.value)
        assert "LLMResponseError" in message
        assert "bad plan" not in message
        assert agent.calls == 0

    def test_budget_exhausted_before_planner_stops_run(self):
        workflow, planner, agent = make_workflow(budget_seconds=1e-9)

        with pytest.raises(WorkflowBudgetExhaustedError):
            asyncio.run(workflow.run(make_request()))

        assert planner.calls == 0
        assert agent.calls == 0

    def test_agent_failure_is_recoverable_and_does_not_raise(self):
        workflow, planner, agent = make_workflow(
            bug_agent=FakeFindingAgent(error=RuntimeError("boom"))
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.findings == []
        assert result.recoverable_errors == ["RuntimeError"]

    def test_result_keeps_plan_when_all_agents_are_skipped(self):
        workflow, planner, agent = make_workflow(
            planner=FakePlanner(make_plan(Category.QUALITY))
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.plan.agents == [Category.QUALITY]
        assert result.skipped_agents == [Category.QUALITY]

    def test_graph_state_exposes_plan_and_completed_status(self):
        planner = FakePlanner()
        agent = FakeFindingAgent([make_finding()])
        graph = create_analysis_graph(planner, {BUG_NODE: agent})
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
        assert state["completed_nodes"] == [PLANNER_NODE, BUG_NODE]
        assert [finding.category for finding in state["findings"]] == [
            Category.BUG
        ]