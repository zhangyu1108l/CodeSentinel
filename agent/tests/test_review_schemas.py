"""Tests for review DTO schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)


def make_finding(**overrides):
    data = {
        "category": Category.QUALITY,
        "severity": Severity.LOW,
        "confidence": 0.5,
        "rule_id": "MOCK-001",
        "title": "Mock review finding",
        "file_path": "mock/Example.java",
        "start_line": 1,
        "end_line": 1,
        "description": "description",
        "reason": "reason",
        "suggestion": "suggestion",
        "references": ["MOCK"],
    }
    data.update(overrides)
    return data


def make_request(**overrides):
    data = {
        "task_id": 1,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "files": [],
    }
    data.update(overrides)
    return data


class TestCategory:
    def test_valid_categories(self):
        assert {c.value for c in Category} == {
            "BUG",
            "SECURITY",
            "PERFORMANCE",
            "QUALITY",
        }

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            ReviewFinding(**make_finding(category="NOT_A_CATEGORY"))


class TestSeverity:
    def test_valid_severities(self):
        assert {s.value for s in Severity} == {
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW",
            "INFO",
        }

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValidationError):
            ReviewFinding(**make_finding(severity="EXTREME"))


class TestConfidence:
    def test_confidence_zero_is_valid(self):
        finding = ReviewFinding(**make_finding(confidence=0))
        assert finding.confidence == 0

    def test_confidence_one_is_valid(self):
        finding = ReviewFinding(**make_finding(confidence=1))
        assert finding.confidence == 1

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            ReviewFinding(**make_finding(confidence=-0.1))

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            ReviewFinding(**make_finding(confidence=1.1))


class TestRequiredFields:
    def test_finding_missing_required_field_rejected(self):
        for field in (
            "category",
            "severity",
            "confidence",
            "rule_id",
            "title",
            "file_path",
            "start_line",
            "end_line",
            "description",
            "reason",
            "suggestion",
            "references",
        ):
            data = make_finding()
            del data[field]
            with pytest.raises(ValidationError):
                ReviewFinding(**data)

    def test_request_missing_required_field_rejected(self):
        for field in ("task_id", "repository", "pr_number", "commit_sha"):
            data = make_request()
            del data[field]
            with pytest.raises(ValidationError):
                ReviewTaskRequest(**data)


class TestReviewTaskRequest:
    def test_valid_request_with_default_files(self):
        request = ReviewTaskRequest(**make_request())
        assert request.task_id == 1
        assert request.repository == "owner/repo"
        assert request.files == []

    def test_valid_request_with_files(self):
        request = ReviewTaskRequest(**make_request(files=["src/Main.java"]))
        assert request.files == ["src/Main.java"]
