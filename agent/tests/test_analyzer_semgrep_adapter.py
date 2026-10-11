"""Tests for the Phase 7.5 Semgrep adapter.

A fake executor is injected everywhere: Semgrep is never installed,
started or needed. All payloads are synthetic and no network is used.
"""

import json
import os

import pytest

from app.analyzers.execution import (
    CommandExecutionResult,
    ExecutionStatus,
)
from app.analyzers.semgrep_adapter import SemgrepAdapter
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisFinding,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

_MISSING = object()


def completed(stdout="[]", exit_code=0, **overrides):
    data = {
        "status": ExecutionStatus.COMPLETED,
        "exit_code": exit_code,
        "stdout": stdout,
        "duration_ms": 12,
    }
    data.update(overrides)
    return CommandExecutionResult(**data)


class FakeExecutor:
    def __init__(self, result=None):
        self.requests = []
        self.result = result if result is not None else completed()

    def execute(self, request):
        self.requests.append(request)
        return self.result


def scan_result(
    check_id="python.lang.correctness.useless-eqeq.useless-eqeq",
    path="pkg/mod.py",
    start_line=1,
    end_line=_MISSING,
    message="useless comparison",
    severity="WARNING",
    metadata=_MISSING,
):
    entry = {
        "check_id": check_id,
        "extra": {
            "fingerprint": "abc123",
            "is_ignored": False,
            "lines": "x == x",
            "message": message,
            "severity": severity,
        },
        "path": path,
        "start": {"col": 1, "line": start_line, "offset": 0},
    }
    if end_line is _MISSING:
        entry["end"] = {"col": 5, "line": start_line, "offset": 4}
    elif end_line is not None:
        entry["end"] = {"col": 5, "line": end_line, "offset": 4}
    if metadata is _MISSING:
        entry["extra"]["metadata"] = {}
    elif metadata is not None:
        entry["extra"]["metadata"] = metadata
    return entry


def report(*results, errors=None, scanned=("pkg/mod.py",)):
    return json.dumps(
        {
            "errors": list(errors) if errors is not None else [],
            "paths": {"scanned": list(scanned)},
            "results": list(results),
            "version": "1.90.0",
        }
    )


def write_file(root, name, content="x == x\n"):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build(tmp_path, files=("pkg/mod.py",)):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    config = tmp_path / "trusted_rules.yml"
    config.write_text("rules: []\n", encoding="utf-8")
    for name in files:
        write_file(repo, name)
    executor = FakeExecutor()
    adapter = SemgrepAdapter(
        ToolRunner(executor=executor), str(config)
    )
    return adapter, executor, repo, config


def analyze_with(
    tmp_path,
    execution,
    targets=("pkg/mod.py",),
    files=("pkg/mod.py",),
):
    adapter, executor, repo, config = build(tmp_path, files)
    executor.result = execution
    result = adapter.analyze(str(repo), list(targets))
    return result, executor


def config_argument(config):
    return f"--config={os.path.realpath(str(config))}"


class TestCommandConstruction:
    def test_command_is_explicit_argument_list(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg/mod.py"])
        assert executor.requests[0].command == [
            "semgrep",
            "scan",
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            config_argument(config),
            "pkg/mod.py",
        ]

    def test_cwd_is_repository_directory(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg/mod.py"])
        assert executor.requests[0].cwd == os.path.realpath(str(repo))

    def test_custom_executable_used(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter = SemgrepAdapter(
            ToolRunner(executor=executor),
            str(config),
            executable="/opt/tools/semgrep",
        )
        adapter.analyze(str(repo), ["pkg/mod.py"])
        assert executor.requests[0].command[0] == "/opt/tools/semgrep"

    def test_no_config_auto_or_registry(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg/mod.py"])
        command = executor.requests[0].command
        assert "auto" not in command
        assert not any(
            argument.startswith("p/") for argument in command
        )
        assert not any(
            argument.startswith("http") for argument in command
        )

    def test_no_implicit_metrics_or_version_check(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg/mod.py"])
        command = executor.requests[0].command
        assert "--metrics=off" in command
        assert "--disable-version-check" in command
        assert "--no-git-ignore" in command

    def test_multiple_targets_keep_order(self, tmp_path):
        adapter, executor, repo, config = build(
            tmp_path, files=("pkg/mod.py", "app.py")
        )
        adapter.analyze(str(repo), ["pkg/mod.py", "app.py"])
        command = executor.requests[0].command
        assert command[-2:] == ["pkg/mod.py", "app.py"]

    def test_all_arguments_are_strings(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg/mod.py"])
        assert all(
            isinstance(argument, str)
            for argument in executor.requests[0].command
        )

    def test_relative_config_resolved_to_absolute(
        self, tmp_path, monkeypatch
    ):
        adapter_executor = FakeExecutor()
        config = tmp_path / "trusted_rules.yml"
        config.write_text("rules: []\n", encoding="utf-8")
        repo = tmp_path / "repo"
        repo.mkdir()
        write_file(repo, "pkg/mod.py")
        monkeypatch.chdir(tmp_path)
        adapter = SemgrepAdapter(
            ToolRunner(executor=adapter_executor), "trusted_rules.yml"
        )
        adapter.analyze(str(repo), ["pkg/mod.py"])
        assert (
            config_argument(config)
            in adapter_executor.requests[0].command
        )


class TestTrustedConfigValidation:
    def test_missing_config_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            SemgrepAdapter(
                ToolRunner(executor=FakeExecutor()),
                str(tmp_path / "missing.yml"),
            )

    @pytest.mark.parametrize("config", ["", "   "])
    def test_blank_config_rejected(self, config):
        with pytest.raises(ValueError):
            SemgrepAdapter(ToolRunner(executor=FakeExecutor()), config)

    def test_none_config_rejected(self):
        with pytest.raises(ValueError):
            SemgrepAdapter(ToolRunner(executor=FakeExecutor()), None)

    def test_directory_config_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            SemgrepAdapter(
                ToolRunner(executor=FakeExecutor()), str(tmp_path)
            )

    def test_padded_config_rejected(self, tmp_path):
        config = tmp_path / "trusted_rules.yml"
        config.write_text("rules: []\n")
        with pytest.raises(ValueError):
            SemgrepAdapter(
                ToolRunner(executor=FakeExecutor()),
                f" {config} ",
            )

    def test_nul_config_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            SemgrepAdapter(
                ToolRunner(executor=FakeExecutor()), "a\x00b.yml"
            )

    def test_config_inside_repo_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        inside = repo / "rules.yml"
        inside.write_text("rules: []\n", encoding="utf-8")
        write_file(repo, "pkg/mod.py")
        executor = FakeExecutor()
        adapter = SemgrepAdapter(
            ToolRunner(executor=executor), str(inside)
        )
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["pkg/mod.py"])
        assert executor.requests == []

    def test_nested_config_inside_repo_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "config").mkdir(parents=True)
        inside = repo / "config" / "rules.yml"
        inside.write_text("rules: []\n", encoding="utf-8")
        executor = FakeExecutor()
        adapter = SemgrepAdapter(
            ToolRunner(executor=executor), str(inside)
        )
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["pkg/mod.py"])
        assert executor.requests == []


class TestExecutionStatusMapping:
    def test_tool_not_found(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.tool is StaticAnalysisTool.SEMGREP
        assert result.status is StaticAnalysisStatus.UNAVAILABLE
        assert result.error_code is StaticAnalysisErrorCode.TOOL_NOT_FOUND
        assert result.exit_code is None
        assert result.findings == []

    def test_timeout(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.TIMEOUT
        assert result.error_code is StaticAnalysisErrorCode.TIMEOUT
        assert result.findings == []

    def test_spawn_failure(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.SPAWN_FAILED
        assert result.findings == []

    def test_execution_error_unknown(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.UNKNOWN,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.UNKNOWN
        assert result.findings == []


class TestExitCodeHandling:
    def test_exit_code_zero_without_findings(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 0
        assert result.findings == []

    def test_exit_code_one_with_findings_is_ok(self, tmp_path):
        execution = completed(
            report(scan_result()), exit_code=1
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 1
        assert len(result.findings) == 1

    def test_exit_code_one_without_findings_is_ok(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    @pytest.mark.parametrize("exit_code", [2, 3, 5, 7])
    def test_fatal_exit_codes_are_process_failed(
        self, tmp_path, exit_code
    ):
        execution = completed(report(), exit_code=exit_code)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.exit_code == exit_code
        assert result.findings == []

    def test_parse_failure_keeps_exit_code(self, tmp_path):
        execution = completed("not json", exit_code=1)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.exit_code == 1


class TestSuccessMapping:
    def test_no_findings_gives_empty_findings(self, tmp_path):
        result, _ = analyze_with(tmp_path, completed(report()))
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []
        assert result.error_code is None
        assert result.duration_ms == 12

    def test_single_finding_field_mapping(self, tmp_path):
        entry = scan_result(
            check_id="python.lang.security.audit.exec-detected",
            path="pkg/mod.py",
            start_line=5,
            end_line=7,
            message="Detected the use of exec().",
            severity="ERROR",
            metadata={"category": "security"},
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry), exit_code=1)
        )
        finding = result.findings[0]
        assert finding.tool is StaticAnalysisTool.SEMGREP
        assert (
            finding.rule_id
            == "python.lang.security.audit.exec-detected"
        )
        assert finding.message == "Detected the use of exec()."
        assert finding.category is Category.SECURITY
        assert finding.severity is Severity.HIGH
        assert finding.file_path == "pkg/mod.py"
        assert finding.start_line == 5
        assert finding.end_line == 7

    def test_multiple_findings_keep_order(self, tmp_path):
        entries = [
            scan_result(
                check_id="a.b.one",
                start_line=1,
                metadata=None,
            ),
            scan_result(
                check_id="a.b.two",
                path="pkg/mod.py",
                start_line=10,
                metadata=None,
            ),
            scan_result(
                check_id="a.b.three",
                path="pkg/mod.py",
                start_line=20,
                metadata=None,
            ),
        ]
        result, _ = analyze_with(
            tmp_path, completed(report(*entries))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert [finding.start_line for finding in result.findings] == [
            1,
            10,
            20,
        ]

    def test_multilanguage_targets_accepted(self, tmp_path):
        names = (
            "src/Main.java",
            "web/app.js",
            "svc/main.go",
            "pkg/mod.py",
        )
        execution = completed(report(scanned=names))
        result, executor = analyze_with(
            tmp_path,
            execution,
            targets=names,
            files=names,
        )
        assert result.status is StaticAnalysisStatus.OK
        assert executor.requests[0].command[-4:] == list(names)

    def test_java_finding_maps(self, tmp_path):
        entry = scan_result(
            check_id="java.lang.security.audit.script-engine",
            path="src/Main.java",
            metadata={"category": "security"},
        )
        execution = completed(
            report(entry, scanned=("src/Main.java",))
        )
        result, _ = analyze_with(
            tmp_path,
            execution,
            targets=("src/Main.java",),
            files=("src/Main.java",),
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].file_path == "src/Main.java"


class TestSeverityMapping:
    @pytest.mark.parametrize(
        ("severity", "expected"),
        [
            ("ERROR", Severity.HIGH),
            ("WARNING", Severity.MEDIUM),
            ("INFO", Severity.LOW),
        ],
    )
    def test_severity_maps_explicitly(
        self, tmp_path, severity, expected
    ):
        entry = scan_result(severity=severity)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].severity is expected

    @pytest.mark.parametrize(
        "severity",
        ["CRITICAL", "error", "Warning", "", "WARN", "UNKNOWN"],
    )
    def test_unknown_severity_is_schema_mismatch(
        self, tmp_path, severity
    ):
        entry = scan_result(severity=severity)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_missing_severity_is_schema_mismatch(self, tmp_path):
        entry = scan_result()
        del entry["extra"]["severity"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_severity_is_not_final_risk_claim(self, tmp_path):
        low = scan_result(
            check_id="rule.info", severity="INFO", metadata=None
        )
        high = scan_result(
            check_id="rule.error",
            severity="ERROR",
            start_line=2,
            metadata=None,
        )
        result, _ = analyze_with(
            tmp_path, completed(report(low, high))
        )
        assert result.findings[0].severity is Severity.LOW
        assert result.findings[1].severity is Severity.HIGH


class TestCategoryMapping:
    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("security", Category.SECURITY),
            ("correctness", Category.BUG),
            ("performance", Category.PERFORMANCE),
            ("best-practice", Category.QUALITY),
            ("maintainability", Category.QUALITY),
            ("portability", Category.QUALITY),
        ],
    )
    def test_metadata_category_mapping(
        self, tmp_path, category, expected
    ):
        entry = scan_result(metadata={"category": category})
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is expected

    def test_metadata_category_is_case_insensitive(self, tmp_path):
        entry = scan_result(metadata={"category": "Security"})
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.SECURITY

    def test_check_id_segment_used_when_metadata_missing(
        self, tmp_path
    ):
        entry = scan_result(
            check_id="python.lang.security.audit.exec-detected",
            metadata=None,
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.SECURITY

    def test_check_id_segment_used_when_metadata_unknown(
        self, tmp_path
    ):
        entry = scan_result(
            check_id="rules.correctness.unused-value",
            metadata={"category": "weird"},
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.BUG

    def test_non_string_metadata_category_falls_back(
        self, tmp_path
    ):
        entry = scan_result(
            check_id="my.company.rule",
            metadata={"category": ["security"]},
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.QUALITY

    def test_default_is_quality_not_security(self, tmp_path):
        entry = scan_result(
            check_id="my.company.custom-rule", metadata=None
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.QUALITY
        assert result.findings[0].category is not Category.SECURITY

    def test_performance_segment_fallback(self, tmp_path):
        entry = scan_result(
            check_id="lang.performance.regex", metadata=None
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.PERFORMANCE


class TestLineNumbers:
    def test_start_line_from_start(self, tmp_path):
        entry = scan_result(start_line=9)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].start_line == 9

    def test_end_line_from_end(self, tmp_path):
        entry = scan_result(start_line=3, end_line=6)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].start_line == 3
        assert result.findings[0].end_line == 6

    def test_missing_end_falls_back_to_start(self, tmp_path):
        entry = scan_result(start_line=7, end_line=None)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].start_line == 7
        assert result.findings[0].end_line == 7

    def test_end_before_start_rejected(self, tmp_path):
        entry = scan_result(start_line=10, end_line=4)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize("line", [0, -1, "1", 1.0, True])
    def test_invalid_start_line_rejected(self, tmp_path, line):
        entry = scan_result(start_line=line)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize("line", [0, -1, "2"])
    def test_invalid_end_line_rejected(self, tmp_path, line):
        entry = scan_result(start_line=1, end_line=line)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_missing_start_rejected(self, tmp_path):
        entry = scan_result()
        del entry["start"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_end_without_line_rejected(self, tmp_path):
        entry = scan_result()
        del entry["end"]["line"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )


class TestParseFailures:
    @pytest.mark.parametrize(
        "stdout", ["", " ", "\n", "not json", "{} trailing"]
    )
    def test_non_json_output_is_parse_error(self, tmp_path, stdout):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    @pytest.mark.parametrize(
        "stdout", ["[]", "42", '"text"', "null"]
    )
    def test_non_object_payload_is_schema_mismatch(
        self, tmp_path, stdout
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_missing_results_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {"errors": [], "paths": {"scanned": []}}
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_results_wrong_type_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {
                "errors": [],
                "paths": {"scanned": []},
                "results": {},
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_errors_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {"paths": {"scanned": ["pkg/mod.py"]}, "results": []}
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_errors_wrong_type_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {
                "errors": "boom",
                "paths": {"scanned": ["pkg/mod.py"]},
                "results": [],
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_paths_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps({"errors": [], "results": []})
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_scanned_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {"errors": [], "paths": {}, "results": []}
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_non_string_scanned_entry_is_schema_mismatch(
        self, tmp_path
    ):
        stdout = json.dumps(
            {"errors": [], "paths": {"scanned": [42]}, "results": []}
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_result_entry_not_object_is_schema_mismatch(
        self, tmp_path
    ):
        stdout = json.dumps(
            {
                "errors": [],
                "paths": {"scanned": ["pkg/mod.py"]},
                "results": [42],
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_check_id_is_schema_mismatch(self, tmp_path):
        entry = scan_result()
        del entry["check_id"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("check_id", ["", "   ", 42, None])
    def test_invalid_check_id_is_schema_mismatch(
        self, tmp_path, check_id
    ):
        entry = scan_result(check_id=check_id)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_extra_is_schema_mismatch(self, tmp_path):
        entry = scan_result()
        del entry["extra"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("message", ["", "   ", 42])
    def test_invalid_message_is_schema_mismatch(
        self, tmp_path, message
    ):
        entry = scan_result(message=message)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_message_is_schema_mismatch(self, tmp_path):
        entry = scan_result()
        del entry["extra"]["message"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_one_bad_entry_invalidates_whole_run(self, tmp_path):
        entries = [scan_result(), {"check_id": "x"}]
        result, _ = analyze_with(
            tmp_path, completed(report(*entries))
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_truncated_stdout_is_rejected(self, tmp_path):
        execution = completed(
            report(scan_result()), stdout_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    def test_truncated_stdout_with_incomplete_json_rejected(
        self, tmp_path
    ):
        execution = completed(
            stdout='{"results": [{"check_id": "x"',
            stdout_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_truncated_stderr_alone_is_accepted(self, tmp_path):
        execution = completed(
            report(scan_result()), stderr_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert len(result.findings) == 1


class TestScanCompleteness:
    def test_scan_errors_reject_whole_run(self, tmp_path):
        execution = completed(
            report(
                scan_result(),
                errors=[
                    {
                        "code": 2,
                        "level": "warn",
                        "message": "Timeout",
                        "type": "Timeout",
                    }
                ],
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    @pytest.mark.parametrize("level", ["warn", "error", "fatal"])
    def test_any_error_level_rejects_run(self, tmp_path, level):
        execution = completed(
            report(errors=[{"level": level, "message": "x"}])
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.findings == []

    def test_unscanned_target_rejects_run(self, tmp_path):
        execution = completed(report())
        result, _ = analyze_with(
            tmp_path,
            execution,
            targets=("pkg/mod.py", "app.py"),
            files=("pkg/mod.py", "app.py"),
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    def test_unscanned_target_with_findings_still_rejected(
        self, tmp_path
    ):
        execution = completed(report(scan_result()))
        result, _ = analyze_with(
            tmp_path,
            execution,
            targets=("pkg/mod.py", "app.py"),
            files=("pkg/mod.py", "app.py"),
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.findings == []

    def test_all_targets_scanned_is_ok(self, tmp_path):
        result, _ = analyze_with(
            tmp_path,
            completed(report()),
            targets=("pkg/mod.py",),
            files=("pkg/mod.py",),
        )
        assert result.status is StaticAnalysisStatus.OK

    def test_absolute_scanned_paths_normalized(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        scanned = str(repo / "pkg" / "mod.py")
        executor.result = completed(
            report(scanned=(scanned,))
        )
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.status is StaticAnalysisStatus.OK

    def test_backslash_scanned_paths_normalized(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        executor.result = completed(
            report(scanned=("pkg\\mod.py",))
        )
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.status is StaticAnalysisStatus.OK

    def test_extra_scanned_files_tolerated(self, tmp_path):
        adapter, executor, repo, config = build(
            tmp_path, files=("pkg/mod.py", "other.py")
        )
        executor.result = completed(
            report(scanned=("pkg/mod.py", "other.py"))
        )
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.status is StaticAnalysisStatus.OK

    def test_scanned_path_outside_repo_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        outside = os.path.join(
            os.path.dirname(str(repo)), "elsewhere.py"
        )
        executor.result = completed(
            report(scanned=(outside,))
        )
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_traversal_scanned_path_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        executor.result = completed(
            report(scanned=("../mod.py",))
        )
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH


class TestFilePathMapping:
    def test_relative_path_kept(self, tmp_path):
        entry = scan_result(path="pkg/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_backslash_path_normalized(self, tmp_path):
        entry = scan_result(path="pkg\\mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_dot_slash_prefix_normalized(self, tmp_path):
        entry = scan_result(path="./pkg/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_absolute_path_inside_repo_normalized(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        entry = scan_result(path=str(repo / "pkg" / "mod.py"))
        executor.result = completed(report(entry))
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.findings[0].file_path == "pkg/mod.py"

    @pytest.mark.parametrize(
        "path",
        [
            "../outside.py",
            "pkg/../../outside.py",
            "..\\outside.py",
            "",
            "   ",
        ],
    )
    def test_traversal_or_blank_path_rejected(self, tmp_path, path):
        entry = scan_result(path=path)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_absolute_path_outside_repo_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        outside = os.path.join(
            os.path.dirname(str(repo)), "outside.py"
        )
        executor.result = completed(
            report(scan_result(path=outside))
        )
        result = adapter.analyze(str(repo), ["pkg/mod.py"])
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_drive_absolute_path_rejected(self, tmp_path):
        entry = scan_result(path="C:/repo/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_unrequested_file_rejected(self, tmp_path):
        entry = scan_result(path="other.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.skipif(
        os.name != "nt", reason="case folding is Windows specific"
    )
    def test_case_different_path_maps_on_windows(self, tmp_path):
        entry = scan_result(path="PKG/MOD.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].file_path == "pkg/mod.py"


class TestInputValidation:
    def test_blank_repo_dir_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        for repo_dir in ("", "   "):
            with pytest.raises(ValueError):
                adapter.analyze(repo_dir, ["pkg/mod.py"])

    def test_missing_repo_dir_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(
                os.path.join(str(tmp_path), "missing"),
                ["pkg/mod.py"],
            )

    def test_empty_targets_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [])

    def test_string_targets_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), "pkg/mod.py")

    def test_none_targets_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), None)

    def test_absolute_target_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        absolute = str(repo / "pkg" / "mod.py")
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [absolute])
        assert executor.requests == []

    def test_drive_target_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["C:/repo/mod.py"])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target",
        [
            "../outside.py",
            "pkg/../../outside.py",
            "..\\outside.py",
            "pkg/./mod.py",
            "pkg//mod.py",
            "pkg/mod.py/",
        ],
    )
    def test_malformed_target_rejected(self, tmp_path, target):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    def test_nul_target_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["pkg/mod\x00.py"])
        assert executor.requests == []

    def test_missing_target_file_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["pkg/missing.py"])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "name", ["src/Main.java", "web/app.js", "svc/main.go"]
    )
    def test_non_python_files_accepted(self, tmp_path, name):
        adapter, executor, repo, config = build(
            tmp_path, files=(name,)
        )
        executor.result = completed(report(scanned=(name,)))
        result = adapter.analyze(str(repo), [name])
        assert result.status is StaticAnalysisStatus.OK

    def test_backslash_input_normalized(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg\\mod.py"])
        assert executor.requests[0].command[-1] == "pkg/mod.py"

    def test_duplicate_targets_deduplicated(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["pkg/mod.py", "pkg/mod.py"])
        command = executor.requests[0].command
        assert command.count("pkg/mod.py") == 1

    @pytest.mark.parametrize("executable", ["", "   "])
    def test_blank_executable_rejected(self, tmp_path, executable):
        config = tmp_path / "trusted_rules.yml"
        config.write_text("rules: []\n", encoding="utf-8")
        with pytest.raises(ValueError):
            SemgrepAdapter(
                ToolRunner(executor=FakeExecutor()),
                str(config),
                executable=executable,
            )


class TestSafety:
    def test_failure_result_does_not_expose_raw_output(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.UNKNOWN,
            stdout="sensitive-source-content",
            stderr="sensitive-error-detail",
        )
        result, _ = analyze_with(tmp_path, execution)
        dumped = result.model_dump_json()
        assert "sensitive-source-content" not in dumped
        assert "sensitive-error-detail" not in dumped

    def test_parse_failure_does_not_expose_output(self, tmp_path):
        execution = completed(stdout="secret_token_123 not json")
        result, _ = analyze_with(tmp_path, execution)
        assert "secret_token_123" not in result.model_dump_json()

    def test_scan_error_message_not_exposed(self, tmp_path):
        execution = completed(
            report(
                errors=[
                    {
                        "level": "error",
                        "message": "sensitive-scan-error-message",
                    }
                ]
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert (
            "sensitive-scan-error-message"
            not in result.model_dump_json()
        )

    def test_message_content_only_in_findings(self, tmp_path):
        entry = scan_result(message="Detected the use of exec().")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert (
            result.findings[0].message
            == "Detected the use of exec()."
        )


class TestResultContract:
    def test_ok_result_has_no_error_code(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(scan_result()))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.error_code is None

    @pytest.mark.parametrize(
        "execution",
        [
            CommandExecutionResult(
                status=ExecutionStatus.UNAVAILABLE,
                error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
            ),
            CommandExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error_code=StaticAnalysisErrorCode.TIMEOUT,
            ),
            CommandExecutionResult(
                status=ExecutionStatus.ERROR,
                error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
            ),
        ],
    )
    def test_failure_result_has_no_findings(self, tmp_path, execution):
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is not StaticAnalysisStatus.OK
        assert result.error_code is not None
        assert result.findings == []

    def test_findings_all_carry_semgrep_tool(self, tmp_path):
        entries = [
            scan_result(check_id="a.b.one", metadata=None),
            scan_result(
                check_id="a.b.two", start_line=2, metadata=None
            ),
        ]
        result, _ = analyze_with(
            tmp_path, completed(report(*entries))
        )
        assert all(
            finding.tool is StaticAnalysisTool.SEMGREP
            for finding in result.findings
        )

    def test_ok_result_with_findings_round_trips(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(scan_result()))
        )
        recreated = type(result).model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result