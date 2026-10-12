"""Tests for the Phase 8.8 live opt-in gates and the network blocker.

These tests prove the safety property itself: with the default
environment (no opt-in), the DeepSeek and static tool gates are closed
and outbound host resolution is blocked, independent of whether
DEEPSEEK_API_KEY is configured.
"""

import socket

import pytest

from tests.live_gates import (
    DEEPSEEK_LIVE_ENV,
    STATIC_TOOLS_LIVE_ENV,
    deepseek_live_enabled,
    static_tools_live_enabled,
)


class TestGateParsing:
    def test_gates_are_closed_without_env(self, monkeypatch):
        monkeypatch.delenv(DEEPSEEK_LIVE_ENV, raising=False)
        monkeypatch.delenv(STATIC_TOOLS_LIVE_ENV, raising=False)

        assert deepseek_live_enabled() is False
        assert static_tools_live_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_values_open_the_gates(self, monkeypatch, value):
        monkeypatch.setenv(DEEPSEEK_LIVE_ENV, value)
        monkeypatch.setenv(STATIC_TOOLS_LIVE_ENV, value)

        assert deepseek_live_enabled() is True
        assert static_tools_live_enabled() is True

    @pytest.mark.parametrize(
        "value", ["", "0", "false", "no", "off", "garbage"]
    )
    def test_other_values_keep_the_gates_closed(
        self, monkeypatch, value
    ):
        monkeypatch.setenv(DEEPSEEK_LIVE_ENV, value)
        monkeypatch.setenv(STATIC_TOOLS_LIVE_ENV, value)

        assert deepseek_live_enabled() is False
        assert static_tools_live_enabled() is False


class TestNetworkBlocker:
    def test_default_run_blocks_non_loopback_resolution(self):
        if deepseek_live_enabled():
            pytest.skip("live DeepSeek run: blocker is intentionally off")

        with pytest.raises(AssertionError, match="blocked"):
            socket.getaddrinfo("api.deepseek.com", 443)

    def test_loopback_resolution_still_works(self):
        result = socket.getaddrinfo("localhost", 80)
        assert result