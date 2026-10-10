"""Tests for the Phase 7.4 Bandit adapter.

A fake executor is injected everywhere: Bandit is never installed,
started or needed. All payloads are synthetic and no network is used.
"""

import json
import os

import pytest

from app.analyzers.bandit_adapter import BanditAdapter
from app.analyzers.execution import (
    CommandExecutionResult,
    ExecutionStatus,
)
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


def issue(
    test_id="B101",
    issue_text="Use of assert detected.",
    filename="pkg/mod.py",
    line_number=1,
    issue_severity="LOW",
    issue_confidence="HIGH",
    line_range=_MISSING,
):
    entry = {
        "code": "assert value\n",
        "col_offset": 0,
        "end_col_offset": 12,
        "filename": filename,
        "issue_confidence": issue_confidence,
        "issue_severity": issue_severity,
        "issue_text": issue_text,
        "line_number": line_number,
        "more_info": "https://bandit.readthedocs.io/plugins/b101.html",
        "test_id": test_id,
        "test_name": "assert_used",
    }
    if line_range is _MISSING:
        entry["line_range"] = [line_number]
    elif line_range is not None:
        entry["line_range"] = line_range
    return entry


def report(*issues, errors=None):
    return json.dumps(
        {
            "errors": list(errors) if errors is not None else [],
            "generated_at": "2026-10-10T00:00:00Z",
            "metrics": {"_totals": {}},
            "results": list(issues),
        }
    )


def write_file(tmp_path, name, content="x = 1\n"):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def analyze_with(
    tmp_path,
    execution,
    targets=("pkg/mod.py",),
    files=("pkg/mod.py",),
):
    for name in files:
        write_file(tmp_path, name)
    executor = FakeExecutor(execution)
    adapter = BanditAdapter(ToolRunner(executor=executor))
    result = adapter.analyze(str(tmp_path), list(targets))
    return result, executor


class TestCommandConstruction:
    def test_command_is_explicit_argument_list(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed(report()))
        assert executor.requests[0].command == [
            "bandit",
            "-f",
            "json",
            "pkg/mod.py",
        ]

    def test_no_recursive_flag_and_no_exit_zero(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed(report()))
        command = executor.requests[0].command
        assert "-r" not in command
        assert "--exit-zero" not in command
        assert "." not in command

    def test_cwd_is_repository_directory(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed(report()))
        assert executor.requests[0].cwd == os.path.realpath(str(tmp_path))

    def test_custom_executable_used(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor(completed(report()))
        adapter = BanditAdapter(
            ToolRunner(executor=executor),
            executable="/opt/tools/bandit",
        )
        adapter.analyze(str(tmp_path), ["pkg/mod.py"])
        assert executor.requests[0].command[0] == "/opt/tools/bandit"

    def test_multiple_targets_keep_order(self, tmp_path):
        result, executor = analyze_with(
            tmp_path,
            completed(report()),
            targets=("pkg/mod.py", "app.py"),
            files=("pkg/mod.py", "app.py"),
        )
        command = executor.requests[0].command
        assert command[-2:] == ["pkg/mod.py", "app.py"]

    def test_all_arguments_are_strings(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed(report()))
        assert all(
            isinstance(argument, str)
            for argument in executor.requests[0].command
        )


class TestExecutionStatusMapping:
    def test_tool_not_found(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.tool is StaticAnalysisTool.BANDIT
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
    def test_exit_code_zero_without_issues(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 0
        assert result.findings == []

    def test_exit_code_one_with_issues_is_ok(self, tmp_path):
        execution = completed(
            report(issue()), exit_code=1
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 1
        assert len(result.findings) == 1

    def test_exit_code_one_with_empty_results_is_ok(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    def test_other_exit_code_is_process_failed(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=2)
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.exit_code == 2
        assert result.findings == []

    def test_other_exit_code_with_issues_still_failed(self, tmp_path):
        execution = completed(report(issue()), exit_code=2)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.findings == []

    def test_parse_failure_keeps_exit_code(self, tmp_path):
        execution = completed("not json", exit_code=1)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.exit_code == 1


class TestSuccessMapping:
    def test_no_issues_gives_empty_findings(self, tmp_path):
        result, _ = analyze_with(tmp_path, completed(report()))
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []
        assert result.error_code is None
        assert result.duration_ms == 12

    def test_single_issue_field_mapping(self, tmp_path):
        entry = issue(
            test_id="B608",
            issue_text="Possible SQL injection vector.",
            filename="pkg/mod.py",
            line_number=5,
            issue_severity="MEDIUM",
            issue_confidence="HIGH",
            line_range=[5, 6, 7],
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        finding = result.findings[0]
        assert finding.tool is StaticAnalysisTool.BANDIT
        assert finding.rule_id == "B608"
        assert finding.message == "Possible SQL injection vector."
        assert finding.category is Category.SECURITY
        assert finding.severity is Severity.MEDIUM
        assert finding.file_path == "pkg/mod.py"
        assert finding.start_line == 5
        assert finding.end_line == 7

    def test_multiple_issues_keep_order(self, tmp_path):
        entries = [
            issue(test_id="B101", line_number=1, line_range=[1]),
            issue(
                test_id="B404",
                issue_text="Consider possible security implications.",
                line_number=10,
                line_range=[10],
            ),
            issue(
                test_id="B602",
                issue_text="Subprocess with shell=True.",
                line_number=20,
                line_range=[20],
                issue_severity="HIGH",
            ),
        ]
        result, _ = analyze_with(
            tmp_path, completed(report(*entries))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert [finding.rule_id for finding in result.findings] == [
            "B101",
            "B404",
            "B602",
        ]
        assert [finding.start_line for finding in result.findings] == [
            1,
            10,
            20,
        ]

    def test_rule_id_and_message_preserved(self, tmp_path):
        entry = issue(
            test_id="B303",
            issue_text="Use of insecure MD2, MD4, MD5 or SHA1 hash.",
        )
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].rule_id == "B303"
        assert (
            result.findings[0].message
            == "Use of insecure MD2, MD4, MD5 or SHA1 hash."
        )


class TestSeverityMapping:
    @pytest.mark.parametrize(
        ("issue_severity", "expected"),
        [
            ("LOW", Severity.LOW),
            ("MEDIUM", Severity.MEDIUM),
            ("HIGH", Severity.HIGH),
        ],
    )
    def test_severity_maps_directly(
        self, tmp_path, issue_severity, expected
    ):
        entry = issue(issue_severity=issue_severity)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].severity is expected

    @pytest.mark.parametrize(
        "issue_severity",
        ["CRITICAL", "high", "High", "", "UNKNOWN"],
    )
    def test_invalid_severity_is_schema_mismatch(
        self, tmp_path, issue_severity
    ):
        entry = issue(issue_severity=issue_severity)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_missing_severity_is_schema_mismatch(self, tmp_path):
        entry = issue()
        del entry["issue_severity"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize(
        "issue_severity", ["LOW", "MEDIUM", "HIGH"]
    )
    def test_category_is_always_security(
        self, tmp_path, issue_severity
    ):
        entry = issue(issue_severity=issue_severity)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].category is Category.SECURITY


class TestConfidenceHandling:
    @pytest.mark.parametrize(
        "issue_confidence", ["LOW", "MEDIUM", "HIGH"]
    )
    def test_valid_confidence_accepted(self, tmp_path, issue_confidence):
        entry = issue(issue_confidence=issue_confidence)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert len(result.findings) == 1

    @pytest.mark.parametrize(
        "issue_confidence", ["UNKNOWN", "low", "", "CRITICAL"]
    )
    def test_invalid_confidence_is_schema_mismatch(
        self, tmp_path, issue_confidence
    ):
        entry = issue(issue_confidence=issue_confidence)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_missing_confidence_is_schema_mismatch(self, tmp_path):
        entry = issue()
        del entry["issue_confidence"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_confidence_is_not_exposed_on_finding(self, tmp_path):
        entry = issue(issue_confidence="LOW")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        finding = result.findings[0]
        assert not hasattr(finding, "confidence")
        assert "confidence" not in StaticAnalysisFinding.model_fields
        assert "issue_confidence" not in result.model_dump_json()

    def test_confidence_does_not_change_severity(self, tmp_path):
        low = issue(
            line_number=1, issue_severity="HIGH",
            issue_confidence="LOW",
        )
        high = issue(
            line_number=2, issue_severity="HIGH",
            issue_confidence="HIGH",
        )
        result, _ = analyze_with(
            tmp_path, completed(report(low, high))
        )
        assert result.findings[0].severity is Severity.HIGH
        assert result.findings[1].severity is Severity.HIGH


class TestLineNumbers:
    def test_start_line_from_line_number(self, tmp_path):
        entry = issue(line_number=9, line_range=[9])
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].start_line == 9

    def test_line_range_max_is_end_line(self, tmp_path):
        entry = issue(line_number=3, line_range=[3, 4, 5])
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].end_line == 5

    def test_single_line_range(self, tmp_path):
        entry = issue(line_number=3, line_range=[3])
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].end_line == 3

    def test_missing_line_range_falls_back_to_start(self, tmp_path):
        entry = issue(line_number=7, line_range=None)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].start_line == 7
        assert result.findings[0].end_line == 7

    def test_empty_line_range_falls_back_to_start(self, tmp_path):
        entry = issue(line_number=7, line_range=[])
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].end_line == 7

    @pytest.mark.parametrize(
        "line_range", [[0], [-1, 2], [0, 1]]
    )
    def test_non_positive_line_range_entry_rejected(
        self, tmp_path, line_range
    ):
        entry = issue(line_number=1, line_range=line_range)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize(
        "line_range", [["3"], [1.5], [True]]
    )
    def test_non_integer_line_range_rejected(
        self, tmp_path, line_range
    ):
        entry = issue(line_number=1, line_range=line_range)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_line_range_before_start_rejected(self, tmp_path):
        entry = issue(line_number=10, line_range=[1, 2])
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize("line_number", [0, -1, "1", 1.0, True])
    def test_invalid_line_number_rejected(
        self, tmp_path, line_number
    ):
        entry = issue(line_number=line_number)
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
        stdout = json.dumps({"errors": []})
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_results_wrong_type_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps({"errors": [], "results": {}})
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_errors_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps({"results": []})
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_errors_wrong_type_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps({"errors": "boom", "results": []})
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_scan_errors_reject_whole_run(self, tmp_path):
        execution = completed(
            report(
                issue(),
                errors=[
                    {
                        "filename": "pkg/mod.py",
                        "reason": "syntax error while parsing AST",
                    }
                ],
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    def test_scan_errors_without_results_rejected(self, tmp_path):
        execution = completed(
            report(errors=[{"reason": "unable to parse"}])
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.findings == []

    def test_result_entry_not_object_is_schema_mismatch(self, tmp_path):
        execution = completed(
            stdout=json.dumps(
                {"errors": [], "results": [42]}
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_test_id_is_schema_mismatch(self, tmp_path):
        entry = issue()
        del entry["test_id"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("test_id", ["", "   "])
    def test_blank_test_id_is_schema_mismatch(
        self, tmp_path, test_id
    ):
        entry = issue(test_id=test_id)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("test_id", [123, None])
    def test_non_string_test_id_is_schema_mismatch(
        self, tmp_path, test_id
    ):
        entry = issue(test_id=test_id)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_issue_text_is_schema_mismatch(self, tmp_path):
        entry = issue()
        del entry["issue_text"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("issue_text", ["", "   "])
    def test_blank_issue_text_is_schema_mismatch(
        self, tmp_path, issue_text
    ):
        entry = issue(issue_text=issue_text)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_non_string_issue_text_is_schema_mismatch(self, tmp_path):
        entry = issue(issue_text=42)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_line_number_is_schema_mismatch(self, tmp_path):
        entry = issue()
        del entry["line_number"]
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_one_bad_entry_invalidates_whole_run(self, tmp_path):
        entries = [issue(test_id="B101"), {"test_id": "B404"}]
        result, _ = analyze_with(
            tmp_path, completed(report(*entries))
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_truncated_stdout_is_rejected(self, tmp_path):
        execution = completed(
            report(issue()), stdout_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    def test_truncated_stdout_with_incomplete_json_rejected(
        self, tmp_path
    ):
        execution = completed(
            stdout='{"results": [{"test_id": "B101"',
            stdout_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_truncated_stderr_alone_is_accepted(self, tmp_path):
        execution = completed(
            report(issue()), stderr_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert len(result.findings) == 1


class TestFilePathMapping:
    def test_relative_path_kept(self, tmp_path):
        entry = issue(filename="pkg/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_backslash_path_normalized(self, tmp_path):
        entry = issue(filename="pkg\\mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_dot_slash_prefix_normalized(self, tmp_path):
        entry = issue(filename="./pkg/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_absolute_path_inside_repo_normalized(self, tmp_path):
        absolute = os.path.join(str(tmp_path), "pkg", "mod.py")
        entry = issue(filename=absolute)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    @pytest.mark.parametrize(
        "filename",
        [
            "../outside.py",
            "pkg/../../outside.py",
            "..\\outside.py",
            "",
            "   ",
        ],
    )
    def test_traversal_or_blank_filename_rejected(
        self, tmp_path, filename
    ):
        entry = issue(filename=filename)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_absolute_path_outside_repo_rejected(self, tmp_path):
        outside = os.path.join(
            os.path.dirname(str(tmp_path)), "outside.py"
        )
        entry = issue(filename=outside)
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_drive_absolute_path_rejected(self, tmp_path):
        entry = issue(filename="C:/repo/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_unrequested_file_rejected(self, tmp_path):
        entry = issue(filename="other.py")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )


class TestInputValidation:
    def test_blank_repo_dir_rejected(self, tmp_path):
        adapter = BanditAdapter(ToolRunner(executor=FakeExecutor()))
        for repo_dir in ("", "   "):
            with pytest.raises(ValueError):
                adapter.analyze(repo_dir, ["pkg/mod.py"])

    def test_missing_repo_dir_rejected(self, tmp_path):
        adapter = BanditAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(
                os.path.join(str(tmp_path), "missing"), ["pkg/mod.py"]
            )

    def test_empty_targets_rejected(self, tmp_path):
        adapter = BanditAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [])

    def test_string_targets_rejected(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        adapter = BanditAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), "pkg/mod.py")

    def test_none_targets_rejected(self, tmp_path):
        adapter = BanditAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), None)

    def test_absolute_target_rejected(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        absolute = os.path.join(str(tmp_path), "pkg", "mod.py")
        executor = FakeExecutor()
        adapter = BanditAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [absolute])
        assert executor.requests == []

    def test_drive_target_rejected(self, tmp_path):
        executor = FakeExecutor()
        adapter = BanditAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), ["C:/repo/mod.py"])
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
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor()
        adapter = BanditAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [target])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target", ["notes.md", "mod.PY", "archive.py.bak"]
    )
    def test_non_python_target_rejected(self, tmp_path, target):
        executor = FakeExecutor()
        adapter = BanditAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [target])
        assert executor.requests == []

    def test_missing_target_file_rejected(self, tmp_path):
        executor = FakeExecutor()
        adapter = BanditAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), ["pkg/missing.py"])
        assert executor.requests == []

    def test_pyi_target_accepted(self, tmp_path):
        result, executor = analyze_with(
            tmp_path,
            completed(report()),
            targets=("pkg/stub.pyi",),
            files=("pkg/stub.pyi",),
        )
        assert executor.requests[0].command[-1] == "pkg/stub.pyi"

    def test_backslash_input_normalized(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor(completed(report()))
        adapter = BanditAdapter(ToolRunner(executor=executor))
        adapter.analyze(str(tmp_path), ["pkg\\mod.py"])
        assert executor.requests[0].command[-1] == "pkg/mod.py"

    def test_duplicate_targets_deduplicated(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor(completed(report()))
        adapter = BanditAdapter(ToolRunner(executor=executor))
        adapter.analyze(str(tmp_path), ["pkg/mod.py", "pkg/mod.py"])
        command = executor.requests[0].command
        assert command.count("pkg/mod.py") == 1

    @pytest.mark.parametrize("executable", ["", "   "])
    def test_blank_executable_rejected(self, executable):
        with pytest.raises(ValueError):
            BanditAdapter(
                ToolRunner(executor=FakeExecutor()),
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

    def test_scan_error_reason_not_exposed(self, tmp_path):
        execution = completed(
            report(
                errors=[
                    {
                        "filename": "pkg/mod.py",
                        "reason": "sensitive-scan-error-reason",
                    }
                ]
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert "sensitive-scan-error-reason" not in result.model_dump_json()

    def test_issue_text_only_in_findings(self, tmp_path):
        entry = issue(issue_text="Use of assert detected.")
        result, _ = analyze_with(
            tmp_path, completed(report(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].message == "Use of assert detected."


class TestResultContract:
    def test_ok_result_has_no_error_code(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(issue()))
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

    def test_findings_all_carry_bandit_tool(self, tmp_path):
        entries = [issue(test_id="B101"), issue(test_id="B602")]
        result, _ = analyze_with(
            tmp_path, completed(report(*entries))
        )
        assert all(
            finding.tool is StaticAnalysisTool.BANDIT
            for finding in result.findings
        )

    def test_ok_result_with_findings_round_trips(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(issue()))
        )
        recreated = type(result).model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result