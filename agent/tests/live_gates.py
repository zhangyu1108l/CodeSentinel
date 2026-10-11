"""Explicit opt-in gates for live tests (Phase 8.8).

Default test runs must never reach the real DeepSeek API or real static
analysis tools, independent of whether DEEPSEEK_API_KEY is configured.
Live tests require an explicit environment opt-in and are skipped
otherwise:

- CODESENTINEL_DEEPSEEK_LIVE=1   enables tests/test_deepseek_live.py
- CODESENTINEL_STATIC_TOOLS_LIVE=1  enables tests/test_static_tools_live.py

Truthy values are 1/true/yes/on (case-insensitive). Anything else,
including an unset variable, keeps the gate closed.
"""

import os

DEEPSEEK_LIVE_ENV = "CODESENTINEL_DEEPSEEK_LIVE"
STATIC_TOOLS_LIVE_ENV = "CODESENTINEL_STATIC_TOOLS_LIVE"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def deepseek_live_enabled() -> bool:
    """Whether live DeepSeek tests are explicitly enabled."""
    return _env_enabled(DEEPSEEK_LIVE_ENV)


def static_tools_live_enabled() -> bool:
    """Whether live static analysis tool tests are explicitly enabled."""
    return _env_enabled(STATIC_TOOLS_LIVE_ENV)