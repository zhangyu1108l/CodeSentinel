"""Tests for ReviewService with mocked LLMService."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.exceptions import LLMException
from app.llm.llm_service import LLMService
from app.schemas.review import Category, ReviewFinding, Severity
from app.services.review_service import ReviewService

VALID_FINDING = ReviewFinding(
    category=Category.QUALITY,
    severity=Severity.LOW,
    confidence=0.5,
    rule_id="MOCK-001",
    title="Finding title",
    file_path="src/Main.java",
    start_line=1,
    end_line=1,
    description="description",
    reason="reason",
    suggestion="suggestion",
    references=["MOCK"],
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
    from app.schemas.review import ReviewTaskRequest

    return ReviewTaskRequest(**data)


def make_llm(findings=None, error=None):
    llm = MagicMock(spec=LLMService)
    if error is not None:
        llm.generate_findings = AsyncMock(side_effect=error)
    else:
        llm.generate_findings = AsyncMock(return_value=findings or [])
    return llm


class TestReviewService:
    def setup_method(self):
        self.llm = make_llm()
        self.service = ReviewService(llm_service=self.llm)

    def test_returns_review_task_result(self):
        result = asyncio.run(self.service.review(make_request()))
        from app.schemas.review import ReviewTaskResult

        assert isinstance(result, ReviewTaskResult)

    def test_task_id_matches_input(self):
        result = asyncio.run(self.service.review(make_request(task_id=77)))
        assert result.task_id == 77

    def test_status_is_completed(self):
        result = asyncio.run(self.service.review(make_request()))
        assert result.status == "COMPLETED"

    def test_empty_files_returns_empty_findings(self):
        result = asyncio.run(self.service.review(make_request(files=[])))
        assert result.findings == []
        assert result.report["total_findings"] == 0

    def test_findings_come_from_llm_service(self):
        self.llm.generate_findings = AsyncMock(return_value=[VALID_FINDING])
        result = asyncio.run(self.service.review(make_request()))
        assert len(result.findings) == 1
        assert result.findings[0].rule_id == "MOCK-001"
        assert result.report["total_findings"] == 1

    def test_llm_receives_messages(self):
        asyncio.run(self.service.review(make_request()))
        self.llm.generate_findings.assert_called_once()
        messages = self.llm.generate_findings.call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "owner/repo" in messages[1]["content"]

    def test_report_summary_contains_repository(self):
        result = asyncio.run(self.service.review(make_request()))
        assert "owner/repo#42" in result.report["summary"]

    def test_llm_exception_propagates(self):
        service = ReviewService(
            llm_service=make_llm(error=LLMException("DeepSeek down"))
        )
        with pytest.raises(LLMException, match="DeepSeek down"):
            asyncio.run(service.review(make_request()))
