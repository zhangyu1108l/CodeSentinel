"""Live DeepSeek API tests.

These tests call the real DeepSeek API and are skipped automatically
unless DEEPSEEK_API_KEY is configured. They are never required by the
default pytest run.

Run explicitly with:
    DEEPSEEK_API_KEY=sk-... pytest tests/test_deepseek_live.py
"""

import asyncio

import pytest

from app.config.settings import settings
from app.llm.llm_service import LLMService
from app.prompts.review import build_messages
from app.schemas.review import ReviewTaskRequest

pytestmark = pytest.mark.skipif(
    not settings.DEEPSEEK_API_KEY,
    reason="DEEPSEEK_API_KEY is not configured; skipping live DeepSeek tests",
)


def make_request(files=None):
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        files=files or [],
    )


def test_live_deepseek_empty_files_returns_empty_findings():
    """Phase 5.2: no code content is provided, so a well-behaved
    model must return an empty findings list."""
    request = make_request()
    messages = build_messages(request)

    service = LLMService()
    findings = asyncio.run(service.generate_findings(messages))

    assert findings == []


def test_live_deepseek_with_file_paths_only_returns_empty_findings():
    """File paths without content are still not analyzable."""
    request = make_request(files=["src/Main.java"])
    messages = build_messages(request)

    service = LLMService()
    findings = asyncio.run(service.generate_findings(messages))

    assert findings == []
