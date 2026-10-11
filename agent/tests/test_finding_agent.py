"""Tests for the dimension specific finding agent (Phase 8.3)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.finding_agent import (
    IMPLEMENTED_AGENT_CATEGORIES,
    FindingAgent,
)
from app.llm.exceptions import LLMException
from app.llm.llm_service import LLMService
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)


def make_finding(category, title="title"):
    return ReviewFinding(
        category=category,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id="R1",
        title=title,
        file_path="a.py",
        start_line=1,
        end_line=1,
        description="description",
        reason="reason",
        suggestion="suggestion",
        references=[],
    )


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


class TestFindingAgent:
    def test_only_bug_category_is_implemented(self):
        assert IMPLEMENTED_AGENT_CATEGORIES == frozenset({Category.BUG})

    def test_unimplemented_categories_are_rejected(self):
        for category in (
            Category.SECURITY,
            Category.PERFORMANCE,
            Category.QUALITY,
        ):
            with pytest.raises(ValueError):
                FindingAgent(category)

    def test_keeps_only_its_own_category(self):
        llm = MagicMock(spec=LLMService)
        llm.generate_findings = AsyncMock(
            return_value=[
                make_finding(Category.BUG),
                make_finding(Category.SECURITY),
            ]
        )
        agent = FindingAgent(Category.BUG, llm_service=llm)

        findings = asyncio.run(agent.analyze(make_request()))

        assert [finding.category for finding in findings] == [
            Category.BUG
        ]
        assert llm.generate_findings.await_count == 1

    def test_empty_findings_are_returned_unchanged(self):
        llm = MagicMock(spec=LLMService)
        llm.generate_findings = AsyncMock(return_value=[])
        agent = FindingAgent(Category.BUG, llm_service=llm)

        assert asyncio.run(agent.analyze(make_request())) == []

    def test_prompt_carries_the_category_and_schema(self):
        llm = MagicMock(spec=LLMService)
        llm.generate_findings = AsyncMock(return_value=[])
        agent = FindingAgent(Category.BUG, llm_service=llm)

        asyncio.run(agent.analyze(make_request()))

        messages = llm.generate_findings.call_args[0][0]
        assert "BUG" in messages[0]["content"]
        assert '"findings"' in messages[0]["content"]
        assert "no file content" in messages[1]["content"]

    def test_llm_failure_propagates(self):
        llm = MagicMock(spec=LLMService)
        llm.generate_findings = AsyncMock(side_effect=LLMException("down"))
        agent = FindingAgent(Category.BUG, llm_service=llm)

        with pytest.raises(LLMException):
            asyncio.run(agent.analyze(make_request()))