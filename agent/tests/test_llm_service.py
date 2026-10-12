"""Tests for LLMService structured output handling."""

import asyncio
import json
import traceback
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.deepseek_client import DeepSeekClient
from app.llm.exceptions import LLMException, LLMResponseError
from app.llm.llm_service import LLMService
from app.schemas.review import Category, ReviewFinding, Severity

MESSAGES = [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "user prompt"},
]

VALID_FINDING = {
    "category": "SECURITY",
    "severity": "HIGH",
    "confidence": 0.9,
    "rule_id": "CWE-89",
    "title": "Potential SQL Injection",
    "file_path": "src/UserRepository.java",
    "start_line": 52,
    "end_line": 52,
    "description": "Potential SQL injection risk.",
    "reason": "External input is directly concatenated into SQL.",
    "suggestion": "Use parameterized queries.",
    "references": ["CWE-89"],
}


def make_service(content):
    client = MagicMock(spec=DeepSeekClient)
    client.chat = AsyncMock(return_value=content)
    return LLMService(deepseek_client=client)


class TestLLMService:
    def test_valid_json_returns_findings(self):
        service = make_service(
            json.dumps({"findings": [VALID_FINDING]})
        )
        findings = asyncio.run(service.generate_findings(MESSAGES))

        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, ReviewFinding)
        assert finding.category == Category.SECURITY
        assert finding.severity == Severity.HIGH
        assert finding.confidence == 0.9
        assert finding.rule_id == "CWE-89"

    def test_empty_findings(self):
        service = make_service('{"findings": []}')
        findings = asyncio.run(service.generate_findings(MESSAGES))
        assert findings == []

    def test_invalid_json_raises_response_error(self):
        service = make_service("not valid json")
        with pytest.raises(LLMResponseError, match="invalid JSON"):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_json_wrapped_in_markdown_raises_response_error(self):
        service = make_service('```json\n{"findings": []}\n```')
        with pytest.raises(LLMResponseError):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_missing_findings_key_raises_response_error(self):
        service = make_service("{}")
        with pytest.raises(LLMResponseError, match="schema validation"):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_confidence_out_of_range_raises_response_error(self):
        payload = json.dumps(
            {"findings": [{**VALID_FINDING, "confidence": 1.5}]}
        )
        service = make_service(payload)
        with pytest.raises(LLMResponseError):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_invalid_category_raises_response_error(self):
        payload = json.dumps(
            {"findings": [{**VALID_FINDING, "category": "NOTHING"}]}
        )
        service = make_service(payload)
        with pytest.raises(LLMResponseError):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_invalid_severity_raises_response_error(self):
        payload = json.dumps(
            {"findings": [{**VALID_FINDING, "severity": "EXTREME"}]}
        )
        service = make_service(payload)
        with pytest.raises(LLMResponseError):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_missing_finding_field_raises_response_error(self):
        broken = dict(VALID_FINDING)
        del broken["suggestion"]
        service = make_service(json.dumps({"findings": [broken]}))
        with pytest.raises(LLMResponseError):
            asyncio.run(service.generate_findings(MESSAGES))

    def test_client_exception_propagates(self):
        client = MagicMock(spec=DeepSeekClient)
        client.chat = AsyncMock(
            side_effect=LLMException("DeepSeek API error: HTTP 429")
        )
        service = LLMService(deepseek_client=client)
        with pytest.raises(LLMException, match="HTTP 429"):
            asyncio.run(service.generate_findings(MESSAGES))


SENTINEL = "SENTINEL-LLM-OUTPUT-DO-NOT-LOG"


class TestSchemaFailureStaysInputFree:
    def make_invalid_content(self):
        finding = dict(VALID_FINDING)
        finding["description"] = SENTINEL
        del finding["suggestion"]
        return json.dumps({"findings": [finding]})

    def test_error_message_and_log_hide_the_llm_output(self, caplog):
        service = make_service(self.make_invalid_content())
        with caplog.at_level(
            "ERROR", logger="codesentinel-ai.llm_service"
        ):
            with pytest.raises(LLMResponseError) as exc_info:
                asyncio.run(service.generate_findings(MESSAGES))

        message = str(exc_info.value)
        assert "LLM output failed schema validation" in message
        assert "findings.0.suggestion" in message
        assert "missing" in message
        assert SENTINEL not in message
        assert "input_value" not in message

        log_text = "\n".join(
            record.getMessage() for record in caplog.records
        )
        assert "findings.0.suggestion" in log_text
        assert SENTINEL not in log_text
        assert "input_value" not in log_text

    def test_traceback_does_not_leak_the_llm_output(self):
        service = make_service(self.make_invalid_content())
        with pytest.raises(LLMResponseError) as exc_info:
            asyncio.run(service.generate_findings(MESSAGES))

        text = "".join(traceback.format_exception(exc_info.value))
        assert SENTINEL not in text
        assert "ValidationError" not in text
