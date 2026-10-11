"""Tests for the Phase 8.7 reporter (deterministic report structure)."""

from app.agents.reporter import (
    NOTE_EMPTY_DEGRADED,
    build_analysis_report,
)
from app.schemas.report import (
    AnalysisFinding,
    FindingSource,
    ReportStatus,
)
from app.schemas.review import Category, ReviewTaskRequest, Severity


def make_request():
    return ReviewTaskRequest(
        task_id=7,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        files=["a.py"],
    )


def make_finding(
    category=Category.BUG,
    severity=Severity.HIGH,
    source=FindingSource.AGENT,
):
    return AnalysisFinding(
        sources=[source],
        category=category,
        severity=severity,
        rule_id="R1",
        message="message",
        file_path="a.py",
        start_line=1,
        end_line=1,
    )


CONTEXT_OK = {
    "available": True,
    "degraded": False,
    "reason": None,
    "file_count": 1,
    "files_with_content": 1,
    "estimated_tokens": 10,
    "truncated": False,
}

STATIC_OK = {
    "available": True,
    "degraded": False,
    "reason": None,
    "tools_run": ["RUFF"],
    "findings": 0,
}


def build(**overrides):
    data = {
        "request": make_request(),
        "findings": [make_finding()],
        "planned_agents": [Category.BUG],
        "executed_agents": [Category.BUG],
        "context_report": CONTEXT_OK,
        "static_report": STATIC_OK,
        "validation_summary": {"agent_kept": 1},
    }
    data.update(overrides)
    return build_analysis_report(**data)


class TestReportStructure:
    def test_clean_run_is_completed(self):
        report = build()

        assert report.status is ReportStatus.COMPLETED
        assert report.degraded is False
        assert report.finding_count == 1
        assert report.task_id == 7
        assert report.repository == "owner/repo"

    def test_severity_counts_include_all_severities(self):
        report = build(
            findings=[
                make_finding(severity=Severity.CRITICAL),
                make_finding(severity=Severity.LOW),
                make_finding(
                    severity=Severity.LOW,
                    source=FindingSource.STATIC,
                ),
            ]
        )

        assert report.severity_counts == {
            "CRITICAL": 1,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 2,
            "INFO": 0,
        }

    def test_agent_and_stage_facts_are_preserved(self):
        report = build(
            duplicates_merged=2,
            source_counts={"AGENT": 1, "STATIC": 0},
            planned_agents=[Category.BUG, Category.SECURITY],
            executed_agents=[Category.BUG],
            failed_agents=[Category.SECURITY],
            skipped_agents=[Category.QUALITY],
            recoverable_errors=["LLMResponseError"],
        )

        assert report.planned_agents == [
            Category.BUG,
            Category.SECURITY,
        ]
        assert report.executed_agents == [Category.BUG]
        assert report.failed_agents == [Category.SECURITY]
        assert report.skipped_agents == [Category.QUALITY]
        assert report.recoverable_errors == ["LLMResponseError"]
        assert report.duplicates_merged == 2
        assert report.source_counts == {"AGENT": 1, "STATIC": 0}
        assert report.context == CONTEXT_OK
        assert report.static_analysis == STATIC_OK
        assert report.validation == {"agent_kept": 1}


class TestDegradedSemantics:
    def test_context_unavailable_degrades_even_without_errors(self):
        report = build(
            findings=[],
            executed_agents=[],
            context_report={
                "available": False,
                "degraded": False,
                "reason": "not_configured",
            },
        )

        assert report.degraded is True
        assert report.status is ReportStatus.DEGRADED
        assert NOTE_EMPTY_DEGRADED in report.notes
        assert any("not_configured" in note for note in report.notes)

    def test_degraded_context_degrades_report(self):
        report = build(
            context_report={
                "available": False,
                "degraded": True,
                "reason": "http_error:500",
            }
        )

        assert report.degraded is True
        assert any("http_error:500" in note for note in report.notes)

    def test_failed_agent_degrades_and_is_explained(self):
        report = build(failed_agents=[Category.SECURITY])

        assert report.degraded is True
        assert any(
            "SECURITY" in note and "failed" in note
            for note in report.notes
        )

    def test_degraded_static_stage_degrades_report(self):
        report = build(
            static_report={
                "available": True,
                "degraded": True,
                "reason": None,
                "tools_run": ["RUFF"],
                "failed_tools": ["BANDIT"],
                "findings": 0,
            }
        )

        assert report.degraded is True

    def test_unavailable_static_stage_is_noted(self):
        report = build(
            static_report={
                "available": False,
                "degraded": False,
                "reason": "not_configured",
            }
        )

        assert report.degraded is False
        assert any(
            "static analysis unavailable" in note
            for note in report.notes
        )

    def test_missing_static_report_is_noted(self):
        report = build(static_report=None)

        assert any(
            "static analysis stage was not run" in note
            for note in report.notes
        )

    def test_validator_failure_degrades_without_dropping_findings(self):
        report = build(
            findings=[],
            validation_summary={"failed": "ValueError"},
        )

        assert report.degraded is True
        assert NOTE_EMPTY_DEGRADED in report.notes
        assert any(
            "validator failed: ValueError" in note
            for note in report.notes
        )

    def test_skipped_agents_are_noted(self):
        report = build(
            planned_agents=[Category.QUALITY],
            executed_agents=[],
            skipped_agents=[Category.QUALITY],
        )

        assert any(
            "QUALITY" in note and "skipped" in note
            for note in report.notes
        )

    def test_zero_finding_clean_run_has_no_degraded_note(self):
        report = build(findings=[], executed_agents=[Category.BUG])

        assert report.degraded is False
        assert NOTE_EMPTY_DEGRADED not in report.notes
        assert report.finding_count == 0