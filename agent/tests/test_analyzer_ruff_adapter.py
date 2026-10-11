"""Tests for the Phase 7.3 Ruff adapter.

A fake executor is injected everywhere: Ruff is never installed, started
or needed. All payloads are synthetic and no network is used.
"""

import json
import os

import pytest

from app.analyzers.execution import (
    CommandExecutionResult,
    ExecutionStatus,
)
from app.analyzers.ruff_adapter import RuffAdapter
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)


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


def diagnostic(
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


def payload(*diagnostics):
    return json.dumps(list(diagnostics))


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
    adapter = RuffAdapter(ToolRunner(executor=executor))
    result = adapter.analyze(str(tmp_path), list(targets))
    return result, executor


class TestCommandConstruction:
    def test_command_is_explicit_argument_list(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed())
        assert executor.requests[0].command == [
            "ruff",
            "check",
            "--output-format",
            "json",
            "--isolated",
            "--no-cache",
            "pkg/mod.py",
        ]

    def test_cwd_is_repository_directory(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed())
        assert executor.requests[0].cwd == os.path.realpath(str(tmp_path))

    def test_custom_executable_used(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor(completed())
        adapter = RuffAdapter(
            ToolRunner(executor=executor),
            executable="/opt/tools/ruff",
        )
        adapter.analyze(str(tmp_path), ["pkg/mod.py"])
        assert executor.requests[0].command[0] == "/opt/tools/ruff"

    def test_multiple_targets_keep_order(self, tmp_path):
        result, executor = analyze_with(
            tmp_path,
            completed(),
            targets=("pkg/mod.py", "app.py"),
            files=("pkg/mod.py", "app.py"),
        )
        command = executor.requests[0].command
        assert command[-2:] == ["pkg/mod.py", "app.py"]

    def test_no_directory_scan_argument(self, tmp_path):
        result, executor = analyze_with(tmp_path, completed())
        command = executor.requests[0].command
        assert "." not in command
        assert ".." not in command
        assert all(isinstance(argument, str) for argument in command)


class TestExecutionStatusMapping:
    def test_tool_not_found(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.tool is StaticAnalysisTool.RUFF
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
    def test_exit_code_zero_without_diagnostics(self, tmp_path):
        result, _ = analyze_with(tmp_path, completed(stdout="[]"))
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 0
        assert result.findings == []

    def test_exit_code_one_with_diagnostics_is_ok(self, tmp_path):
        execution = completed(
            stdout=payload(diagnostic()), exit_code=1
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 1
        assert len(result.findings) == 1

    def test_exit_code_one_with_empty_payload_is_ok(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(stdout="[]", exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    def test_other_exit_code_is_process_failed(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(stdout="[]", exit_code=2)
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.exit_code == 2
        assert result.findings == []

    def test_other_exit_code_with_payload_still_failed(self, tmp_path):
        execution = completed(
            stdout=payload(diagnostic()), exit_code=2
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    def test_parse_failure_keeps_exit_code(self, tmp_path):
        execution = completed(stdout="not json", exit_code=1)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.exit_code == 1


class TestSuccessMapping:
    def test_no_diagnostics_gives_empty_findings(self, tmp_path):
        result, _ = analyze_with(tmp_path, completed(stdout="[]"))
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []
        assert result.error_code is None
        assert result.duration_ms == 12

    def test_single_diagnostic_field_mapping(self, tmp_path):
        entry = diagnostic(
            code="B008",
            message="Do not perform function call in defaults",
            filename="pkg/mod.py",
            row=4,
            end_row=6,
        )
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        finding = result.findings[0]
        assert finding.tool is StaticAnalysisTool.RUFF
        assert finding.rule_id == "B008"
        assert finding.category is Category.BUG
        assert finding.severity is Severity.MEDIUM
        assert (
            finding.message
            == "Do not perform function call in defaults"
        )
        assert finding.file_path == "pkg/mod.py"
        assert finding.start_line == 4
        assert finding.end_line == 6

    def test_multiple_diagnostics_keep_order(self, tmp_path):
        entries = [
            diagnostic(code="F401", row=1, end_row=1),
            diagnostic(
                code="E501",
                message="Line too long",
                row=10,
                end_row=10,
            ),
            diagnostic(
                code="S105",
                message="Possible hardcoded password",
                row=20,
                end_row=20,
            ),
        ]
        result, _ = analyze_with(
            tmp_path, completed(payload(*entries))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert [finding.rule_id for finding in result.findings] == [
            "F401",
            "E501",
            "S105",
        ]
        assert [finding.start_line for finding in result.findings] == [
            1,
            10,
            20,
        ]

    def test_rule_id_and_message_preserved(self, tmp_path):
        entry = diagnostic(
            code="F821", message="Undefined name `foo`"
        )
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].rule_id == "F821"
        assert result.findings[0].message == "Undefined name `foo`"


class TestRuleMapping:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("S101", Category.SECURITY),
            ("S105", Category.SECURITY),
            ("S506", Category.SECURITY),
            ("B008", Category.BUG),
            ("B006", Category.BUG),
            ("BLE001", Category.BUG),
            ("TRY300", Category.BUG),
            ("PERF401", Category.PERFORMANCE),
            ("PERF102", Category.PERFORMANCE),
            ("F401", Category.QUALITY),
            ("F841", Category.QUALITY),
            ("E501", Category.QUALITY),
            ("W291", Category.QUALITY),
            ("I001", Category.QUALITY),
            ("UP035", Category.QUALITY),
            ("PLW0602", Category.QUALITY),
            ("RUF100", Category.QUALITY),
            ("C901", Category.QUALITY),
            ("N802", Category.QUALITY),
            ("D103", Category.QUALITY),
            ("T201", Category.QUALITY),
            ("F811", Category.BUG),
            ("F821", Category.BUG),
            ("F822", Category.BUG),
            ("F823", Category.BUG),
        ],
    )
    def test_category_mapping(self, tmp_path, code, expected):
        entry = diagnostic(code=code)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].category is expected

    def test_sim_prefix_is_not_security(self, tmp_path):
        entry = diagnostic(code="SIM102")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].category is Category.QUALITY

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("S101", Severity.HIGH),
            ("B008", Severity.MEDIUM),
            ("PERF401", Severity.LOW),
            ("F401", Severity.INFO),
            ("E501", Severity.INFO),
        ],
    )
    def test_severity_mapping(self, tmp_path, code, expected):
        entry = diagnostic(code=code)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].severity is expected


class TestParseFailures:
    @pytest.mark.parametrize(
        "stdout", ["", " ", "\n", "not json", "[] trailing"]
    )
    def test_non_json_output_is_parse_error(self, tmp_path, stdout):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    @pytest.mark.parametrize(
        "stdout",
        ["{}", "42", '"text"', "null", "[42]", '["a"]'],
    )
    def test_non_list_payload_is_schema_mismatch(
        self, tmp_path, stdout
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_missing_code_is_schema_mismatch(self, tmp_path):
        entry = diagnostic()
        del entry["code"]
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_null_code_is_schema_mismatch(self, tmp_path):
        entry = diagnostic(code=None)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("code", ["", "   "])
    def test_blank_code_is_schema_mismatch(self, tmp_path, code):
        entry = diagnostic(code=code)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_message_is_schema_mismatch(self, tmp_path):
        entry = diagnostic()
        del entry["message"]
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("message", ["", "   "])
    def test_blank_message_is_schema_mismatch(
        self, tmp_path, message
    ):
        entry = diagnostic(message=message)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_non_string_message_is_schema_mismatch(self, tmp_path):
        entry = diagnostic(message=42)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_location_is_schema_mismatch(self, tmp_path):
        entry = diagnostic()
        del entry["location"]
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_end_location_is_schema_mismatch(self, tmp_path):
        entry = diagnostic()
        del entry["end_location"]
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("row", [0, -1, "1", 1.0, True])
    def test_invalid_start_row_is_schema_mismatch(
        self, tmp_path, row
    ):
        entry = diagnostic(row=row, end_row=1)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_end_row_before_start_row_is_schema_mismatch(
        self, tmp_path
    ):
        entry = diagnostic(row=10, end_row=9)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_one_bad_entry_invalidates_whole_run(self, tmp_path):
        entries = [diagnostic(code="F401"), {"code": "E501"}]
        result, _ = analyze_with(
            tmp_path, completed(payload(*entries))
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_truncated_stdout_is_rejected(self, tmp_path):
        execution = completed(
            stdout=payload(diagnostic()), stdout_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    def test_truncated_stdout_with_incomplete_json_rejected(
        self, tmp_path
    ):
        execution = completed(
            stdout='[{"code": "F401",', stdout_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_truncated_stderr_alone_is_accepted(self, tmp_path):
        execution = completed(
            stdout=payload(diagnostic()), stderr_truncated=True
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert len(result.findings) == 1


class TestFilePathMapping:
    def test_relative_path_kept(self, tmp_path):
        entry = diagnostic(filename="pkg/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_backslash_path_normalized(self, tmp_path):
        entry = diagnostic(filename="pkg\\mod.py")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_dot_slash_prefix_normalized(self, tmp_path):
        entry = diagnostic(filename="./pkg/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.findings[0].file_path == "pkg/mod.py"

    def test_absolute_path_inside_repo_normalized(self, tmp_path):
        absolute = os.path.join(str(tmp_path), "pkg", "mod.py")
        entry = diagnostic(filename=absolute)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
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
        entry = diagnostic(filename=filename)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_absolute_path_outside_repo_rejected(self, tmp_path):
        outside = os.path.join(
            os.path.dirname(str(tmp_path)), "outside.py"
        )
        entry = diagnostic(filename=outside)
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_drive_absolute_path_rejected(self, tmp_path):
        entry = diagnostic(filename="C:/repo/mod.py")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_unrequested_file_rejected(self, tmp_path):
        entry = diagnostic(filename="other.py")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )


class TestInputValidation:
    def test_blank_repo_dir_rejected(self, tmp_path):
        adapter = RuffAdapter(ToolRunner(executor=FakeExecutor()))
        for repo_dir in ("", "   "):
            with pytest.raises(ValueError):
                adapter.analyze(repo_dir, ["pkg/mod.py"])

    def test_missing_repo_dir_rejected(self, tmp_path):
        adapter = RuffAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(
                os.path.join(str(tmp_path), "missing"), ["pkg/mod.py"]
            )

    def test_empty_targets_rejected(self, tmp_path):
        adapter = RuffAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [])

    def test_string_targets_rejected(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        adapter = RuffAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), "pkg/mod.py")

    def test_none_targets_rejected(self, tmp_path):
        adapter = RuffAdapter(ToolRunner(executor=FakeExecutor()))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), None)

    def test_absolute_target_rejected(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        absolute = os.path.join(str(tmp_path), "pkg", "mod.py")
        executor = FakeExecutor()
        adapter = RuffAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [absolute])
        assert executor.requests == []

    def test_drive_target_rejected(self, tmp_path):
        executor = FakeExecutor()
        adapter = RuffAdapter(ToolRunner(executor=executor))
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
        adapter = RuffAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [target])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target", ["notes.md", "mod.PY", "archive.py.bak"]
    )
    def test_non_python_target_rejected(self, tmp_path, target):
        executor = FakeExecutor()
        adapter = RuffAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [target])
        assert executor.requests == []

    def test_missing_target_file_rejected(self, tmp_path):
        executor = FakeExecutor()
        adapter = RuffAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), ["pkg/missing.py"])
        assert executor.requests == []

    @pytest.mark.parametrize("target", [" pkg/mod.py", "pkg/mod.py "])
    def test_padded_target_rejected(self, tmp_path, target):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor()
        adapter = RuffAdapter(ToolRunner(executor=executor))
        with pytest.raises(ValueError):
            adapter.analyze(str(tmp_path), [target])
        assert executor.requests == []

    def test_pyi_target_accepted(self, tmp_path):
        result, executor = analyze_with(
            tmp_path,
            completed(),
            targets=("pkg/stub.pyi",),
            files=("pkg/stub.pyi",),
        )
        assert executor.requests[0].command[-1] == "pkg/stub.pyi"

    def test_backslash_input_normalized(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor(completed())
        adapter = RuffAdapter(ToolRunner(executor=executor))
        adapter.analyze(str(tmp_path), ["pkg\\mod.py"])
        assert executor.requests[0].command[-1] == "pkg/mod.py"

    def test_duplicate_targets_deduplicated(self, tmp_path):
        write_file(tmp_path, "pkg/mod.py")
        executor = FakeExecutor(completed())
        adapter = RuffAdapter(ToolRunner(executor=executor))
        adapter.analyze(
            str(tmp_path), ["pkg/mod.py", "pkg/mod.py"]
        )
        command = executor.requests[0].command
        assert command[-1] == "pkg/mod.py"
        assert command.count("pkg/mod.py") == 1

    @pytest.mark.parametrize("executable", ["", "   "])
    def test_blank_executable_rejected(self, executable):
        with pytest.raises(ValueError):
            RuffAdapter(
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

    def test_message_content_only_in_findings(self, tmp_path):
        entry = diagnostic(message="Undefined name `token`")
        result, _ = analyze_with(
            tmp_path, completed(payload(entry))
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].message == "Undefined name `token`"


class TestResultContract:
    def test_ok_result_has_no_error_code(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(payload(diagnostic()))
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

    def test_findings_all_carry_ruff_tool(self, tmp_path):
        entries = [diagnostic(code="F401"), diagnostic(code="S101")]
        result, _ = analyze_with(
            tmp_path, completed(payload(*entries))
        )
        assert all(
            finding.tool is StaticAnalysisTool.RUFF
            for finding in result.findings
        )

    def test_ok_result_with_findings_round_trips(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(payload(diagnostic()))
        )
        recreated = type(result).model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result