"""Tests for ReviewService with mocked LLMService and context client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

from app.context.code_context_builder import CodeContextBuilder
from app.context.pr_context_client import PrContextClient
from app.llm.exceptions import LLMException
from app.llm.llm_service import LLMService
from app.prompts.review import build_messages
from app.schemas.code_context import ContextBudget
from app.schemas.pr_context import PrContext
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


JAVA_SOURCE = "\n".join(
    [
        "class A {",
        "    int helper() { return 1; }",
        "    int changed() { return 2; }",
        "}",
    ]
) + "\n"

JAVA_PATCH = "\n".join(
    [
        "@@ -2,3 +2,3 @@",
        "     int helper() { return 1; }",
        "-    int changed() { return 2; }",
        "+    int changed() { return 3; }",
        " }",
    ]
)


def make_pr_file(**overrides):
    data = {
        "path": "src/A.java",
        "previousPath": None,
        "status": "modified",
        "additions": 1,
        "deletions": 1,
        "changes": 2,
        "patch": JAVA_PATCH,
        "blobUrl": None,
        "content_available": True,
        "content_truncated": False,
        "content_reason": None,
        "content": JAVA_SOURCE,
    }
    data.update(overrides)
    return data


def make_pr_context(files=None):
    return PrContext.model_validate(
        {
            "taskId": 1,
            "owner": "owner",
            "repo": "repo",
            "prNumber": 42,
            "commitSha": "abc123",
            "title": "t",
            "state": "open",
            "baseRef": "main",
            "headRef": "feature/x",
            "files": files if files is not None else [make_pr_file()],
        }
    )


def make_context_client(return_value=None, error=None):
    client = MagicMock(spec=PrContextClient)
    if error is not None:
        client.fetch = AsyncMock(side_effect=error)
    else:
        client.fetch = AsyncMock(
            return_value=return_value
            if return_value is not None
            else make_pr_context()
        )
    return client


def http_error(status_code):
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=httpx.Request("GET", "http://localhost:8080"),
        response=httpx.Response(status_code),
    )


def make_context_service(llm=None, client=None, builder=None, budget=None):
    return ReviewService(
        llm_service=llm if llm is not None else make_llm(),
        pr_context_client=(
            client if client is not None else make_context_client()
        ),
        context_builder=builder,
        context_budget=budget,
    )


class TestReviewServiceContext:
    def test_normal_context_is_assembled_and_budgeted(self):
        llm = make_llm()
        client = make_context_client()
        service = ReviewService(llm_service=llm, pr_context_client=client)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        context = result.report["context"]
        assert context["available"] is True
        assert context["degraded"] is False
        assert context["reason"] is None
        assert context["file_count"] == 1
        assert context["files_with_content"] == 1
        assert context["estimated_tokens"] > 0
        assert context["truncated"] is False
        client.fetch.assert_awaited_once_with(1)
        llm.generate_findings.assert_awaited_once()

    def test_multi_file_context_summary(self):
        files = [
            make_pr_file(),
            make_pr_file(
                path="README.md",
                patch=None,
                content_available=False,
                content_reason="unsupported_language",
                content=None,
            ),
        ]
        service = make_context_service(
            client=make_context_client(make_pr_context(files))
        )

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        assert result.report["context"]["file_count"] == 2
        assert result.report["context"]["files_with_content"] == 1

    def test_prompt_contains_code_context(self):
        llm = make_llm()
        service = make_context_service(llm=llm)

        asyncio.run(service.review(make_request()))

        messages = llm.generate_findings.call_args[0][0]
        user = messages[1]["content"]
        assert "Code context provided by CodeSentinel" in user
        assert "src/A.java" in user
        assert "+    int changed() { return 3; }" in user
        assert "changed methods (touched by this diff):" in user
        assert "context_stats:" in user

    def test_prompt_marks_unavailable_content(self):
        files = [
            make_pr_file(),
            make_pr_file(
                path="README.md",
                patch=None,
                content_available=False,
                content_reason="unsupported_language",
                content=None,
            ),
        ]
        llm = make_llm()
        service = make_context_service(
            llm=llm,
            client=make_context_client(make_pr_context(files)),
        )

        asyncio.run(service.review(make_request()))

        user = llm.generate_findings.call_args[0][0][1]["content"]
        assert "content: unavailable (reason: unsupported_language)" in user
        assert "=== File 2/2: README.md ===" in user

    def test_prompt_declares_truncation(self):
        budget = ContextBudget(
            max_item_chars=10**6,
            max_related_chars=0,
            max_file_chars=10**6,
        )
        llm = make_llm()
        service = make_context_service(llm=llm, budget=budget)

        asyncio.run(service.review(make_request()))

        user = llm.generate_findings.call_args[0][0][1]["content"]
        assert "Context truncation" in user
        assert "INCOMPLETE" in user
        assert "related budget exceeded" in user

    def test_degraded_prompt_states_context_unavailable(self):
        llm = make_llm()
        service = make_context_service(
            llm=llm, client=make_context_client(error=http_error(404))
        )

        asyncio.run(service.review(make_request()))

        user = llm.generate_findings.call_args[0][0][1]["content"]
        assert "PR context unavailable" in user
        assert "http_error:404" in user
        assert "```" not in user
        assert JAVA_SOURCE not in user

    def test_not_configured_prompt_keeps_phase_five_behaviour(self):
        llm = make_llm()
        service = ReviewService(llm_service=llm)

        asyncio.run(service.review(make_request()))

        messages = llm.generate_findings.call_args[0][0]
        assert messages == build_messages(make_request())

    def test_budget_uses_phase_6_6_logic(self):
        budget = ContextBudget(
            max_item_chars=10**6,
            max_related_chars=0,
            max_file_chars=10**6,
        )
        service = make_context_service(budget=budget)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        assert result.report["context"]["available"] is True
        assert result.report["context"]["truncated"] is True

    @pytest.mark.parametrize(
        "error,expected_reason",
        [
            (http_error(404), "http_error:404"),
            (http_error(500), "http_error:500"),
            (httpx.ConnectError("refused"), "ConnectError"),
            (httpx.ReadTimeout("slow"), "ReadTimeout"),
            (ValueError("broken contract"), "ValueError"),
        ],
    )
    def test_context_failures_degrade(self, error, expected_reason):
        llm = make_llm(findings=[VALID_FINDING])
        service = make_context_service(
            llm=llm, client=make_context_client(error=error)
        )

        result = asyncio.run(service.review(make_request()))

        assert result.status == "DEGRADED"
        assert result.report["context"] == {
            "available": False,
            "degraded": True,
            "reason": expected_reason,
        }
        assert "degraded" in result.report["summary"]
        assert "owner/repo#42" in result.report["summary"]
        assert result.report["total_findings"] == 1
        llm.generate_findings.assert_awaited_once()

    def test_validation_error_degrades(self):
        error = ValidationError.from_exception_data(
            "PrContext",
            [{"type": "missing", "loc": ("taskId",), "input": None}],
        )
        service = make_context_service(
            client=make_context_client(error=error)
        )

        result = asyncio.run(service.review(make_request()))

        assert result.status == "DEGRADED"
        assert result.report["context"]["reason"] == "ValidationError"

    def test_builder_failure_degrades(self):
        builder = MagicMock(spec=CodeContextBuilder)
        builder.build = MagicMock(side_effect=ValueError("builder bug"))
        service = make_context_service(builder=builder)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "DEGRADED"
        assert result.report["context"]["reason"] == "ValueError"

    def test_context_failure_never_raises(self):
        service = make_context_service(
            client=make_context_client(error=http_error(500))
        )

        result = asyncio.run(service.review(make_request()))

        assert result.task_id == 1
        assert result.findings == []

    def test_not_configured_keeps_phase_five_behaviour(self):
        llm = make_llm()
        service = ReviewService(llm_service=llm)

        result = asyncio.run(service.review(make_request()))

        assert result.status == "COMPLETED"
        assert result.report["context"] == {
            "available": False,
            "degraded": False,
            "reason": "not_configured",
        }
        llm.generate_findings.assert_awaited_once()

    def test_llm_failure_still_propagates(self):
        service = make_context_service(
            llm=make_llm(error=LLMException("DeepSeek down"))
        )

        with pytest.raises(LLMException, match="DeepSeek down"):
            asyncio.run(service.review(make_request()))

    def test_llm_failure_propagates_when_context_degraded(self):
        service = make_context_service(
            llm=make_llm(error=LLMException("DeepSeek down")),
            client=make_context_client(error=http_error(404)),
        )

        with pytest.raises(LLMException, match="DeepSeek down"):
            asyncio.run(service.review(make_request()))

    def test_request_is_not_mutated(self):
        request = make_request()
        before = request.model_dump()
        service = make_context_service()

        asyncio.run(service.review(request))

        assert request.model_dump() == before

    def test_repeated_calls_are_deterministic(self):
        files = [make_pr_file()]
        first = asyncio.run(
            make_context_service(
                client=make_context_client(make_pr_context(files))
            ).review(make_request())
        )
        second = asyncio.run(
            make_context_service(
                client=make_context_client(make_pr_context(files))
            ).review(make_request())
        )
        assert first == second
