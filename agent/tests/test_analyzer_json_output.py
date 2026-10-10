"""Tests for the Phase 7.2 JSON parsing boundary.

Synthetic text only: no external tool, no network.
"""

import pytest
from pydantic import ValidationError

from app.analyzers.json_output import (
    JsonParseResult,
    JsonStatus,
    parse_json_output,
)
from app.schemas.static_analysis import StaticAnalysisErrorCode


class TestJsonStatus:
    def test_exact_status_values(self):
        assert {status.value for status in JsonStatus} == {
            "VALID",
            "EMPTY",
            "INVALID",
        }


class TestParseJsonOutputValid:
    @pytest.mark.parametrize(
        "text",
        [
            "{}",
            "[]",
            '{"findings": []}',
            '[{"rule_id": "F401"}]',
            "42",
            "0",
            "-1.5",
            "true",
            "false",
            "null",
            '"plain string"',
            '{"nested": {"a": [1, 2, null]}}',
            '  {"a": 1}  ',
            '\n\t{"a": 1}\r\n',
            '{"message": "unused import"}',
        ],
    )
    def test_valid_json_returns_valid_status(self, text):
        result = parse_json_output(text)
        assert result.status is JsonStatus.VALID
        assert result.error_code is None

    def test_object_data_preserved(self):
        result = parse_json_output('{"findings": []}')
        assert result.data == {"findings": []}

    def test_array_data_preserved(self):
        result = parse_json_output('[{"check": "x"}]')
        assert result.data == [{"check": "x"}]

    def test_json_null_is_valid_with_none_data(self):
        result = parse_json_output("null")
        assert result.status is JsonStatus.VALID
        assert result.data is None

    def test_scalar_data_preserved(self):
        assert parse_json_output("42").data == 42
        assert parse_json_output('"x"').data == "x"
        assert parse_json_output("true").data is True

    def test_whitespace_around_document_tolerated(self):
        result = parse_json_output('  \n {"a": 1} \t ')
        assert result.status is JsonStatus.VALID
        assert result.data == {"a": 1}


class TestParseJsonOutputEmpty:
    @pytest.mark.parametrize("text", ["", " ", "   ", "\n", "\t", " \r\n "])
    def test_whitespace_only_is_empty(self, text):
        result = parse_json_output(text)
        assert result.status is JsonStatus.EMPTY
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.data is None


class TestParseJsonOutputInvalid:
    @pytest.mark.parametrize(
        "text",
        [
            "not json",
            "error: something failed",
            "Traceback (most recent call last):",
            "{",
            "}",
            '{"a":',
            '{"a": 1',
            "[1, 2",
            '{"a": 1} trailing',
            "1 2",
            "true false",
            "None",
            "True",
            "'single quotes'",
            '{"results": [{"check',
        ],
    )
    def test_non_json_text_is_invalid(self, text):
        result = parse_json_output(text)
        assert result.status is JsonStatus.INVALID
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.data is None

    def test_plain_text_never_becomes_valid(self):
        result = parse_json_output("0 findings found")
        assert result.status is not JsonStatus.VALID
        assert result.data is None

    def test_deeply_nested_document_is_invalid(self):
        text = "[" * 10000 + "]" * 10000
        result = parse_json_output(text)
        assert result.status is JsonStatus.INVALID
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_no_exception_text_exposed(self):
        result = parse_json_output('{"broken": ')
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert "broken" not in result.model_dump_json()


class TestJsonParseResultContract:
    def test_valid_with_error_code_rejected(self):
        with pytest.raises(ValidationError):
            JsonParseResult(
                status=JsonStatus.VALID,
                error_code=StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

    @pytest.mark.parametrize(
        "status", [JsonStatus.EMPTY, JsonStatus.INVALID]
    )
    def test_non_valid_without_error_code_rejected(self, status):
        with pytest.raises(ValidationError):
            JsonParseResult(status=status)

    @pytest.mark.parametrize(
        "status", [JsonStatus.EMPTY, JsonStatus.INVALID]
    )
    def test_non_valid_requires_invalid_output_code(self, status):
        with pytest.raises(ValidationError):
            JsonParseResult(
                status=status,
                error_code=StaticAnalysisErrorCode.UNKNOWN,
            )

    def test_serialization_round_trip(self):
        result = parse_json_output('{"findings": []}')
        recreated = JsonParseResult.model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result