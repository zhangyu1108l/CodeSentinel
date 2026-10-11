"""Tests for the Phase 8.6 production static analysis service.

A fake executor is injected everywhere: Ruff, Bandit and Semgrep are never
installed, started or needed, and no network is used. All payloads are
synthetic and every assertion checks the truthful status contract.
"""

import json
import logging
import time

import pytest

from app.agents.context_payload import build_agent_context
from app.analyzers.execution import (
    CommandExecutionResult,
    ExecutionStatus,
)
from app.schemas.code_context import (
    ChangedRange,
    CodeContext,
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
    Language,
)
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)
from app.services.request_budget import RequestBudget
from app.services.static_analysis_service import (
    NOTE_SEMGREP_CONFIG_INVALID,
    REASON_BUDGET_EXHAUSTED,
    REASON_NO_CONFIGURED_TOOLS,
    REASON_NO_FILES,
    StaticAnalysisService,
)

SOURCE_SENTINEL = "SENTINEL-SOURCE-DO-NOT-LOG = 1\n"


def completed(stdout="[]", exit_code=0, **overrides):
    data = {
        "status": ExecutionStatus.COMPLETED,
        "exit_code": exit_code,
        "stdout": stdout,
        "duration_ms": 5,
    }
    data.update(overrides)
    return CommandExecutionResult(**data)


def unavailable():
    return CommandExecutionResult(
        status=ExecutionStatus.UNAVAILABLE,
        error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
    )


def timed_out():
    return CommandExecutionResult(
        status=ExecutionStatus.TIMEOUT,
        error_code=StaticAnalysisErrorCode.TIMEOUT,
    )


class FakeExecutor:
    """Returns queued results in call order; never starts a process."""

    def __init__(self, results=None):
        self.requests = []
        self._results = list(results) if results else []

    def execute(self, request):
        self.requests.append(request)
        if not self._results:
            raise AssertionError(
                "unexpected analyzer command: " + repr(request.command)
            )
        return self._results.pop(0)


def ruff_diagnostic(
    code="F401",
    message="`os` imported but unused",
    filename="pkg/mod.py",
    row=1,
    end_row=1,
):
    return {
        "cell": None,
        "code": code,
        "end_location": {"column": 10, "row": end_row},
        "filename": filename,
        "fix": None,
        "location": {"column": 8, "row": row},
        "message": message,
        "noqa_row": row,
        "url": "https://docs.astral.sh/ruff/rules/unused-import",
    }


def ruff_payload(*diagnostics):
    return json.dumps(list(diagnostics))


def bandit_payload(*issues):
    return json.dumps(
        {
            "errors": [],
            "generated_at": "2026-10-11T00:00:00Z",
            "metrics": {"_totals": {}},
            "results": list(issues),
        }
    )


def bandit_issue(
    test_id="B101",
    issue_text="Use of assert detected.",
    filename="pkg/mod.py",
    line_number=1,
):
    return {
        "code": "assert value\n",
        "col_offset": 0,
        "end_col_offset": 12,
        "filename": filename,
        "issue_confidence": "HIGH",
        "issue_severity": "LOW",
        "issue_text": issue_text,
        "line_number": line_number,
        "more_info": "https://bandit.readthedocs.io/plugins/b101.html",
        "test_id": test_id,
        "test_name": "assert_used",
        "line_range": [line_number],
    }


def semgrep_payload(*results, scanned=("pkg/mod.py",)):
    return json.dumps(
        {
            "errors": [],
            "paths": {"scanned": list(scanned)},
            "results": list(results),
            "version": "1.90.0",
        }
    )


def semgrep_result(
    check_id="python.lang.correctness.useless-eqeq",
    path="pkg/mod.py",
    line=1,
    message="useless comparison",
):
    return {
        "check_id": check_id,
        "extra": {
            "fingerprint": "abc123",
            "is_ignored": False,
            "lines": "x == x",
            "message": message,
            "metadata": {},
            "severity": "WARNING",
        },
        "path": path,
        "start": {"col": 1, "line": line, "offset": 0},
        "end": {"col": 5, "line": line, "offset": 4},
    }


PY_FILE = {"pkg/mod.py": SOURCE_SENTINEL}


def make_service(executor, **overrides):
    overrides.setdefault("semgrep_config_path", None)
    return StaticAnalysisService(executor=executor, **overrides)


def make_semgrep_config(tmp_path):
    config = tmp_path / "semgrep-rules.yaml"
    config.write_text("rules: []\n", encoding="utf-8")
    return str(config)


class TestToolAvailability:
    def test_missing_tools_are_unavailable_not_success(self):
        executor = FakeExecutor([unavailable(), unavailable()])
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(30)
        )
        assert [r.tool for r in outcome.results] == [
            StaticAnalysisTool.RUFF,
            StaticAnalysisTool.BANDIT,
        ]
        assert all(
            r.status is StaticAnalysisStatus.UNAVAILABLE
            for r in outcome.results
        )
        assert outcome.aggregate.findings == []
        assert outcome.aggregate.failed_tools == [
            StaticAnalysisTool.RUFF,
            StaticAnalysisTool.BANDIT,
        ]
        assert outcome.aggregate.partial is True
        assert outcome.degraded is True
        summary = outcome.report_summary()
        assert summary["failed_tools"] == ["RUFF", "BANDIT"]
        assert summary["findings"] == 0

    def test_blank_executable_is_not_configured(self):
        executor = FakeExecutor([completed(bandit_payload())])
        outcome = make_service(executor, ruff_executable="  ").analyze(
            PY_FILE, RequestBudget(30)
        )
        assert [r.tool for r in outcome.results] == [
            StaticAnalysisTool.BANDIT
        ]
        assert StaticAnalysisTool.RUFF in outcome.not_configured_tools
        assert (
            StaticAnalysisTool.SEMGREP in outcome.not_configured_tools
        )
        assert executor.requests[0].command[0] == "bandit"

    def test_all_tools_disabled_reports_no_configuration(self):
        executor = FakeExecutor()
        outcome = make_service(
            executor,
            ruff_executable=None,
            bandit_executable="",
            semgrep_executable=None,
        ).analyze(PY_FILE, RequestBudget(30))
        assert outcome.results == []
        assert REASON_NO_CONFIGURED_TOOLS in outcome.notes
        assert outcome.budget_exhausted is False
        assert executor.requests == []
        assert len(outcome.not_configured_tools) == 3

    def test_tools_without_applicable_files_are_skipped(self):
        executor = FakeExecutor()
        outcome = make_service(executor).analyze(
            {"notes.md": "text\n"}, RequestBudget(30)
        )
        assert outcome.results == []
        assert outcome.aggregate.skipped_tools == [
            StaticAnalysisTool.RUFF,
            StaticAnalysisTool.BANDIT,
        ]
        assert outcome.aggregate.failed_tools == []
        assert executor.requests == []

    def test_semgrep_without_config_is_never_executed(self):
        executor = FakeExecutor([completed(), completed(bandit_payload())])
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(30)
        )
        assert len(executor.requests) == 2
        assert outcome.not_configured_tools == [
            StaticAnalysisTool.SEMGREP
        ]

    def test_invalid_semgrep_config_is_not_configured_without_degrading(
        self, tmp_path
    ):
        executor = FakeExecutor([completed(), completed(bandit_payload())])
        outcome = make_service(
            executor, semgrep_config_path=str(tmp_path / "missing.yaml")
        ).analyze(PY_FILE, RequestBudget(30))
        assert len(executor.requests) == 2
        assert outcome.not_configured_tools == [
            StaticAnalysisTool.SEMGREP
        ]
        assert NOTE_SEMGREP_CONFIG_INVALID in outcome.notes
        # Decision C: a missing trusted config is an optional capability
        # gap, not an execution failure of the enabled tools.
        assert outcome.degraded is False

    def test_invalid_inputs_are_caller_defects(self, tmp_path):
        executor = FakeExecutor()
        service = make_service(executor)
        with pytest.raises(ValueError):
            service.analyze(PY_FILE, "not-a-budget")
        with pytest.raises(ValueError):
            service.analyze("not-a-mapping", RequestBudget(30))
        with pytest.raises(ValueError):
            StaticAnalysisService(executor=executor, stage_share=0)
        with pytest.raises(ValueError):
            StaticAnalysisService(executor=executor, stage_share=1.5)

    def test_path_traversal_is_rejected_before_any_tool_runs(self):
        executor = FakeExecutor()
        with pytest.raises(ValueError, match="traversal"):
            make_service(executor).analyze(
                {"../evil.py": "x = 1\n"}, RequestBudget(30)
            )
        assert executor.requests == []


class TestSuccessPaths:
    def test_success_with_zero_findings_is_not_degraded(self, tmp_path):
        executor = FakeExecutor(
            [
                completed(ruff_payload()),
                completed(bandit_payload()),
                completed(semgrep_payload(scanned=("pkg/mod.py",))),
            ]
        )
        outcome = make_service(
            executor, semgrep_config_path=make_semgrep_config(tmp_path)
        ).analyze(PY_FILE, RequestBudget(30))
        assert [r.status for r in outcome.results] == [
            StaticAnalysisStatus.OK,
            StaticAnalysisStatus.OK,
            StaticAnalysisStatus.OK,
        ]
        assert outcome.aggregate.findings == []
        assert outcome.aggregate.partial is False
        assert outcome.degraded is False
        assert outcome.budget_exhausted is False

    def test_findings_are_mapped_with_paths_and_lines(self, tmp_path):
        executor = FakeExecutor(
            [
                completed(ruff_payload(ruff_diagnostic(row=2, end_row=2))),
                completed(bandit_payload(bandit_issue(line_number=3))),
                completed(
                    semgrep_payload(semgrep_result(line=4)),
                    scanned=("pkg/mod.py",),
                ),
            ]
        )
        outcome = make_service(
            executor, semgrep_config_path=make_semgrep_config(tmp_path)
        ).analyze(PY_FILE, RequestBudget(30))
        findings = outcome.findings
        assert [f.tool for f in findings] == [
            StaticAnalysisTool.RUFF,
            StaticAnalysisTool.BANDIT,
            StaticAnalysisTool.SEMGREP,
        ]
        for finding in findings:
            assert finding.file_path == "pkg/mod.py"
            assert finding.start_line >= 1
            assert finding.end_line >= finding.start_line
        assert findings[0].rule_id == "F401"
        assert findings[0].start_line == 2
        assert findings[1].start_line == 3
        assert findings[2].start_line == 4
        assert outcome.report_summary()["findings"] == 3

    def test_non_zero_exit_with_valid_findings_is_ok(self):
        executor = FakeExecutor(
            [completed(ruff_payload(ruff_diagnostic()), exit_code=1)]
        )
        outcome = make_service(
            executor, bandit_executable=None
        ).analyze(PY_FILE, RequestBudget(30))
        result = outcome.results[0]
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 1
        assert len(outcome.findings) == 1


class TestFailureTruthfulness:
    def test_timeout_is_reported_and_never_yields_findings(self):
        executor = FakeExecutor([timed_out(), completed(bandit_payload())])
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(30)
        )
        statuses = {r.tool: r.status for r in outcome.results}
        assert statuses[StaticAnalysisTool.RUFF] is (
            StaticAnalysisStatus.TIMEOUT
        )
        assert statuses[StaticAnalysisTool.BANDIT] is (
            StaticAnalysisStatus.OK
        )
        assert outcome.aggregate.failed_tools == [
            StaticAnalysisTool.RUFF
        ]
        assert outcome.aggregate.findings == []
        assert outcome.degraded is True

    def test_truncated_output_is_a_parse_error(self):
        executor = FakeExecutor(
            [completed(ruff_payload(ruff_diagnostic()), stdout_truncated=True)]
        )
        outcome = make_service(
            executor, bandit_executable=None
        ).analyze(PY_FILE, RequestBudget(30))
        result = outcome.results[0]
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.findings == []
        assert outcome.aggregate.findings == []

    def test_corrupted_output_is_a_parse_error(self):
        executor = FakeExecutor(
            [completed("not json {", exit_code=1)]
        )
        outcome = make_service(
            executor, bandit_executable=None
        ).analyze(PY_FILE, RequestBudget(30))
        result = outcome.results[0]
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is (
            StaticAnalysisErrorCode.INVALID_OUTPUT
        )
        assert outcome.degraded is True

    def test_partial_failure_keeps_only_ok_findings(self):
        executor = FakeExecutor(
            [completed(ruff_payload(ruff_diagnostic())), unavailable()]
        )
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(30)
        )
        assert len(outcome.findings) == 1
        assert outcome.aggregate.completed_tools == [
            StaticAnalysisTool.RUFF
        ]
        assert outcome.aggregate.failed_tools == [
            StaticAnalysisTool.BANDIT
        ]
        assert outcome.aggregate.partial is True

    def test_scheduler_error_result_is_not_success(self):
        class BrokenAnalyzer:
            def analyze(self, repo_dir, file_paths):
                raise RuntimeError("boom")

        # The scheduler converts a raising analyzer into ERROR; no layer
        # may turn that into a successful empty scan.
        from app.analyzers.scheduler import StaticAnalysisScheduler

        scheduler = StaticAnalysisScheduler(
            {StaticAnalysisTool.RUFF: BrokenAnalyzer()}
        )
        outcome = scheduler.run_on_contents(PY_FILE)
        assert outcome.results[0].status is StaticAnalysisStatus.ERROR
        assert outcome.results[0].findings == []


class TestBudgetSharing:
    def test_expired_budget_never_starts_a_tool(self):
        clock = [1000.0]
        budget = RequestBudget(10, clock=lambda: clock[0])
        clock[0] += 11
        executor = FakeExecutor()
        outcome = make_service(executor).analyze(PY_FILE, budget)
        assert executor.requests == []
        assert outcome.results == []
        assert outcome.budget_exhausted is True
        assert REASON_BUDGET_EXHAUSTED in outcome.notes
        assert outcome.degraded is True

    def test_stage_share_bounds_each_tool_timeout(self):
        executor = FakeExecutor([completed(), completed(bandit_payload())])
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(40)
        )
        assert len(outcome.results) == 2
        # stage = 40 * 0.5 = 20s, two tools -> 10s each (the budget clock
        # is real, so allow for the microseconds the test itself burns).
        for request in executor.requests:
            assert request.timeout_seconds == pytest.approx(10.0, abs=0.05)

    def test_per_tool_timeout_is_capped_by_framework_default(self):
        executor = FakeExecutor([completed(), completed(bandit_payload())])
        outcome = make_service(executor, stage_share=1.0).analyze(
            PY_FILE, RequestBudget(1000)
        )
        assert len(outcome.results) == 2
        assert [r.timeout_seconds for r in executor.requests] == [
            60.0,
            60.0,
        ]

    def test_scheduler_gate_marks_budget_exhausted_tools(self):
        class SlowExecutor(FakeExecutor):
            def execute(self, request):
                self.requests.append(request)
                time.sleep(0.3)
                return completed()

        # remaining 11.2 - reserve 11 = 0.2s deadline budget; stage share
        # min(5.6, 0.2) = 0.2s, so the first (fake) tool consumes 0.3s and
        # the scheduler must not start the second one. The fake executor
        # ignores its own timeout, which is exactly why the scheduler gate
        # has to hold; the wrapper still caps the wait at 0.1s per tool.
        executor = SlowExecutor()
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(11.2)
        )
        assert [r.tool for r in outcome.results] == [
            StaticAnalysisTool.RUFF
        ]
        assert outcome.aggregate.budget_exhausted_tools == [
            StaticAnalysisTool.BANDIT
        ]
        assert outcome.budget_exhausted is True
        assert REASON_BUDGET_EXHAUSTED in outcome.notes
        assert outcome.results[0].status is StaticAnalysisStatus.OK
        assert outcome.results[0].findings == []

    def test_empty_file_mapping_reports_no_files(self):
        executor = FakeExecutor()
        outcome = make_service(executor).analyze({}, RequestBudget(30))
        assert outcome.results == []
        assert REASON_NO_FILES in outcome.notes
        assert outcome.budget_exhausted is False


class TestSafetyAndHygiene:
    def test_source_content_never_reaches_logs(self, caplog):
        caplog.set_level(logging.DEBUG)
        executor = FakeExecutor(
            [completed(ruff_payload(ruff_diagnostic())), unavailable()]
        )
        make_service(executor).analyze(PY_FILE, RequestBudget(30))
        assert SOURCE_SENTINEL not in caplog.text

    def test_workspace_is_removed_after_run(self, tmp_path):
        parent = tmp_path / "work"
        parent.mkdir()
        executor = FakeExecutor([completed(), completed(bandit_payload())])
        make_service(executor).analyze(
            PY_FILE, RequestBudget(30), parent_dir=str(parent)
        )
        assert list(parent.iterdir()) == []

    def test_report_summary_is_json_safe_and_content_free(self):
        executor = FakeExecutor(
            [completed(ruff_payload(ruff_diagnostic())), unavailable()]
        )
        outcome = make_service(executor).analyze(
            PY_FILE, RequestBudget(30)
        )
        dumped = json.dumps(outcome.report_summary())
        assert SOURCE_SENTINEL not in dumped
        assert '"RUFF"' in dumped
        assert "F401" not in dumped


class TestPayloadChain:
    def test_aggregated_findings_inject_into_agent_context(self):
        executor = FakeExecutor(
            [completed(ruff_payload(ruff_diagnostic()))]
        )
        outcome = make_service(
            executor, bandit_executable=None
        ).analyze(PY_FILE, RequestBudget(30))
        assert len(outcome.findings) == 1

        file_diff = FileDiff(
            path="pkg/mod.py",
            status=FileStatus.MODIFIED,
            language=Language.PYTHON,
            changed_ranges=[ChangedRange(start_line=1, end_line=1)],
        )
        context = CodeContext(
            repository="owner/repo",
            pr_number=42,
            head_sha="abc123",
            files=[
                FileContext(
                    file_diff=file_diff,
                    content=FileContent(
                        path="pkg/mod.py", content=SOURCE_SENTINEL
                    ),
                    line_count=1,
                    content_available=True,
                )
            ],
        )
        payload = build_agent_context(
            context, static_findings=outcome.findings
        )
        assert payload.available is True
        assert payload.static_findings_included == 1
        assert "F401" in payload.static_section
        assert payload.paths == ["pkg/mod.py"]
        assert payload.line_ranges["pkg/mod.py"] == [(1, 1)]


class TestRealExecutorAvailability:
    def test_missing_executables_are_unavailable_with_real_executor(self):
        """Real SubprocessExecutor, no fake: a missing tool must degrade.

        The executables are intentionally names that do not exist on any
        machine, so this test spawns nothing and needs no installed tool.
        """
        service = StaticAnalysisService(
            ruff_executable="codesentinel-missing-tool-ruff",
            bandit_executable="codesentinel-missing-tool-bandit",
            semgrep_config_path=None,
        )

        outcome = service.analyze(PY_FILE, RequestBudget(30))

        statuses = {result.tool: result.status for result in outcome.results}
        assert statuses == {
            StaticAnalysisTool.RUFF: StaticAnalysisStatus.UNAVAILABLE,
            StaticAnalysisTool.BANDIT: StaticAnalysisStatus.UNAVAILABLE,
        }
        assert outcome.aggregate.findings == []
        assert outcome.degraded is True
        assert outcome.budget_exhausted is False
        summary = outcome.report_summary()
        assert set(summary["failed_tools"]) == {"RUFF", "BANDIT"}
        assert summary["findings"] == 0


class TestDocumentedBudgetBound:
    def test_execution_overhead_constants_are_locked(self):
        """The documented static stage bound depends on these constants.

        A timed out tool can overrun its own timeout by the terminate
        grace plus two reader joins; DEVELOPMENT_STATUS.md documents the
        resulting row (11s per timed out tool, plus the per tool cap).
        If the constants change, that analysis must be updated.
        """
        from app.analyzers import execution

        grace = execution._TERMINATE_GRACE_SECONDS
        join = execution._READER_JOIN_TIMEOUT_SECONDS
        assert grace == 1.0
        assert join == 5.0
        assert grace + 2 * join == 11.0
        assert execution.PROCESS_CLEANUP_RESERVE_SECONDS == 11.0


class TestDeadlineReserve:
    """Fixed clock tests for the Phase 8.9 shared deadline reserve."""

    def test_tool_timeout_leaves_the_cleanup_reserve(self):
        from app.analyzers.execution import (
            PROCESS_CLEANUP_RESERVE_SECONDS,
        )

        clock = [100.0]
        budget = RequestBudget(30, clock=lambda: clock[0])
        executor = FakeExecutor(
            [completed(), completed(bandit_payload())]
        )
        outcome = make_service(executor).analyze(PY_FILE, budget)
        assert len(outcome.results) == 2
        # remaining 30 - reserve 11 = 19; stage min(15, 19) = 15; per
        # tool 7.5 and the executor wrapper cannot raise it.
        for request in executor.requests:
            assert request.timeout_seconds == pytest.approx(7.5)
            assert request.timeout_seconds <= (
                30 - PROCESS_CLEANUP_RESERVE_SECONDS
            )

    def test_no_tool_starts_when_remaining_is_not_above_reserve(self):
        from app.analyzers.execution import (
            PROCESS_CLEANUP_RESERVE_SECONDS,
        )

        assert PROCESS_CLEANUP_RESERVE_SECONDS == 11.0
        clock = [0.0]
        budget = RequestBudget(10, clock=lambda: clock[0])
        executor = FakeExecutor()
        outcome = make_service(executor).analyze(PY_FILE, budget)
        assert executor.requests == []
        assert outcome.results == []
        assert outcome.budget_exhausted is True
        assert REASON_BUDGET_EXHAUSTED in outcome.notes
        assert outcome.degraded is True

    def test_remaining_just_above_reserve_still_starts_tools(self):
        clock = [0.0]
        budget = RequestBudget(12, clock=lambda: clock[0])
        executor = FakeExecutor(
            [completed(), completed(bandit_payload())]
        )
        outcome = make_service(executor).analyze(PY_FILE, budget)
        assert len(executor.requests) == 2
        # remaining 12 - reserve 11 = 1; stage min(6, 1) = 1; per tool
        # 0.5.
        for request in executor.requests:
            assert request.timeout_seconds == pytest.approx(0.5)
        assert outcome.budget_exhausted is False

    def test_all_configured_tools_ok_is_not_degraded_under_reserve(self):
        from app.analyzers.execution import (
            PROCESS_CLEANUP_RESERVE_SECONDS,
        )

        clock = [0.0]
        budget = RequestBudget(30, clock=lambda: clock[0])
        executor = FakeExecutor(
            [completed(), completed(bandit_payload())]
        )
        outcome = make_service(executor).analyze(PY_FILE, budget)
        assert outcome.degraded is False
        assert PROCESS_CLEANUP_RESERVE_SECONDS == 11.0