"""Tests for the Phase 8.7 deterministic finding aggregation."""

from app.agents.finding_aggregator import aggregate_findings
from app.schemas.report import FindingSource
from app.schemas.review import Category, ReviewFinding, Severity
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisTool,
)


def make_agent_finding(
    category=Category.BUG,
    file_path="a.py",
    start=1,
    end=1,
    rule_id="R1",
    title="Title",
    description="description",
):
    return ReviewFinding(
        category=category,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id=rule_id,
        title=title,
        file_path=file_path,
        start_line=start,
        end_line=end,
        description=description,
        reason="reason",
        suggestion="suggestion",
        references=[],
    )


def make_static(
    tool=StaticAnalysisTool.RUFF,
    file_path="a.py",
    start=1,
    end=1,
    rule_id="F401",
    category=Category.QUALITY,
    message="unused import",
):
    return StaticAnalysisFinding(
        tool=tool,
        rule_id=rule_id,
        category=category,
        severity=Severity.INFO,
        message=message,
        file_path=file_path,
        start_line=start,
        end_line=end,
    )


class TestAgentAggregation:
    def test_agent_finding_keeps_all_fields_and_provenance(self):
        finding = make_agent_finding()

        outcome = aggregate_findings([finding], [])

        assert len(outcome.findings) == 1
        merged = outcome.findings[0]
        assert merged.sources == [FindingSource.AGENT]
        assert merged.agent is Category.BUG
        assert merged.tool is None
        assert merged.confidence == 0.5
        assert merged.title == "Title"
        assert merged.message == "description"
        assert outcome.source_counts == {"AGENT": 1, "STATIC": 0}
        assert outcome.duplicates_merged == 0

    def test_agent_duplicates_are_merged(self):
        first = make_agent_finding()
        second = make_agent_finding(title="TITLE")

        outcome = aggregate_findings([first, second], [])

        assert len(outcome.findings) == 1
        assert outcome.duplicates_merged == 1

    def test_agent_findings_with_different_titles_stay_distinct(self):
        first = make_agent_finding(title="One")
        second = make_agent_finding(title="Two")

        outcome = aggregate_findings([first, second], [])

        assert len(outcome.findings) == 2


class TestStaticAggregation:
    def test_static_finding_keeps_tool_and_no_invented_fields(self):
        outcome = aggregate_findings([], [make_static()])

        merged = outcome.findings[0]
        assert merged.sources == [FindingSource.STATIC]
        assert merged.tool is StaticAnalysisTool.RUFF
        assert merged.agent is None
        assert merged.confidence is None
        assert merged.title is None
        assert merged.reason is None
        assert merged.suggestion is None
        assert merged.message == "unused import"
        assert outcome.source_counts == {"AGENT": 0, "STATIC": 1}

    def test_static_duplicates_are_merged(self):
        outcome = aggregate_findings(
            [], [make_static(), make_static()]
        )

        assert len(outcome.findings) == 1
        assert outcome.duplicates_merged == 1

    def test_different_tools_with_same_rule_stay_distinct(self):
        outcome = aggregate_findings(
            [],
            [
                make_static(tool=StaticAnalysisTool.RUFF),
                make_static(tool=StaticAnalysisTool.SEMGREP),
            ],
        )

        assert len(outcome.findings) == 2


class TestCrossSourceMerging:
    def test_static_evidence_merges_into_matching_agent_finding(self):
        finding = make_agent_finding(
            category=Category.SECURITY,
            rule_id="SQLI",
            start=5,
            end=6,
            title="SQL injection",
        )
        static = make_static(
            tool=StaticAnalysisTool.SEMGREP,
            rule_id="sqli",
            category=Category.SECURITY,
            start=5,
            end=6,
        )

        outcome = aggregate_findings([finding], [static])

        assert len(outcome.findings) == 1
        merged = outcome.findings[0]
        assert merged.sources == [
            FindingSource.AGENT,
            FindingSource.STATIC,
        ]
        assert merged.tool is StaticAnalysisTool.SEMGREP
        assert merged.title == "SQL injection"
        assert merged.confidence == 0.5
        assert merged.message == "description"
        assert outcome.duplicates_merged == 1
        assert outcome.source_counts == {"AGENT": 1, "STATIC": 0}

    def test_different_rule_is_not_merged(self):
        finding = make_agent_finding(rule_id="SQLI")
        static = make_static(rule_id="B608")

        outcome = aggregate_findings([finding], [static])

        assert len(outcome.findings) == 2
        assert outcome.duplicates_merged == 0

    def test_different_line_range_is_not_merged(self):
        finding = make_agent_finding(start=1, end=1)
        static = make_static(start=9, end=9, rule_id="R1")

        outcome = aggregate_findings([finding], [static])

        assert len(outcome.findings) == 2

    def test_different_category_is_not_merged(self):
        finding = make_agent_finding(category=Category.BUG, rule_id="R1")
        static = make_static(category=Category.SECURITY, rule_id="R1")

        outcome = aggregate_findings([finding], [static])

        assert len(outcome.findings) == 2

    def test_multiple_statics_for_one_agent_entry_add_source_once(self):
        finding = make_agent_finding(
            category=Category.SECURITY,
            rule_id="SQLI",
            start=5,
            end=6,
        )
        first = make_static(
            tool=StaticAnalysisTool.SEMGREP,
            rule_id="sqli",
            category=Category.SECURITY,
            start=5,
            end=6,
        )
        second = make_static(
            tool=StaticAnalysisTool.BANDIT,
            rule_id="sqlI",
            category=Category.SECURITY,
            start=5,
            end=6,
        )

        outcome = aggregate_findings([finding], [first, second])

        assert len(outcome.findings) == 1
        assert outcome.findings[0].sources == [
            FindingSource.AGENT,
            FindingSource.STATIC,
        ]
        assert outcome.findings[0].tool is StaticAnalysisTool.SEMGREP
        assert outcome.duplicates_merged == 2

    def test_order_is_agent_findings_then_unmatched_static(self):
        agent = make_agent_finding(
            category=Category.BUG, rule_id="A1", file_path="a.py"
        )
        merged_static = make_static(
            file_path="b.py", rule_id="B1", category=Category.QUALITY
        )
        lone_static = make_static(
            file_path="c.py", rule_id="C1", category=Category.SECURITY
        )
        agent_same_place = make_agent_finding(
            category=Category.QUALITY,
            file_path="b.py",
            rule_id="B1",
            title="Agent quality",
        )

        outcome = aggregate_findings(
            [agent, agent_same_place], [merged_static, lone_static]
        )

        assert [
            (finding.file_path, finding.rule_id)
            for finding in outcome.findings
        ] == [("a.py", "A1"), ("b.py", "B1"), ("c.py", "C1")]
        assert outcome.findings[1].sources == [
            FindingSource.AGENT,
            FindingSource.STATIC,
        ]
        assert outcome.findings[2].sources == [FindingSource.STATIC]