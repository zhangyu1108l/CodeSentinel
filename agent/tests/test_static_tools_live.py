"""Live static analysis tool integration tests (Phase 8.8, opt-in).

These tests execute real ruff / bandit / semgrep binaries through the
real SubprocessExecutor and the real StaticAnalysisService. They are
skipped unless CODESENTINEL_STATIC_TOOLS_LIVE=1 AND the tool is on PATH,
so the default run never depends on installed analyzers.

They are intentionally NOT part of the default evidence base: the tool
outcomes recorded here (zero findings, findings, timeouts, output limits)
depend on the installed tool versions and are environment specific.

Run explicitly with:
    CODESENTINEL_STATIC_TOOLS_LIVE=1 pytest tests/test_static_tools_live.py
"""

import shutil

import pytest

from app.schemas.static_analysis import (
    StaticAnalysisStatus,
    StaticAnalysisTool,
)
from app.services.request_budget import RequestBudget
from app.services.static_analysis_service import StaticAnalysisService
from tests.live_gates import static_tools_live_enabled

pytestmark = pytest.mark.skipif(
    not static_tools_live_enabled(),
    reason=(
        "live static tool tests require "
        "CODESENTINEL_STATIC_TOOLS_LIVE=1; skipping"
    ),
)

RUFF_SOURCE = "import os\n\n\nx = 1\n"
CLEAN_SOURCE = "x = 1\n"
SEMGREP_CONFIG = """rules:
  - id: test-useless-eqeq
    languages: [python]
    message: useless comparison
    severity: WARNING
    pattern: $X == $X
"""


def missing(tool: str) -> bool:
    return shutil.which(tool) is None


class TestLiveRuff:
    @pytest.mark.skipif(missing("ruff"), reason="ruff is not on PATH")
    def test_ruff_reports_the_unused_import(self, tmp_path):
        service = StaticAnalysisService(
            ruff_executable="ruff",
            bandit_executable=None,
            semgrep_config_path=None,
        )

        outcome = service.analyze(
            {"pkg/mod.py": RUFF_SOURCE},
            RequestBudget(60),
            parent_dir=str(tmp_path),
        )

        assert outcome.results, "ruff did not run"
        result = outcome.results[0]
        assert result.status is StaticAnalysisStatus.OK
        assert [finding.rule_id for finding in result.findings] == ["F401"]
        finding = result.findings[0]
        assert finding.file_path == "pkg/mod.py"
        assert finding.start_line >= 1

    @pytest.mark.skipif(missing("ruff"), reason="ruff is not on PATH")
    def test_ruff_zero_findings_is_ok(self, tmp_path):
        service = StaticAnalysisService(
            ruff_executable="ruff",
            bandit_executable=None,
            semgrep_config_path=None,
        )

        outcome = service.analyze(
            {"pkg/mod.py": CLEAN_SOURCE},
            RequestBudget(60),
            parent_dir=str(tmp_path),
        )

        result = outcome.results[0]
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []
        assert outcome.aggregate.finding_count == 0


class TestLiveBandit:
    @pytest.mark.skipif(missing("bandit"), reason="bandit is not on PATH")
    def test_bandit_runs_and_reports_explicit_status(self, tmp_path):
        service = StaticAnalysisService(
            ruff_executable=None,
            bandit_executable="bandit",
            semgrep_config_path=None,
        )

        outcome = service.analyze(
            {"pkg/mod.py": "import subprocess\n"},
            RequestBudget(60),
            parent_dir=str(tmp_path),
        )

        assert outcome.results, "bandit did not run"
        result = outcome.results[0]
        assert result.tool is StaticAnalysisTool.BANDIT
        # A non zero exit code with valid JSON is still OK by contract;
        # findings depend on the bandit version and its default rules.
        assert result.status is StaticAnalysisStatus.OK


class TestLiveSemgrep:
    @pytest.mark.skipif(missing("semgrep"), reason="semgrep is not on PATH")
    def test_semgrep_runs_with_trusted_config(self, tmp_path):
        work = tmp_path / "work"
        work.mkdir()
        config = tmp_path / "rules.yaml"
        config.write_text(SEMGREP_CONFIG, encoding="utf-8")
        service = StaticAnalysisService(
            ruff_executable=None,
            bandit_executable=None,
            semgrep_executable="semgrep",
            semgrep_config_path=str(config),
        )

        outcome = service.analyze(
            {"pkg/mod.py": "x = 1\nif x == x:\n    pass\n"},
            RequestBudget(120),
            parent_dir=str(work),
        )

        assert outcome.results, "semgrep did not run"
        result = outcome.results[0]
        assert result.status is StaticAnalysisStatus.OK
        assert all(
            finding.rule_id == "test-useless-eqeq"
            for finding in result.findings
        )