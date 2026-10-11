"""Global test guards (Phase 8.8).

Safety rule: the default test run must never make real outbound network
requests, so no test can reach the real DeepSeek API even when
DEEPSEEK_API_KEY is configured. This module installs an autouse fixture
that blocks host name resolution for every non-loopback host; any test
that accidentally tries to go online fails loudly instead of spending
money or leaking data.

The blocker is lifted only for the explicit live run:
CODESENTINEL_DEEPSEEK_LIVE=1 (see tests/live_gates.py). Live static tool
tests spawn local processes only and are not affected.
"""

import socket

import pytest

from tests.live_gates import deepseek_live_enabled

_ALLOWED_HOSTS = frozenset(
    {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}
)


def _is_loopback(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    if not isinstance(host, str):
        return False
    if host in _ALLOWED_HOSTS:
        return True
    return host.startswith("127.")


@pytest.fixture(autouse=True)
def _block_outbound_network(monkeypatch):
    """Fail any default-run test that resolves a non-loopback host."""
    if deepseek_live_enabled():
        return
    real_getaddrinfo = socket.getaddrinfo

    def guarded(host, port, *args, **kwargs):
        if _is_loopback(host):
            return real_getaddrinfo(host, port, *args, **kwargs)
        raise AssertionError(
            "Outbound network access is blocked in the default test run "
            f"(host={host!r}). Set CODESENTINEL_DEEPSEEK_LIVE=1 together "
            "with DEEPSEEK_API_KEY to run live DeepSeek tests explicitly."
        )

    monkeypatch.setattr(socket, "getaddrinfo", guarded)