"""Tests for the Phase 8.7 analysis context stage.

Fake PR context client and fake static service only: no network, no LLM,
no tool process. The stage reuses the real CodeContextBuilder and the
real context budget helpers.
"""

import asyncio
import logging

import httpx

from app.analyzers.aggregation import aggregate_results
from app.analyzers.scheduler import SchedulerOutcome
from app.context.pr_context_client import PrContextClient
from app.graph.analysis_context import (
    REASON_BUDGET_EXHAUSTED,
    REASON_NOT_CONFIGURED,
    AnalysisContextStage,
)
from app.schemas.pr_context import PrContext
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)
from app.services.request_budget import RequestBudget
from app.services.static_analysis_service import StaticAnalysisOutcome

PY_SOURCE = "x = 2\ny = 3\n"
SOURCE_SENTINEL = "SENTINEL-CONTEXT-SOURCE"

PY_PATCH = "\n".join(
    [
        "@@ -1,2 +1,2 @@",
        "-x = 1",
        "+x = 2",
        " y = 3",
    ]
)


def make_request():
    from app.schemas.review import ReviewTaskRequest

    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


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
            "prNumber": 2,
            "commitSha": "abc123",
            "title": "t",
            "state": "open",
            "baseRef": "main",
            "headRef": "feature/x",
            "files": files if files is not None else [make_pr_file()],
        }
    )


class FakeContextClient:
    def __init__(self, value=None, error=None):
        self.value = value if value is not None else make_pr_context()
        self.error = error
        self.calls = 0

    async def fetch(self, task_id):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.value


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
    def __init__(self, outcome=None, error=None):
        self.calls = []
        self._outcome = outcome
        self._error = error

    def analyze(self, files, budget, parent_dir=None):
        self.calls.append((dict(files), budget))
        if self._error is not None:
            raise self._error
        if self._outcome is None:
            return make_outcome()
        return self._outcome


def prepare(stage, budget=None):
    return asyncio.run(
        stage.prepare(make_request(), budget or RequestBudget(30))
    )


class TestAvailability:
    def test_without_client_context_is_not_configured(self):
        result = prepare(AnalysisContextStage())

        assert result.payload is None
        assert result.context_report["available"] is False
        assert result.context_report["reason"] == REASON_NOT_CONFIGURED
        assert result.static_report["available"] is False
        assert result.static_report["reason"] == REASON_NOT_CONFIGURED
        assert result.static_findings == []

    def test_expired_budget_never_fetches(self):
        client = FakeContextClient()
        stage = AnalysisContextStage(pr_context_client=client)
        budget = RequestBudget(1e-9)

        result = prepare(stage, budget)

        assert client.calls == 0
        assert result.context_report["reason"] == REASON_BUDGET_EXHAUSTED

    def test_context_timeout_must_be_positive_finite(self):
        for value in (0, -1, float("nan"), float("inf"), "x", True):
            try:
                AnalysisContextStage(context_timeout_seconds=value)
            except ValueError:
                continue
            raise AssertionError(f"expected ValueError for {value!r}")


class TestContextLoading:
    def test_successful_context_builds_payload(self):
        static = FakeStaticService(
            outcome=make_outcome([make_static_finding()])
        )
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(),
            static_analysis_service=static,
        )

        result = prepare(stage)

        assert result.context_report["available"] is True
        assert result.context_report["degraded"] is False
        assert result.context_report["file_count"] == 1
        assert result.payload is not None
        assert result.payload.available is True
        assert result.payload.paths == ["pkg/mod.py"]
        assert "F401" in result.payload.static_section
        assert result.static_findings == [make_static_finding()]
        assert result.static_report["available"] is True
        assert result.static_report["tools_run"] == ["RUFF"]

    def test_changed_ranges_are_exposed_for_validation(self):
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient()
        )

        result = prepare(stage)

        assert (1, 1) in result.changed_ranges["pkg/mod.py"]

    def test_degraded_context_has_no_changed_ranges(self):
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(
                error=RuntimeError("no context")
            )
        )

        result = prepare(stage)

        assert result.changed_ranges == {}

    def test_static_service_receives_content_and_shared_budget(self):
        static = FakeStaticService()
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(),
            static_analysis_service=static,
        )
        budget = RequestBudget(30)

        prepare(stage, budget)

        files, received_budget = static.calls[0]
        assert files == {"pkg/mod.py": PY_SOURCE}
        assert received_budget is budget

    def test_without_static_service_payload_still_built(self):
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient()
        )

        result = prepare(stage)

        assert result.payload.available is True
        assert result.static_report["reason"] == REASON_NOT_CONFIGURED
        assert result.static_findings == []

    def test_files_without_content_report_no_files(self):
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
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(
                make_pr_context(files)
            ),
            static_analysis_service=static,
        )

        result = prepare(stage)

        assert static.calls == []
        assert result.static_report["reason"] == "no_files"
        assert result.static_report["available"] is False
        assert result.context_report["available"] is True


class TestDegradation:
    def test_fetch_failure_degrades_with_status_code(self):
        error = httpx.HTTPStatusError(
            "HTTP 500",
            request=httpx.Request("GET", "http://localhost:8080"),
            response=httpx.Response(500),
        )
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(error=error)
        )

        result = prepare(stage)

        assert result.payload is None
        assert result.context_report["available"] is False
        assert result.context_report["degraded"] is True
        assert result.context_report["reason"] == "http_error:500"
        assert result.static_report["available"] is False
        assert result.static_report["degraded"] is True
        assert result.static_findings == []

    def test_static_failure_does_not_break_context(self):
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(),
            static_analysis_service=FakeStaticService(
                error=RuntimeError("boom")
            ),
        )

        result = prepare(stage)

        assert result.context_report["available"] is True
        assert result.payload.available is True
        assert result.static_report["available"] is False
        assert result.static_report["degraded"] is True
        assert result.static_report["reason"] == "RuntimeError"
        assert result.static_findings == []

    def test_source_content_never_reaches_logs(self, caplog):
        caplog.set_level(logging.DEBUG)
        stage = AnalysisContextStage(
            pr_context_client=FakeContextClient(),
            static_analysis_service=FakeStaticService(),
        )

        prepare(stage)

        assert SOURCE_SENTINEL not in caplog.text
        assert PY_SOURCE not in caplog.text