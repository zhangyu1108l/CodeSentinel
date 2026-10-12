"""End to end tests for the Phase 8.7 analysis pipeline.

The graph runs with fake planners, agents, context stages and a fake LLM
layer: no real LLM, no network, no tool process. The tests lock the
pipeline contract (Planner -> context -> agents -> validator -> reporter)
and the production switch decision (the router still serves the existing
ReviewWorkflow).
"""

import asyncio

import pytest

from app.agents.context_payload import AgentContextPayload
from app.graph.analysis_context import ContextStageResult
from app.graph.analysis_workflow import (
    BUG_NODE,
    PERFORMANCE_NODE,
    QUALITY_NODE,
    SECURITY_NODE,
    AnalysisWorkflow,
)
from app.schemas.plan import AnalysisPlan
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisTool,
)

ALL_NODES = {
    BUG_NODE: Category.BUG,
    SECURITY_NODE: Category.SECURITY,
    PERFORMANCE_NODE: Category.PERFORMANCE,
    QUALITY_NODE: Category.QUALITY,
}


def make_payload(available=True):
    return AgentContextPayload(
        available=available,
        reason=None if available else "context_unavailable",
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        code_section="CODE",
        paths=["a.py"] if available else [],
        line_ranges={"a.py": [(1, 10)]} if available else {},
    )


def make_finding(
    category=Category.BUG,
    file_path="a.py",
    rule_id="R1",
    title="Title",
):
    return ReviewFinding(
        category=category,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id=rule_id,
        title=title,
        file_path=file_path,
        start_line=1,
        end_line=1,
        description="description",
        reason="reason",
        suggestion="suggestion",
        references=[],
    )


class FakePlanner:
    def __init__(self, plan=None, error=None):
        self.plan_value = plan or AnalysisPlan.model_validate(
            {"tasks": [{"agent": "BUG"}]}
        )
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
        changed_ranges=None,
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
        self.changed_ranges = dict(changed_ranges or {})

    async def prepare(self, request, budget):
        return ContextStageResult(
            payload=self.payload,
            context_report=dict(self.context_report),
            static_report=dict(self.static_report),
            static_findings=list(self.static_findings),
            changed_ranges=dict(self.changed_ranges),
        )

STATIC_FINDING = StaticAnalysisFinding(
    tool=StaticAnalysisTool.RUFF,
    rule_id="F401",
    category=Category.QUALITY,
    severity=Severity.INFO,
    message="`os` imported but unused",
    file_path="a.py",
    start_line=1,
    end_line=1,
)


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


def make_plan(*categories):
    return AnalysisPlan.model_validate(
        {"tasks": [{"agent": category.value} for category in categories]}
    )


def make_agents():
    return {
        node_id: FakeFindingAgent(
            [make_finding(category=category)]
        )
        for node_id, category in ALL_NODES.items()
    }


class CountingValidator:
    """Delegates to the real validator and counts invocations."""

    def __init__(self):
        from app.agents.validator import Validator

        self._validator = Validator()
        self.calls = 0

    def validate(self, payload, findings, static_findings, **kwargs):
        self.calls += 1
        return self._validator.validate(
            payload, findings, static_findings, **kwargs
        )


class FailingValidator:
    def __init__(self):
        self.calls = 0

    def validate(self, payload, findings, static_findings, **kwargs):
        self.calls += 1
        raise ValueError("boom")


def build_workflow(
    planner=None,
    agents=None,
    context_stage=None,
    validator=None,
    **overrides,
):
    return AnalysisWorkflow(
        planner_agent=planner
        or FakePlanner(
            make_plan(
                Category.BUG,
                Category.SECURITY,
                Category.PERFORMANCE,
                Category.QUALITY,
            )
        ),
        finding_agents=agents or make_agents(),
        context_stage=context_stage or FakeContextStage(),
        validator=validator,
        **overrides,
    )


class TestFullPipeline:
    def test_all_four_agents_run_once_and_are_reported(self):
        validator = CountingValidator()
        workflow = build_workflow(validator=validator)
        agents = workflow.finding_agents

        result = asyncio.run(workflow.run(make_request()))

        assert all(agent.calls == 1 for agent in agents.values())
        assert validator.calls == 1
        assert result.report.executed_agents == [
            Category.BUG,
            Category.SECURITY,
            Category.PERFORMANCE,
            Category.QUALITY,
        ]
        assert result.report.planned_agents == result.report.executed_agents
        assert result.report.finding_count == 4
        assert result.report.source_counts == {"AGENT": 4, "STATIC": 0}
        assert result.report.validation["agent_kept"] == 4
        assert result.report.degraded is False

    def test_partial_agent_failure_keeps_other_findings(self):
        agents = make_agents()
        agents[SECURITY_NODE] = FakeFindingAgent(
            error=RuntimeError("boom")
        )
        workflow = build_workflow(agents=agents)

        result = asyncio.run(workflow.run(make_request()))

        assert result.report.failed_agents == [Category.SECURITY]
        assert result.report.executed_agents == [
            Category.BUG,
            Category.PERFORMANCE,
            Category.QUALITY,
        ]
        assert [finding.category for finding in result.findings] == [
            Category.BUG,
            Category.PERFORMANCE,
            Category.QUALITY,
        ]
        assert result.recoverable_errors == ["RuntimeError"]
        assert result.report.degraded is True
        assert any(
            "SECURITY" in note for note in result.report.notes
        )

    def test_static_evidence_is_reported_and_merged(self):
        static = STATIC_FINDING
        stage = FakeContextStage(static_findings=[static])
        agents = {
            QUALITY_NODE: FakeFindingAgent(
                [
                    make_finding(
                        category=Category.QUALITY,
                        rule_id="F401",
                        title="Unused import",
                    )
                ]
            )
        }
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.QUALITY)),
            agents=agents,
            context_stage=stage,
        )

        result = asyncio.run(workflow.run(make_request()))

        report = result.report
        assert report.finding_count == 1
        assert report.duplicates_merged == 1
        merged = report.findings[0]
        assert merged.sources == ["AGENT", "STATIC"]
        assert merged.tool is StaticAnalysisTool.RUFF
        assert report.source_counts == {"AGENT": 1, "STATIC": 0}
        assert report.static_analysis is not None

    def test_static_only_findings_are_reported(self):
        stage = FakeContextStage(static_findings=[STATIC_FINDING])
        agents = {
            QUALITY_NODE: FakeFindingAgent([])
        }
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.QUALITY)),
            agents=agents,
            context_stage=stage,
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.report.finding_count == 1
        finding = result.report.findings[0]
        assert finding.tool is StaticAnalysisTool.RUFF
        assert finding.confidence is None
        assert finding.title is None

    def test_context_degraded_drops_unverifiable_agent_findings(self):
        stage = FakeContextStage(
            payload=make_payload(available=False),
            context_report={
                "available": False,
                "degraded": True,
                "reason": "http_error:500",
                "file_count": 0,
                "files_with_content": 0,
                "estimated_tokens": 0,
                "truncated": False,
            },
        )
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.BUG)),
            agents={BUG_NODE: FakeFindingAgent([make_finding()])},
            context_stage=stage,
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.findings == []
        assert result.report.finding_count == 0
        assert result.report.degraded is True
        assert result.report.validation["agent_dropped"] == {
            "no_context": 1
        }
        assert any(
            "not a clean result" in note
            for note in result.report.notes
        )

    def test_validator_failure_is_reported_not_hidden(self):
        validator = FailingValidator()
        workflow = build_workflow(validator=validator)

        result = asyncio.run(workflow.run(make_request()))

        assert validator.calls == 1
        assert result.findings == []
        assert result.report.validation == {"failed": "ValueError"}
        assert result.report.degraded is True
        assert "ValueError" in result.recoverable_errors
        assert any(
            "validator failed: ValueError" in note
            for note in result.report.notes
        )

    def test_zero_findings_clean_run_is_not_degraded(self):
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.BUG)),
            agents={BUG_NODE: FakeFindingAgent([])},
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.report.finding_count == 0
        assert result.report.degraded is False
        assert result.report.status == "COMPLETED"
        assert result.report.severity_counts["HIGH"] == 0

    def test_findings_are_classified_against_changed_lines(self):
        stage = FakeContextStage(changed_ranges={"a.py": [(1, 1)]})
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.BUG)),
            agents={BUG_NODE: FakeFindingAgent([make_finding()])},
            context_stage=stage,
        )

        result = asyncio.run(workflow.run(make_request()))

        validation = result.report.validation
        assert validation["changed_line_anchored"] == 1
        assert validation["not_on_changed_lines"] == 0

    def test_off_diff_finding_is_counted_but_kept(self):
        stage = FakeContextStage(changed_ranges={"a.py": [(50, 60)]})
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.BUG)),
            agents={BUG_NODE: FakeFindingAgent([make_finding()])},
            context_stage=stage,
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.report.finding_count == 1
        assert (
            result.report.validation["not_on_changed_lines"] == 1
        )

    def test_static_degradation_does_not_stop_the_agents(self):
        stage = FakeContextStage(
            static_report={
                "available": True,
                "degraded": True,
                "reason": None,
                "tools_run": ["RUFF"],
                "failed_tools": ["BANDIT"],
                "findings": 0,
            }
        )
        workflow = build_workflow(
            planner=FakePlanner(make_plan(Category.BUG)),
            agents={BUG_NODE: FakeFindingAgent([make_finding()])},
            context_stage=stage,
        )

        result = asyncio.run(workflow.run(make_request()))

        assert result.report.finding_count == 1
        assert result.report.degraded is True
        assert result.report.static_analysis["degraded"] is True
        assert result.report.executed_agents == [Category.BUG]


class TestProductionSwitchGuard:
    def test_router_does_not_use_the_analysis_workflow(self):
        import app.api.review_router as router

        assert not hasattr(router, "AnalysisWorkflow")
        assert not hasattr(router, "get_analysis_workflow")

    def test_router_still_serves_the_review_workflow(self):
        from app.api import review_router

        assert hasattr(review_router, "get_review_workflow")
        assert hasattr(review_router, "get_review_service")

    def test_analysis_workflow_is_not_referenced_by_review_service(self):
        import app.services.review_service as review_service

        assert not hasattr(review_service, "AnalysisWorkflow")

    def test_review_route_response_model_is_the_review_contract(self):
        from app.main import app as fastapi_app

        schema = fastapi_app.openapi()
        operation = schema["paths"]["/api/reviews"]["post"]

        success = operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert success["$ref"].endswith("/ReviewTaskResult")

        request = operation["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert request["$ref"].endswith("/ReviewTaskRequest")

    def test_request_never_constructs_or_runs_analysis_machinery(
        self, monkeypatch
    ):
        """The strongest guard: a real request must not reach the pipeline.

        AnalysisWorkflow construction/run, PlannerAgent.plan and
        FindingAgent.analyze all raise if invoked; a successful request
        with exactly one ReviewService.review call proves the production
        route only uses the existing review chain (no duplicate LLM).
        """
        from unittest.mock import AsyncMock, MagicMock

        from fastapi.testclient import TestClient

        from app.agents import finding_agent, planner
        from app.api.review_router import get_review_service
        from app.graph import analysis_workflow
        from app.graph.analysis_context import AnalysisContextStage
        from app.main import app as fastapi_app
        from app.schemas.review import ReviewTaskResult

        async def must_not_run(*args, **kwargs):
            raise AssertionError(
                "analysis machinery must not run on /api/reviews"
            )

        def must_not_construct(*args, **kwargs):
            raise AssertionError(
                "AnalysisWorkflow must not be constructed on /api/reviews"
            )

        monkeypatch.setattr(
            analysis_workflow.AnalysisWorkflow,
            "__init__",
            must_not_construct,
        )
        monkeypatch.setattr(
            analysis_workflow.AnalysisWorkflow, "run", must_not_run
        )
        monkeypatch.setattr(planner.PlannerAgent, "plan", must_not_run)
        monkeypatch.setattr(
            finding_agent.FindingAgent, "analyze", must_not_run
        )
        monkeypatch.setattr(
            AnalysisContextStage, "prepare", must_not_run
        )

        service = MagicMock()
        service.review = AsyncMock(
            return_value=ReviewTaskResult(
                task_id=1,
                status="COMPLETED",
                report={"summary": "ok", "total_findings": 0},
                findings=[],
            )
        )
        fastapi_app.dependency_overrides[get_review_service] = (
            lambda: service
        )
        client = TestClient(fastapi_app, raise_server_exceptions=False)
        try:
            response = client.post(
                "/api/reviews",
                json={
                    "task_id": 1,
                    "repository": "owner/repo",
                    "pr_number": 42,
                    "commit_sha": "abc123",
                    "files": [],
                },
            )
        finally:
            fastapi_app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"
        assert service.review.await_count == 1