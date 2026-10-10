"""Tests for the Phase 7.1 static analysis data contract.

Synthetic data only: no DeepSeek, no network, no external tools.
"""

import pytest
from pydantic import ValidationError

from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)


def finding_data(**overrides):
    data = {
        "tool": StaticAnalysisTool.RUFF,
        "rule_id": "F401",
        "category": Category.QUALITY,
        "severity": Severity.LOW,
        "message": "Unused import.",
        "file_path": "agent/app/main.py",
        "start_line": 3,
        "end_line": 3,
    }
    data.update(overrides)
    return data


def make_finding(**overrides):
    return StaticAnalysisFinding(**finding_data(**overrides))


def result_data(**overrides):
    data = {
        "tool": StaticAnalysisTool.RUFF,
        "status": StaticAnalysisStatus.OK,
        "findings": [],
        "exit_code": 0,
        "duration_ms": 25,
    }
    data.update(overrides)
    return data


def make_result(**overrides):
    return StaticAnalysisResult(**result_data(**overrides))


NON_OK_STATUSES = [
    StaticAnalysisStatus.UNAVAILABLE,
    StaticAnalysisStatus.TIMEOUT,
    StaticAnalysisStatus.ERROR,
    StaticAnalysisStatus.PARSE_ERROR,
]


class TestToolEnum:
    def test_exact_tool_values(self):
        assert {tool.value for tool in StaticAnalysisTool} == {
            "RUFF",
            "BANDIT",
            "SEMGREP",
            "PMD",
            "CHECKSTYLE",
        }

    @pytest.mark.parametrize("tool", list(StaticAnalysisTool))
    def test_every_tool_finding_is_valid(self, tool):
        finding = make_finding(tool=tool)
        assert finding.tool is tool

    @pytest.mark.parametrize("tool", list(StaticAnalysisTool))
    def test_every_tool_result_is_valid(self, tool):
        result = make_result(tool=tool)
        assert result.tool is tool

    def test_unknown_tool_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(tool="SONARQUBE")

    def test_tool_is_string_enum(self):
        assert StaticAnalysisTool.RUFF == "RUFF"


class TestStatusEnum:
    def test_exact_status_values(self):
        assert {status.value for status in StaticAnalysisStatus} == {
            "OK",
            "UNAVAILABLE",
            "TIMEOUT",
            "ERROR",
            "PARSE_ERROR",
        }

    def test_unknown_status_rejected(self):
        with pytest.raises(ValidationError):
            make_result(status="SKIPPED")

    @pytest.mark.parametrize("status", NON_OK_STATUSES)
    def test_every_non_ok_status_accepts_a_safe_error_code(self, status):
        result = make_result(
            status=status,
            findings=[],
            error_code=StaticAnalysisErrorCode.UNKNOWN,
        )
        assert result.status is status

    def test_exact_error_code_values(self):
        assert {code.value for code in StaticAnalysisErrorCode} == {
            "TOOL_NOT_FOUND",
            "SPAWN_FAILED",
            "TIMEOUT",
            "PROCESS_FAILED",
            "INVALID_OUTPUT",
            "SCHEMA_MISMATCH",
            "UNKNOWN",
        }

    @pytest.mark.parametrize("error_code", list(StaticAnalysisErrorCode))
    def test_every_error_code_value_is_accepted(self, error_code):
        result = make_result(
            status=StaticAnalysisStatus.ERROR,
            findings=[],
            error_code=error_code,
        )
        assert result.error_code is error_code

    def test_unknown_error_code_rejected(self):
        with pytest.raises(ValidationError):
            make_result(
                status=StaticAnalysisStatus.ERROR,
                findings=[],
                error_code="STACK_TRACE_INCLUDED",
            )


class TestFindingRequiredFields:
    def test_missing_required_field_rejected(self):
        for field in (
            "tool",
            "rule_id",
            "category",
            "severity",
            "message",
            "file_path",
            "start_line",
            "end_line",
        ):
            data = finding_data()
            del data[field]
            with pytest.raises(ValidationError):
                StaticAnalysisFinding(**data)

    def test_valid_finding_keeps_values(self):
        finding = make_finding()
        assert finding.rule_id == "F401"
        assert finding.category is Category.QUALITY
        assert finding.severity is Severity.LOW
        assert finding.start_line == 3
        assert finding.end_line == 3


class TestRuleIdAndMessage:
    @pytest.mark.parametrize("field", ["rule_id", "message"])
    @pytest.mark.parametrize("value", ["", " ", "   ", "\t", " \n "])
    def test_blank_value_rejected(self, field, value):
        with pytest.raises(ValidationError):
            make_finding(**{field: value})

    @pytest.mark.parametrize("field", ["rule_id", "message"])
    def test_missing_value_rejected(self, field):
        data = finding_data()
        del data[field]
        with pytest.raises(ValidationError):
            StaticAnalysisFinding(**data)

    def test_normal_value_accepted(self):
        finding = make_finding(rule_id="B608", message="Possible SQL injection")
        assert finding.rule_id == "B608"
        assert finding.message == "Possible SQL injection"


class TestLineNumbers:
    def test_start_line_one_valid(self):
        assert make_finding(start_line=1, end_line=1).start_line == 1

    def test_start_line_zero_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(start_line=0, end_line=0)

    def test_start_line_negative_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(start_line=-3, end_line=1)

    def test_end_line_equal_to_start_line_valid(self):
        finding = make_finding(start_line=7, end_line=7)
        assert finding.end_line == 7

    def test_end_line_greater_than_start_line_valid(self):
        finding = make_finding(start_line=7, end_line=12)
        assert finding.end_line == 12

    def test_end_line_smaller_than_start_line_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(start_line=10, end_line=9)

    def test_end_line_zero_with_start_line_one_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(start_line=1, end_line=0)

    def test_missing_line_fields_rejected(self):
        for field in ("start_line", "end_line"):
            data = finding_data()
            del data[field]
            with pytest.raises(ValidationError):
                StaticAnalysisFinding(**data)


class TestFilePath:
    @pytest.mark.parametrize(
        "path",
        [
            "File.py",
            "src/Main.java",
            "a/b/c/d.py",
            "agent/app/schemas/static_analysis.py",
            "dir with space/File One.java",
            "dir/name.d/File.java",
            "src\\Main.java",
        ],
    )
    def test_valid_relative_path_accepted(self, path):
        assert make_finding(file_path=path).file_path == path

    @pytest.mark.parametrize(
        "path",
        [
            "",
            " ",
            "   ",
            " src/Main.java",
            "src/Main.java ",
            "/etc/passwd",
            "/src/Main.java",
            "\\src\\Main.java",
            "\\\\server\\share\\x.py",
            "C:\\repo\\Main.java",
            "c:/repo/Main.java",
            "C:Main.java",
            "../secret.py",
            "..\\secret.py",
            "a/../b.py",
            "a\\..\\b.py",
            "..",
            "src/..",
            "a/../../b.py",
        ],
    )
    def test_invalid_path_rejected(self, path):
        with pytest.raises(ValidationError):
            make_finding(file_path=path)

    def test_missing_file_path_rejected(self):
        data = finding_data()
        del data["file_path"]
        with pytest.raises(ValidationError):
            StaticAnalysisFinding(**data)


class TestCategoryAndSeverityReuse:
    def test_values_are_review_enums(self):
        finding = make_finding()
        assert isinstance(finding.category, Category)
        assert isinstance(finding.severity, Severity)

    def test_all_review_categories_accepted(self):
        for category in Category:
            assert make_finding(category=category).category is category

    def test_all_review_severities_accepted(self):
        for severity in Severity:
            assert make_finding(severity=severity).severity is severity

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(category="STYLE")

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValidationError):
            make_finding(severity="EXTREME")


class TestResultRequiredFields:
    def test_missing_required_field_rejected(self):
        for field in ("tool", "status"):
            data = result_data()
            del data[field]
            with pytest.raises(ValidationError):
                StaticAnalysisResult(**data)

    def test_findings_none_rejected(self):
        with pytest.raises(ValidationError):
            make_result(findings=None)


class TestStatusContract:
    def test_ok_with_empty_findings_is_valid(self):
        result = make_result(findings=[])
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    def test_ok_with_findings_is_valid(self):
        result = make_result(findings=[make_finding()])
        assert len(result.findings) == 1

    def test_ok_rejects_error_code(self):
        with pytest.raises(ValidationError):
            make_result(
                status=StaticAnalysisStatus.OK,
                error_code=StaticAnalysisErrorCode.UNKNOWN,
            )

    @pytest.mark.parametrize("status", NON_OK_STATUSES)
    def test_non_ok_requires_error_code(self, status):
        with pytest.raises(ValidationError):
            make_result(status=status, findings=[], error_code=None)

    @pytest.mark.parametrize("status", NON_OK_STATUSES)
    def test_non_ok_rejects_findings(self, status):
        with pytest.raises(ValidationError):
            make_result(
                status=status,
                error_code=StaticAnalysisErrorCode.UNKNOWN,
                findings=[make_finding()],
            )

    @pytest.mark.parametrize("status", NON_OK_STATUSES)
    def test_non_ok_without_findings_is_valid(self, status):
        result = make_result(
            status=status,
            error_code=StaticAnalysisErrorCode.UNKNOWN,
            findings=[],
        )
        assert result.findings == []

    def test_unavailable_with_tool_not_found(self):
        result = make_result(
            status=StaticAnalysisStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
            exit_code=None,
            duration_ms=None,
        )
        assert result.exit_code is None
        assert result.duration_ms is None

    def test_parse_error_with_invalid_output(self):
        result = make_result(
            status=StaticAnalysisStatus.PARSE_ERROR,
            error_code=StaticAnalysisErrorCode.INVALID_OUTPUT,
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR


class TestExitCodeAndStatus:
    def test_ok_with_nonzero_exit_code_and_findings(self):
        result = make_result(exit_code=1, findings=[make_finding()])
        assert result.exit_code == 1
        assert len(result.findings) == 1

    def test_ok_with_nonzero_exit_code_and_empty_findings(self):
        result = make_result(exit_code=2, findings=[])
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    def test_error_status_with_nonzero_exit_code(self):
        result = make_result(
            status=StaticAnalysisStatus.ERROR,
            error_code=StaticAnalysisErrorCode.PROCESS_FAILED,
            exit_code=2,
            findings=[],
        )
        assert result.exit_code == 2

    def test_timed_out_run_with_exit_code(self):
        result = make_result(
            status=StaticAnalysisStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
            exit_code=None,
            findings=[],
        )
        assert result.exit_code is None

    def test_exit_code_optional(self):
        result = make_result(exit_code=None)
        assert result.exit_code is None

    def test_negative_exit_code_accepted(self):
        result = make_result(exit_code=-9)
        assert result.exit_code == -9


class TestDurationMs:
    def test_duration_none_accepted(self):
        assert make_result(duration_ms=None).duration_ms is None

    def test_duration_zero_accepted(self):
        assert make_result(duration_ms=0).duration_ms == 0

    def test_duration_positive_accepted(self):
        assert make_result(duration_ms=1234).duration_ms == 1234

    def test_duration_negative_rejected(self):
        with pytest.raises(ValidationError):
            make_result(duration_ms=-1)


class TestToolConsistency:
    def test_finding_tool_must_match_result_tool(self):
        with pytest.raises(ValidationError):
            make_result(
                tool=StaticAnalysisTool.RUFF,
                findings=[make_finding(tool=StaticAnalysisTool.BANDIT)],
            )

    @pytest.mark.parametrize("tool", list(StaticAnalysisTool))
    def test_matching_tool_accepted(self, tool):
        result = make_result(tool=tool, findings=[make_finding(tool=tool)])
        assert result.findings[0].tool is tool

    def test_multiple_findings_with_matching_tool_accepted(self):
        findings = [
            make_finding(rule_id="F401"),
            make_finding(rule_id="E501", start_line=10, end_line=10),
        ]
        result = make_result(findings=findings)
        assert len(result.findings) == 2


class TestSerialization:
    def test_ok_result_model_dump_values(self):
        result = make_result(findings=[make_finding()])
        dumped = result.model_dump()
        assert dumped["tool"] == "RUFF"
        assert dumped["status"] == "OK"
        assert dumped["error_code"] is None
        assert dumped["exit_code"] == 0
        assert dumped["findings"][0]["file_path"] == "agent/app/main.py"

    def test_ok_result_round_trips_via_model_validate(self):
        result = make_result(findings=[make_finding()])
        recreated = StaticAnalysisResult.model_validate(result.model_dump())
        assert recreated == result

    def test_ok_result_round_trips_via_json(self):
        result = make_result(findings=[make_finding()])
        recreated = StaticAnalysisResult.model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result

    def test_non_ok_result_round_trips_via_json(self):
        result = make_result(
            status=StaticAnalysisStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
            exit_code=None,
            duration_ms=30000,
        )
        dumped = result.model_dump()
        assert dumped["status"] == "TIMEOUT"
        assert dumped["error_code"] == "TIMEOUT"
        recreated = StaticAnalysisResult.model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result

    def test_finding_round_trips_via_json(self):
        finding = make_finding()
        recreated = StaticAnalysisFinding.model_validate_json(
            finding.model_dump_json()
        )
        assert recreated == finding

    def test_finding_has_no_confidence_field(self):
        assert "confidence" not in StaticAnalysisFinding.model_fields

    def test_result_field_names(self):
        assert set(StaticAnalysisResult.model_fields) == {
            "tool",
            "status",
            "findings",
            "exit_code",
            "duration_ms",
            "error_code",
        }