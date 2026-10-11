"""ReviewService integration tests for the Phase 8.6 static stage.

A fake static analysis service is injected: no tool runs and no network
is used. The real StaticAnalysisService is covered separately in
tests/test_static_analysis_service.py.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analyzers.aggregation import aggregate_results
from app.analyzers.scheduler import SchedulerOutcome
from app.context.pr_context_client import PrContextClient
from app.llm.llm_service import LLMService
from app.schemas.pr_context import PrContext
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)
from app.services.request_budget import (
    RequestBudget,
    ReviewBudgetExceededError,
)
from app.services.review_service import ReviewService
from app.services.static_analysis_service import StaticAnalysisOutcome

PY_SOURCE = "x = 2\ny = 3\n"

PY_PATCH = "\n".join(
    [
        "@@ -1,2 +1,2 @@",
        "-x = 1",
        "+x = 2",
        " y = 3",
    ]
)

LLM_FINDING = ReviewFinding(
    category=Category.QUALITY,
    severity=Severity.LOW,
    confidence=0.5,
    rule_id="LLM-001",
    title="LLM finding",
    file_path="src/A.java",
    start_line=1,
    end_line=1,
    description="description",
    reason="reason",
    suggestion="suggestion",
    references=[],
)


def make_request(**overrides):
    data = {
        "task_id": 1,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "files": [],
    }
    data.update(overrides)
    return ReviewTaskRequest(**data)


def make_llm(findings=None):
    llm = MagicMock(spec=LLMService)
    llm.generate_findings = AsyncMock(return_value=findings or [])
    return llm


def make_pr_file(**overrides):
    data = {
        "path": "pkg/mod.py",
        "previousPath": None,
        "status": "modified",
        "additions": 1,
        "deletions": 1,
        "changes": 2,
        "patch": PY_PATCH,
        "blobUrl": None,
        "content_available": True,
        "content_truncated": False,
        "content_reason": None,
        "content": PY_SOURCE,
    }
    data.update(overrides)
    return data


def make_pr_context(files=None):
    return PrContext.model_validate(
        {
            "taskId": 1,
            "owner": "owner",
            "repo": "repo",
            "prNumber": 42,
            "commitSha": "abc123",
            "title": "t",
            "state": "open",
            "baseRef": "main",
            "headRef": "feature/x",
            "files": files if files is not None else [make_pr_file()],
        }
    )


def make_context_client(return_value=None, error=None):
    client = MagicMock(spec=PrContextClient)
    if error is not None:
        client.fetch = AsyncMock(side_effect=error)
    else:
        client.fetch = AsyncMock(
            return_value=return_value
            if return_value is not None
            else make_pr_context()
        )
    return client


def make_static_finding():
    return StaticAnalysisFinding(
        tool=StaticAnalysisTool.RUFF,
        rule_id="F401",
        category=Category.QUALITY,
        severity=Severity.INFO,
        message="`os` imported but unused",
        file_path="pkg/mod.py",
        start_line=1,
        end_line=1,
    )


def make_outcome(findings=None):
    result = StaticAnalysisResult(
        tool=StaticAnalysisTool.RUFF,
        status=StaticAnalysisStatus.OK,
        findings=list(findings or []),
    )
    return StaticAnalysisOutcome(
        results=[result],
        aggregate=aggregate_results(SchedulerOutcome(results=[result])),
    )


class FakeStaticService:
    """Duck typed stand-in for StaticAnalysisService."""

    def __init__(self, outcome=None, error=None, sleep_seconds=0.0):
        self.calls = []
        self._outcome = outcome
        self._error = error
        self._sleep_seconds = sleep_seconds

    def analyze(self, files, budget, parent_dir=None):
        self.calls.append((dict(files), budget))
        if self._sleep_seconds:
            time.sleep(self._sleep_seconds)
        if self._error is not None:
            raise self._error
        if self._outcome is None:
            return make_outcome()
        return self._outcome


def make_service(llm=None, client=None, static=None, **overrides):
    return ReviewService(
        llm_service=llm if llm is not None else make_llm(),
        pr_context_client=(
            client if client is not None else make_context_client()
        ),
        static_analysis_service=static,
        **overrides,
    )


class TestStaticStageWiring:
    def test_findings_reach_prompt_and_report(self):
        llm = make_llm()
        static = FakeStaticService(
            outcome=make_outcome([make_static_finding()])
        )
        service = make_service(llm=llm, static=static)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        user = llm.generate_findings.call_args[0][0][1]["content"]
        assert "- [RUFF] F401 (INFO/QUALITY) pkg/mod.py:1-1" in user
        report = result.report["static_analysis"]
        assert report["available"] is True
        assert report["findings"] == 1
        assert report["tools_run"] == ["RUFF"]
        assert static.calls[0][0] == {"pkg/mod.py": PY_SOURCE}

    def test_static_findings_are_not_merged_into_llm_findings(self):
        llm = make_llm([LLM_FINDING])
        static = FakeStaticService(
            outcome=make_outcome([make_static_finding()])
        )
        service = make_service(llm=llm, static=static)

        result = asyncio.run(service.review(make_request()))

        assert [f.rule_id for f in result.findings] == ["LLM-001"]
        assert result.report["total_findings"] == 1
        assert result.report["static_analysis"]["findings"] == 1

    def test_static_stage_receives_shared_budget(self):
        static = FakeStaticService()
        service = make_service(static=static, request_budget_seconds=5)

        asyncio.run(service.review(make_request()))

        _, budget = static.calls[0]
        assert isinstance(budget, RequestBudget)
        assert budget.seconds == 5

    def test_content_unavailable_files_are_not_sent_to_tools(self):
        files = [
            make_pr_file(),
            make_pr_file(
                path="README.md",
                patch=None,
                content_available=False,
                content_reason="unsupported_language",
                content=None,
            ),
        ]
        static = FakeStaticService()
        service = make_service(
            client=make_context_client(make_pr_context(files)),
            static=static,
        )

        asyncio.run(service.review(make_request()))

        assert static.calls[0][0] == {"pkg/mod.py": PY_SOURCE}

    def test_no_static_service_keeps_previous_report_shape(self):
        service = make_service(client=make_context_client())

        result = asyncio.run(service.review(make_request()))

        assert set(result.report) == {
            "summary",
            "total_findings",
            "context",
        }


class TestStaticStageDegradation:
    def test_static_failure_degrades_without_breaking_review(self):
        llm = make_llm()
        static = FakeStaticService(error=RuntimeError("boom"))
        service = make_service(llm=llm, static=static)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        llm.generate_findings.assert_awaited_once()
        report = result.report["static_analysis"]
        assert report["available"] is False
        assert report["degraded"] is True
        assert report["reason"] == "RuntimeError"
        assert report["tools_run"] == []
        assert report["findings"] == 0
        assert report["status_counts"]["OK"] == 0
        user = llm.generate_findings.call_args[0][0][1]["content"]
        assert "Static analysis evidence" not in user

    def test_context_unavailable_skips_static_stage(self):
        static = FakeStaticService()
        service = make_service(
            client=make_context_client(error=RuntimeError("no context")),
            static=static,
        )

        result = asyncio.run(service.review(make_request()))

        assert static.calls == []
        report = result.report["static_analysis"]
        assert report["available"] is False
        assert report["reason"] == "context_unavailable"
        assert report["degraded"] is False

    def test_context_without_content_skips_static_stage(self):
        files = [
            make_pr_file(
                path="README.md",
                patch=None,
                content_available=False,
                content_reason="unsupported_language",
                content=None,
            )
        ]
        static = FakeStaticService()
        service = make_service(
            client=make_context_client(make_pr_context(files)),
            static=static,
        )

        result = asyncio.run(service.review(make_request()))

        assert static.calls == []
        assert result.report["static_analysis"]["reason"] == "no_files"

    def test_static_stage_may_not_consume_the_llm_budget(self):
        llm = make_llm()
        static = FakeStaticService(sleep_seconds=0.5)
        service = make_service(
            llm=llm, static=static, request_budget_seconds=0.4
        )

        with pytest.raises(ReviewBudgetExceededError):
            asyncio.run(service.review(make_request()))

        llm.generate_findings.assert_not_awaited()

    def test_static_skip_shape_matches_completed_shape(self):
        static = FakeStaticService()
        service = make_service(
            client=make_context_client(error=RuntimeError("no context")),
            static=static,
        )

        result = asyncio.run(service.review(make_request()))

        completed_keys = set(
            make_outcome().report_summary().keys()
        ) | {"available", "reason"}
        assert set(result.report["static_analysis"]) == completed_keys

    def test_production_composition_missing_tools_is_not_success(self):
        """Real service + missing executables must degrade, not fake OK."""
        from app.analyzers.execution import (
            CommandExecutionResult,
            ExecutionStatus,
        )
        from app.schemas.static_analysis import StaticAnalysisErrorCode
        from app.services.static_analysis_service import (
            StaticAnalysisService,
        )

        class UnavailableExecutor:
            def __init__(self):
                self.requests = []

            def execute(self, request):
                self.requests.append(request)
                return CommandExecutionResult(
                    status=ExecutionStatus.UNAVAILABLE,
                    error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
                )

        executor = UnavailableExecutor()
        static = StaticAnalysisService(
            executor=executor, semgrep_config_path=None
        )
        llm = make_llm()
        service = make_service(llm=llm, static=static)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        report = result.report["static_analysis"]
        assert report["available"] is True
        assert report["degraded"] is True
        assert set(report["failed_tools"]) == {"RUFF", "BANDIT"}
        assert report["findings"] == 0
        assert len(executor.requests) == 2
        user = llm.generate_findings.call_args[0][0][1]["content"]
        assert "Static analysis evidence" not in user