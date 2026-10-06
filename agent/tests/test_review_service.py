"""Tests for ReviewService mock generation."""

from app.schemas.review import (
    Category,
    ReviewTaskRequest,
    ReviewTaskResult,
    Severity,
)
from app.services.review_service import ReviewService


def make_request(**overrides):
    data = {
        "task_id": 1,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "files": [],
    }
    data.update(overrides)
    return ReviewTaskRequest(**data)


class TestReviewService:
    def setup_method(self):
        self.service = ReviewService()

    def test_returns_review_task_result(self):
        result = self.service.review(make_request())
        assert isinstance(result, ReviewTaskResult)

    def test_task_id_matches_input(self):
        result = self.service.review(make_request(task_id=77))
        assert result.task_id == 77

    def test_status_is_completed(self):
        result = self.service.review(make_request())
        assert result.status == "COMPLETED"

    def test_findings_not_empty(self):
        result = self.service.review(make_request())
        assert len(result.findings) >= 1

    def test_finding_fields_complete(self):
        finding = self.service.review(make_request()).findings[0]
        assert finding.category == Category.QUALITY
        assert finding.severity == Severity.LOW
        assert 0 <= finding.confidence <= 1
        assert finding.rule_id
        assert finding.title
        assert finding.file_path
        assert finding.start_line >= 1
        assert finding.end_line >= 1
        assert finding.description
        assert finding.reason
        assert finding.suggestion
        assert isinstance(finding.references, list)

    def test_mock_output_is_deterministic(self):
        first = self.service.review(make_request())
        second = self.service.review(make_request())
        assert first == second

    def test_finding_uses_first_file_when_files_provided(self):
        result = self.service.review(make_request(files=["src/Main.java"]))
        assert result.findings[0].file_path == "src/Main.java"

    def test_finding_uses_placeholder_when_files_empty(self):
        result = self.service.review(make_request(files=[]))
        assert result.findings[0].file_path == "mock/Example.java"
