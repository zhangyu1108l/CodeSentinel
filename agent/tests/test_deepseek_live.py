"""Live DeepSeek API tests (explicit opt-in since Phase 8.8).

These tests call the real DeepSeek API and require BOTH:

- CODESENTINEL_DEEPSEEK_LIVE=1
- a configured DEEPSEEK_API_KEY

The default test run never reaches the real API, even when a key is
configured (tests/conftest.py also blocks outbound host resolution).

Run explicitly with:
    CODESENTINEL_DEEPSEEK_LIVE=1 DEEPSEEK_API_KEY=sk-... pytest tests/test_deepseek_live.py
"""

import asyncio

import pytest

from app.config.settings import settings
from app.llm.llm_service import LLMService
from app.prompts.review import build_messages
from app.schemas.review import ReviewTaskRequest
from tests.live_gates import deepseek_live_enabled

pytestmark = pytest.mark.skipif(
    not deepseek_live_enabled() or not settings.DEEPSEEK_API_KEY,
    reason=(
        "live DeepSeek tests require CODESENTINEL_DEEPSEEK_LIVE=1 and "
        "DEEPSEEK_API_KEY; skipping"
    ),
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
