"""Tests for the serial static analysis scheduler (Phase 8 prep)."""

import os
import time
from pathlib import Path

import pytest

from app.analyzers.bandit_adapter import BanditAdapter
from app.analyzers.bandit_adapter import (
    _ALLOWED_SUFFIXES as BANDIT_SUFFIXES,
)
from app.analyzers.checkstyle_adapter import (
    _ALLOWED_SUFFIXES as CHECKSTYLE_SUFFIXES,
)
from app.analyzers.execution import (
    CommandExecutionResult,
    ExecutionStatus,
)
from app.analyzers.pmd_adapter import (
    _ALLOWED_SUFFIXES as PMD_SUFFIXES,
)
from app.analyzers.ruff_adapter import RuffAdapter
from app.analyzers.ruff_adapter import (
    _ALLOWED_SUFFIXES as RUFF_SUFFIXES,
)
from app.analyzers.scheduler import (
    DEFAULT_SUFFIXES_BY_TOOL,
    SchedulerOutcome,
    StaticAnalysisScheduler,
)
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

TOOLS = StaticAnalysisTool
STATUS = StaticAnalysisStatus
ERRORS = StaticAnalysisErrorCode

ALL_FILES = [
    "src/main.py",
    "src/stub.pyi",
    "src/App.java",
    "README.md",
    "notes.txt",
]


class FakeAnalyzer:
    """Test double recording calls and returning a canned outcome."""

    def __init__(self, tool, result=None, error=None, delay=0.0):
        self.tool = tool
        self.result = result
        self.error = error
        self.delay = delay
        self.calls = []

    def analyze(self, repo_dir, file_paths):
        self.calls.append((repo_dir, list(file_paths)))
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


class FakeExecutor:
    """Test double for the analyzer Executor protocol."""

    def __init__(self, results):
        self.requests = []
        self._results = list(results)

    def execute(self, request):
        self.requests.append(request)
        return self._results.pop(0)


class ReadingAnalyzer:
    """Test double that reads the materialized file contents."""

    def __init__(self, tool):
        self.tool = tool
        self.seen = {}

    def analyze(self, repo_dir, file_paths):
        for name in file_paths:
            with open(
                os.path.join(repo_dir, *name.split("/")),
                encoding="utf-8",
            ) as handle:
                self.seen[name] = handle.read()
        return ok_result(self.tool)


def make_finding(tool=TOOLS.RUFF, path="src/main.py"):
    return StaticAnalysisFinding(
        tool=tool,
        rule_id="R1",
        category=Category.QUALITY,
        severity=Severity.INFO,
        message="message",
        file_path=path,
        start_line=1,
        end_line=1,
    )


def ok_result(tool, findings=None):
    return StaticAnalysisResult(
        tool=tool,
        status=STATUS.OK,
        findings=list(findings or []),
    )


def failed_result(tool, status, error_code):
    return StaticAnalysisResult(
        tool=tool, status=status, error_code=error_code
    )


def completed(stdout=""):
    return CommandExecutionResult(
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        stdout=stdout,
        stderr="",
        duration_ms=1,
    )


@pytest.fixture
def repo(tmp_path):
    for name in ALL_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content\n", encoding="utf-8")
    return tmp_path


class TestConstruction:
    def test_rejects_non_mapping_analyzers(self):
        with pytest.raises(ValueError, match="mapping"):
            StaticAnalysisScheduler([FakeAnalyzer(TOOLS.RUFF)])

    def test_rejects_non_tool_keys(self):
        with pytest.raises(ValueError, match="StaticAnalysisTool"):
            StaticAnalysisScheduler(
                {"ruff": FakeAnalyzer(TOOLS.RUFF)}
            )

    def test_rejects_analyzer_without_analyze(self):
        with pytest.raises(ValueError, match="analyze"):
            StaticAnalysisScheduler({TOOLS.RUFF: object()})

    def test_accepts_empty_mapping(self, repo):
        outcome = StaticAnalysisScheduler({}).run(
            str(repo), ["src/main.py"]
        )
        assert outcome == SchedulerOutcome()

    def test_default_suffix_policy_matches_the_adapters(self):
        assert DEFAULT_SUFFIXES_BY_TOOL[TOOLS.RUFF] == tuple(
            RUFF_SUFFIXES
        )
        assert DEFAULT_SUFFIXES_BY_TOOL[TOOLS.BANDIT] == tuple(
            BANDIT_SUFFIXES
        )
        assert DEFAULT_SUFFIXES_BY_TOOL[TOOLS.PMD] == tuple(
            PMD_SUFFIXES
        )
        assert DEFAULT_SUFFIXES_BY_TOOL[TOOLS.CHECKSTYLE] == tuple(
            CHECKSTYLE_SUFFIXES
        )
        assert DEFAULT_SUFFIXES_BY_TOOL[TOOLS.SEMGREP] is None

    def test_rejects_non_mapping_suffixes(self):
        with pytest.raises(ValueError, match="suffixes"):
            StaticAnalysisScheduler({}, suffixes=".py")

    def test_rejects_string_suffix_policy(self):
        with pytest.raises(ValueError, match="suffix policy"):
            StaticAnalysisScheduler({}, suffixes={TOOLS.RUFF: ".py"})

    def test_rejects_empty_suffix_policy(self):
        with pytest.raises(ValueError, match="must not be empty"):
            StaticAnalysisScheduler({}, suffixes={TOOLS.RUFF: ()})

    def test_rejects_blank_suffix_entry(self):
        with pytest.raises(ValueError, match="non-empty strings"):
            StaticAnalysisScheduler(
                {}, suffixes={TOOLS.RUFF: (".py", "")}
            )

    def test_rejects_non_string_suffix_entry(self):
        with pytest.raises(ValueError, match="non-empty strings"):
            StaticAnalysisScheduler(
                {}, suffixes={TOOLS.RUFF: (".py", 3)}
            )


class TestRun:
    def test_runs_analyzers_in_insertion_order(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        semgrep = FakeAnalyzer(TOOLS.SEMGREP, ok_result(TOOLS.SEMGREP))
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        scheduler = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.SEMGREP: semgrep, TOOLS.PMD: pmd}
        )
        outcome = scheduler.run(str(repo), list(ALL_FILES))
        assert [result.tool for result in outcome.results] == [
            TOOLS.RUFF,
            TOOLS.SEMGREP,
            TOOLS.PMD,
        ]
        assert len(ruff.calls) == 1
        assert len(semgrep.calls) == 1
        assert len(pmd.calls) == 1

    def test_routes_targets_by_suffix_policy(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        semgrep = FakeAnalyzer(TOOLS.SEMGREP, ok_result(TOOLS.SEMGREP))
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        scheduler = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.SEMGREP: semgrep, TOOLS.PMD: pmd}
        )
        scheduler.run(str(repo), list(ALL_FILES))
        assert ruff.calls[0][1] == ["src/main.py", "src/stub.pyi"]
        assert semgrep.calls[0][1] == ALL_FILES
        assert pmd.calls[0][1] == ["src/App.java"]

    def test_normalizes_backslash_targets(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src\\main.py"]
        )
        assert ruff.calls[0][1] == ["src/main.py"]

    def test_deduplicates_targets(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py", "src\\main.py", "src/main.py"]
        )
        assert ruff.calls[0][1] == ["src/main.py"]

    def test_repo_dir_is_resolved_to_a_real_path(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"]
        )
        assert ruff.calls[0][0] == os.path.realpath(str(repo))

    def test_empty_file_list_is_a_no_op(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), []
        )
        assert outcome == SchedulerOutcome()
        assert ruff.calls == []

    def test_skips_tools_without_applicable_files(self, tmp_path):
        target = tmp_path / "only.py"
        target.write_text("x = 1\n", encoding="utf-8")
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        outcome = StaticAnalysisScheduler(
            {TOOLS.PMD: pmd, TOOLS.RUFF: ruff}
        ).run(str(tmp_path), ["only.py"])
        assert outcome.skipped_tools == [TOOLS.PMD]
        assert [result.tool for result in outcome.results] == [
            TOOLS.RUFF
        ]
        assert pmd.calls == []

    @pytest.mark.parametrize(
        "status,error_code",
        [
            (STATUS.UNAVAILABLE, ERRORS.TOOL_NOT_FOUND),
            (STATUS.TIMEOUT, ERRORS.TIMEOUT),
            (STATUS.ERROR, ERRORS.PROCESS_FAILED),
            (STATUS.PARSE_ERROR, ERRORS.INVALID_OUTPUT),
        ],
    )
    def test_failure_statuses_pass_through_unchanged(
        self, repo, status, error_code
    ):
        result = failed_result(TOOLS.RUFF, status, error_code)
        ruff = FakeAnalyzer(TOOLS.RUFF, result)
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"]
        )
        assert outcome.results == [result]
        assert outcome.results[0].status is status
        assert outcome.results[0].error_code is error_code

    def test_ok_result_with_findings_passes_through(self, repo):
        finding = make_finding()
        result = ok_result(TOOLS.RUFF, [finding])
        ruff = FakeAnalyzer(TOOLS.RUFF, result)
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"]
        )
        assert outcome.results[0] is result
        assert outcome.results[0].findings == [finding]

    def test_custom_policy_none_means_every_file(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        scheduler = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff}, suffixes={TOOLS.RUFF: None}
        )
        scheduler.run(str(repo), list(ALL_FILES))
        assert ruff.calls[0][1] == ALL_FILES

    def test_custom_policy_restricts_targets(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        scheduler = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff}, suffixes={TOOLS.RUFF: (".txt",)}
        )
        scheduler.run(str(repo), list(ALL_FILES))
        assert ruff.calls[0][1] == ["notes.txt"]

    def test_explicit_empty_mapping_means_every_file(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        scheduler = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff}, suffixes={}
        )
        scheduler.run(str(repo), list(ALL_FILES))
        assert ruff.calls[0][1] == ALL_FILES


class TestInputValidation:
    @pytest.fixture
    def fake(self):
        return FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))

    def test_missing_repo_dir_raises(self, tmp_path, fake):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(tmp_path / "missing"), ["a.py"]
            )
        assert fake.calls == []

    def test_repo_dir_must_be_a_directory(self, repo, fake):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(repo / "src" / "main.py"), ["src/main.py"]
            )
        assert fake.calls == []

    @pytest.mark.parametrize("file_paths", [None, "src/main.py", 123])
    def test_invalid_file_paths_container_raises(
        self, repo, fake, file_paths
    ):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(repo), file_paths
            )
        assert fake.calls == []

    def test_blank_target_raises(self, repo, fake):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(repo), [""]
            )
        assert fake.calls == []

    def test_nonexistent_target_raises(self, repo, fake):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(repo), ["missing.py"]
            )
        assert fake.calls == []

    def test_absolute_target_raises(self, repo, fake):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(repo), [str(repo / "src" / "main.py")]
            )
        assert fake.calls == []

    def test_traversal_target_raises(self, repo, fake):
        with pytest.raises(ValueError):
            StaticAnalysisScheduler({TOOLS.RUFF: fake}).run(
                str(repo), ["../main.py"]
            )
        assert fake.calls == []


class TestFailureIsolation:
    def test_raising_analyzer_is_isolated(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, error=RuntimeError("boom"))
        bandit = FakeAnalyzer(TOOLS.BANDIT, ok_result(TOOLS.BANDIT))
        outcome = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.BANDIT: bandit}
        ).run(str(repo), ["src/main.py"])
        assert [result.tool for result in outcome.results] == [
            TOOLS.RUFF,
            TOOLS.BANDIT,
        ]
        error_result = outcome.results[0]
        assert error_result.status is STATUS.ERROR
        assert error_result.error_code is ERRORS.UNKNOWN
        assert error_result.findings == []
        assert outcome.results[1] == bandit.result
        assert len(bandit.calls) == 1

    def test_value_error_is_isolated_too(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, error=ValueError("bad"))
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"]
        )
        assert outcome.results[0].status is STATUS.ERROR
        assert outcome.results[0].error_code is ERRORS.UNKNOWN

    def test_wrong_return_type_becomes_error(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, result="not a result")
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"]
        )
        assert outcome.results[0].tool is TOOLS.RUFF
        assert outcome.results[0].status is STATUS.ERROR
        assert outcome.results[0].error_code is ERRORS.UNKNOWN

    def test_result_for_a_different_tool_becomes_error(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, result=ok_result(TOOLS.BANDIT))
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"]
        )
        assert outcome.results[0].tool is TOOLS.RUFF
        assert outcome.results[0].status is STATUS.ERROR


class TestRunOnContents:
    def test_materializes_content_and_cleans_up(self, tmp_path):
        analyzer = ReadingAnalyzer(TOOLS.SEMGREP)
        scheduler = StaticAnalysisScheduler(
            {TOOLS.SEMGREP: analyzer}
        )
        work = tmp_path / "work"
        work.mkdir()
        outcome = scheduler.run_on_contents(
            {"pkg/mod.py": "x = 1\n", "README.md": "doc\n"},
            parent_dir=str(work),
        )
        assert analyzer.seen == {
            "pkg/mod.py": "x = 1\n",
            "README.md": "doc\n",
        }
        assert [result.tool for result in outcome.results] == [
            TOOLS.SEMGREP
        ]
        assert list(work.iterdir()) == []

    def test_invalid_path_raises_and_leaves_no_directory(
        self, tmp_path
    ):
        work = tmp_path / "work"
        work.mkdir()
        scheduler = StaticAnalysisScheduler(
            {TOOLS.SEMGREP: ReadingAnalyzer(TOOLS.SEMGREP)}
        )
        with pytest.raises(ValueError):
            scheduler.run_on_contents(
                {"../escape.py": "x"}, parent_dir=str(work)
            )
        assert list(work.iterdir()) == []

    def test_invalid_content_raises_and_leaves_no_directory(
        self, tmp_path
    ):
        work = tmp_path / "work"
        work.mkdir()
        scheduler = StaticAnalysisScheduler(
            {TOOLS.SEMGREP: ReadingAnalyzer(TOOLS.SEMGREP)}
        )
        with pytest.raises(ValueError):
            scheduler.run_on_contents(
                {"a.py": None}, parent_dir=str(work)
            )
        assert list(work.iterdir()) == []

    def test_empty_mapping_returns_empty_outcome(self, tmp_path):
        work = tmp_path / "work"
        work.mkdir()
        scheduler = StaticAnalysisScheduler(
            {TOOLS.SEMGREP: ReadingAnalyzer(TOOLS.SEMGREP)}
        )
        outcome = scheduler.run_on_contents({}, parent_dir=str(work))
        assert outcome == SchedulerOutcome()
        assert list(work.iterdir()) == []

    def test_analyzer_failure_still_cleans_up(self, tmp_path):
        work = tmp_path / "work"
        work.mkdir()
        analyzer = FakeAnalyzer(TOOLS.SEMGREP, error=RuntimeError("boom"))
        outcome = StaticAnalysisScheduler(
            {TOOLS.SEMGREP: analyzer}
        ).run_on_contents({"a.py": "x"}, parent_dir=str(work))
        assert outcome.results[0].status is STATUS.ERROR
        assert list(work.iterdir()) == []

    def test_suffix_filtering_applies_to_materialized_files(
        self, tmp_path
    ):
        work = tmp_path / "work"
        work.mkdir()
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        outcome = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.PMD: pmd}
        ).run_on_contents(
            {"a.py": "", "App.java": ""}, parent_dir=str(work)
        )
        assert ruff.calls[0][1] == ["a.py"]
        assert pmd.calls[0][1] == ["App.java"]
        assert outcome.skipped_tools == []
        assert list(work.iterdir()) == []


class TestRealAdaptersWithFakeTool:
    def test_ruff_and_bandit_adapters_are_schedulable(self, repo):
        ruff_executor = FakeExecutor([completed("[]")])
        bandit_executor = FakeExecutor(
            [completed('{"errors": [], "results": []}')]
        )
        scheduler = StaticAnalysisScheduler(
            {
                TOOLS.RUFF: RuffAdapter(
                    ToolRunner(executor=ruff_executor)
                ),
                TOOLS.BANDIT: BanditAdapter(
                    ToolRunner(executor=bandit_executor)
                ),
            }
        )
        outcome = scheduler.run(
            str(repo), ["src/main.py", "src/App.java"]
        )
        assert [result.tool for result in outcome.results] == [
            TOOLS.RUFF,
            TOOLS.BANDIT,
        ]
        assert all(
            result.status is STATUS.OK for result in outcome.results
        )
        request = ruff_executor.requests[0]
        assert request.command[:4] == [
            "ruff",
            "check",
            "--output-format",
            "json",
        ]
        assert request.command[-1] == "src/main.py"
        assert "src/App.java" not in request.command
        assert request.cwd == os.path.realpath(str(repo))
        assert bandit_executor.requests[0].command[0] == "bandit"


class TestBudget:
    def test_invalid_budget_is_rejected(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        scheduler = StaticAnalysisScheduler({TOOLS.RUFF: ruff})
        for value in (0, -1, "5", True):
            with pytest.raises(ValueError):
                scheduler.run(
                    str(repo), ["src/main.py"], budget_seconds=value
                )
        for value in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError, match="finite"):
                scheduler.run(
                    str(repo), ["src/main.py"], budget_seconds=value
                )
        assert ruff.calls == []

    def test_large_budget_allows_every_tool(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        outcome = StaticAnalysisScheduler({TOOLS.RUFF: ruff}).run(
            str(repo), ["src/main.py"], budget_seconds=30
        )
        assert outcome.budget_exhausted_tools == []
        assert [result.tool for result in outcome.results] == [
            TOOLS.RUFF
        ]

    def test_expired_budget_marks_applicable_tools_not_started(
        self, repo
    ):
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        outcome = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.PMD: pmd}
        ).run(
            str(repo),
            ["src/main.py", "src/App.java"],
            budget_seconds=1e-9,
        )
        assert outcome.results == []
        assert outcome.budget_exhausted_tools == [
            TOOLS.RUFF,
            TOOLS.PMD,
        ]
        assert ruff.calls == []
        assert pmd.calls == []

    def test_budget_consumed_by_first_tool_skips_the_rest(self, repo):
        ruff = FakeAnalyzer(
            TOOLS.RUFF, ok_result(TOOLS.RUFF), delay=0.3
        )
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        outcome = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.PMD: pmd}
        ).run(
            str(repo),
            ["src/main.py", "src/App.java"],
            budget_seconds=0.2,
        )
        assert [result.tool for result in outcome.results] == [
            TOOLS.RUFF
        ]
        assert outcome.budget_exhausted_tools == [TOOLS.PMD]
        assert len(ruff.calls) == 1
        assert pmd.calls == []

    def test_skipped_tools_are_not_budget_exhausted(self, tmp_path):
        target = tmp_path / "only.py"
        target.write_text("x = 1\n", encoding="utf-8")
        pmd = FakeAnalyzer(TOOLS.PMD, ok_result(TOOLS.PMD))
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        outcome = StaticAnalysisScheduler(
            {TOOLS.PMD: pmd, TOOLS.RUFF: ruff}
        ).run(str(tmp_path), ["only.py"], budget_seconds=1e-9)
        assert outcome.skipped_tools == [TOOLS.PMD]
        assert outcome.budget_exhausted_tools == [TOOLS.RUFF]
        assert outcome.results == []

    def test_run_on_contents_with_exhausted_budget_cleans_up(
        self, tmp_path
    ):
        work = tmp_path / "work"
        work.mkdir()
        ruff = FakeAnalyzer(TOOLS.RUFF, ok_result(TOOLS.RUFF))
        outcome = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff}
        ).run_on_contents(
            {"a.py": ""}, parent_dir=str(work), budget_seconds=1e-9
        )
        assert outcome.budget_exhausted_tools == [TOOLS.RUFF]
        assert ruff.calls == []
        assert list(work.iterdir()) == []

    def test_budget_does_not_change_failure_isolation(self, repo):
        ruff = FakeAnalyzer(TOOLS.RUFF, error=RuntimeError("boom"))
        bandit = FakeAnalyzer(TOOLS.BANDIT, ok_result(TOOLS.BANDIT))
        outcome = StaticAnalysisScheduler(
            {TOOLS.RUFF: ruff, TOOLS.BANDIT: bandit}
        ).run(str(repo), ["src/main.py"], budget_seconds=5)
        assert outcome.results[0].status is STATUS.ERROR
        assert outcome.budget_exhausted_tools == []
        assert len(bandit.calls) == 1