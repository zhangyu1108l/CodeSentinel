"""Tests for the AnalysisReport -> ReviewTaskResult mapping (Phase 8.8).

The mapping is the only bridge to the production API contract; these
tests lock that nothing is fabricated (no invented confidence / title),
nothing meaningful is dropped silently (static evidence and mapping
issues are preserved) and the full analysis JSON stays available.
"""

import json

from app.agents.reporter import (
    MAPPING_MISSING_AGENT_FIELDS,
    resolve_mapping_status,
    to_review_task_result,
)
from app.schemas.report import (
    AnalysisFinding,
    AnalysisReport,
    FindingSource,
    ReportStatus,
)
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskResult,
    Severity,
)
from app.schemas.static_analysis import StaticAnalysisTool

CONTEXT = {
    "available": True,
    "degraded": False,
    "reason": None,
    "file_count": 1,
    "files_with_content": 1,
    "estimated_tokens": 10,
    "truncated": False,
}
STATIC = {
    "available": True,
    "degraded": False,
    "reason": None,
    "tools_run": ["RUFF"],
    "findings": 0,
}
VALIDATION = {"agent_kept": 1, "static_unverified": 0}


def make_agent_finding(**overrides):
    data = {
        "sources": [FindingSource.AGENT],
        "category": Category.BUG,
        "severity": Severity.HIGH,
        "rule_id": "R1",
        "message": "null dereference",
        "file_path": "a.py",
        "start_line": 3,
        "end_line": 4,
        "confidence": 0.5,
        "title": "Possible null dereference",
        "reason": "value may be None",
        "suggestion": "guard the None case",
        "references": ["CWE-476"],
        "agent": Category.BUG,
    }
    data.update(overrides)
    return AnalysisFinding(**data)


def make_static_finding(**overrides):
    data = {
        "sources": [FindingSource.STATIC],
        "category": Category.QUALITY,
        "severity": Severity.INFO,
        "rule_id": "F401",
        "message": "`os` imported but unused",
        "file_path": "a.py",
        "start_line": 1,
        "end_line": 1,
        "tool": StaticAnalysisTool.RUFF,
    }
    data.update(overrides)
    return AnalysisFinding(**data)


def make_report(findings=(), degraded=False, notes=(), **overrides):
    data = {
        "task_id": 7,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "status": (
            ReportStatus.DEGRADED if degraded else ReportStatus.COMPLETED
        ),
        "degraded": degraded,
        "findings": list(findings),
        "finding_count": len(findings),
        "severity_counts": {
            severity.value: 0 for severity in Severity
        },
        "source_counts": {"AGENT": 0, "STATIC": 0},
        "duplicates_merged": 0,
        "planned_agents": [Category.BUG],
        "executed_agents": [Category.BUG],
        "failed_agents": [],
        "skipped_agents": [],
        "recoverable_errors": [],
        "context": dict(CONTEXT),
        "static_analysis": dict(STATIC),
        "validation": dict(VALIDATION),
        "notes": list(notes),
    }
    data.update(overrides)
    return AnalysisReport(**data)


class TestAgentFindings:
    def test_agent_finding_maps_one_to_one(self):
        finding = make_agent_finding()

        result = to_review_task_result(make_report([finding]))

        assert len(result.findings) == 1
        mapped = result.findings[0]
        assert isinstance(mapped, ReviewFinding)
        assert mapped.category is Category.BUG
        assert mapped.severity is Severity.HIGH
        assert mapped.confidence == 0.5
        assert mapped.rule_id == "R1"
        assert mapped.title == "Possible null dereference"
        assert mapped.description == "null dereference"
        assert mapped.reason == "value may be None"
        assert mapped.suggestion == "guard the None case"
        assert mapped.file_path == "a.py"
        assert mapped.start_line == 3
        assert mapped.end_line == 4
        assert mapped.references == ["CWE-476"]
        assert result.report["total_findings"] == 1

    def test_task_id_and_status_are_copied(self):
        result = to_review_task_result(make_report([make_agent_finding()]))

        assert result.task_id == 7
        assert result.status == "COMPLETED"
        assert result.report["status"] == "COMPLETED"
        assert result.report["degraded"] is False

    def test_degraded_report_maps_to_degraded_result(self):
        report = make_report(
            [make_agent_finding()],
            degraded=True,
            notes=["context unavailable"],
        )

        result = to_review_task_result(report)

        assert result.status == "DEGRADED"
        assert result.report["degraded"] is True
        assert "degraded" in result.report["summary"].lower()
        assert result.report["notes"] == ["context unavailable"]

    def test_empty_completed_result_maps_cleanly(self):
        result = to_review_task_result(make_report())

        assert result.findings == []
        assert result.report["total_findings"] == 0
        assert result.report["static_finding_count"] == 0
        assert result.report["static_findings"] == []
        assert result.report["mapping_complete"] is True
        assert result.report["mapping_issues"] == []


class TestStaticEvidence:
    def test_static_only_finding_is_preserved_not_dropped(self):
        finding = make_static_finding()

        result = to_review_task_result(make_report([finding]))

        # It cannot become a ReviewFinding without inventing fields, so it
        # must not appear in findings ...
        assert result.findings == []
        assert result.report["total_findings"] == 0
        # ... but it must not be silently dropped either.
        assert result.report["static_finding_count"] == 1
        evidence = result.report["static_findings"][0]
        assert evidence["tool"] == "RUFF"
        assert evidence["rule_id"] == "F401"
        assert evidence["message"] == "`os` imported but unused"
        assert evidence["file_path"] == "a.py"
        assert evidence["start_line"] == 1
        assert evidence["sources"] == ["STATIC"]

    def test_merged_finding_counts_static_provenance(self):
        merged = make_agent_finding(
            sources=[FindingSource.AGENT, FindingSource.STATIC],
            tool=StaticAnalysisTool.RUFF,
        )

        result = to_review_task_result(make_report([merged]))

        assert len(result.findings) == 1
        assert result.report["static_evidence_merged"] == 1
        assert result.report["static_finding_count"] == 0

    def test_mixed_sources_keep_both_representations(self):
        result = to_review_task_result(
            make_report([make_agent_finding(), make_static_finding()])
        )

        assert len(result.findings) == 1
        assert result.report["static_finding_count"] == 1
        assert result.report["total_findings"] == 1


class TestMappingCompleteness:
    def test_missing_agent_fields_are_recorded_not_invented(self):
        agent = make_agent_finding().model_copy(
            update={"title": None, "suggestion": "   "}
        )

        result = to_review_task_result(make_report([agent]))

        assert result.findings == []
        assert result.status == "DEGRADED"
        assert result.report["degraded"] is True
        assert "marked DEGRADED" in result.report["summary"]
        assert result.report["mapping_complete"] is False
        issues = result.report["mapping_issues"]
        assert len(issues) == 1
        assert issues[0]["reason"] == MAPPING_MISSING_AGENT_FIELDS
        assert issues[0]["fields"] == ["title", "suggestion"]
        assert issues[0]["file_path"] == "a.py"
        assert issues[0]["rule_id"] == "R1"

    def test_missing_confidence_is_recorded(self):
        agent = make_agent_finding().model_copy(
            update={"confidence": None}
        )

        result = to_review_task_result(make_report([agent]))

        assert result.status == "DEGRADED"
        assert result.report["mapping_issues"][0]["fields"] == [
            "confidence"
        ]


class TestMappingStatusResolution:
    """Decision A: mapping only ever degrades, never improves."""

    def test_complete_mapping_keeps_completed(self):
        assert (
            resolve_mapping_status("COMPLETED", True) == "COMPLETED"
        )

    def test_incomplete_mapping_degrades_completed(self):
        assert (
            resolve_mapping_status("COMPLETED", False) == "DEGRADED"
        )

    def test_incomplete_mapping_keeps_degraded(self):
        assert resolve_mapping_status("DEGRADED", False) == "DEGRADED"

    def test_incomplete_mapping_never_overwrites_failed(self):
        assert resolve_mapping_status("FAILED", False) == "FAILED"

    def test_complete_mapping_keeps_failed(self):
        assert resolve_mapping_status("FAILED", True) == "FAILED"

    def test_incomplete_mapping_degraded_result_stays_degraded(self):
        report = make_report(
            [make_agent_finding().model_copy(update={"title": None})],
            degraded=True,
        )

        result = to_review_task_result(report)

        assert result.status == "DEGRADED"
        assert result.report["degraded"] is True
        assert result.report["mapping_complete"] is False


class TestLosslessPreservation:
    def test_full_analysis_json_is_embedded(self):
        report = make_report([make_agent_finding(), make_static_finding()])

        result = to_review_task_result(report)

        assert result.report["analysis"] == report.model_dump(mode="json")
        analysis = result.report["analysis"]
        assert analysis["findings"][1]["tool"] == "RUFF"
        assert analysis["findings"][0]["sources"] == ["AGENT"]

    def test_stage_summaries_and_counts_survive(self):
        report = make_report(
            [make_agent_finding()],
            duplicates_merged=2,
            source_counts={"AGENT": 1, "STATIC": 0},
            recoverable_errors=["RuntimeError"],
        )

        result = to_review_task_result(report)

        assert result.report["context"] == CONTEXT
        assert result.report["static_analysis"] == STATIC
        assert result.report["validation"] == VALIDATION
        assert result.report["duplicates_merged"] == 2
        assert result.report["source_counts"] == {
            "AGENT": 1,
            "STATIC": 0,
        }
        assert result.report["agents"]["recoverable_errors"] == [
            "RuntimeError"
        ]

    def test_payload_is_json_serializable(self):
        result = to_review_task_result(
            make_report([make_agent_finding(), make_static_finding()])
        )

        dumped = json.dumps(result.report)
        assert "F401" in dumped


class TestWorkerContract:
    def test_mapped_result_round_trips_through_the_contract(self):
        result = to_review_task_result(
            make_report([make_agent_finding(), make_static_finding()])
        )

        validated = ReviewTaskResult.model_validate(result.model_dump())

        assert validated == result
        finding = validated.findings[0]
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
            assert field in finding.model_dump()

    def test_report_always_carries_the_stable_keys(self):
        result = to_review_task_result(make_report())

        assert set(result.report) == {
            "summary",
            "total_findings",
            "degraded",
            "status",
            "mapping_complete",
            "mapping_issues",
            "analysis",
            "severity_counts",
            "source_counts",
            "static_evidence_merged",
            "static_findings",
            "static_finding_count",
            "duplicates_merged",
            "agents",
            "context",
            "static_analysis",
            "validation",
            "notes",
        }