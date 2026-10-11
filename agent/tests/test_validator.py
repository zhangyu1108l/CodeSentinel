"""Tests for the Phase 8.7 unified finding validator.

No LLM, no tools: findings and payloads are synthetic fixtures. The tests
lock the core promise: agent findings need verifiable locations, static
tool findings are never dropped for missing LLM style fields.
"""

from app.agents.context_payload import AgentContextPayload
from app.agents.validator import (
    REASON_BLANK_EVIDENCE,
    REASON_DUPLICATE,
    REASON_INVALID_STATIC,
    REASON_LINE_RANGE,
    REASON_NO_CONTEXT,
    REASON_PATH_NOT_ALLOWED,
    UNVERIFIED_NOT_IN_PAYLOAD,
    UNVERIFIED_NO_PAYLOAD,
    Validator,
)
from app.schemas.review import Category, ReviewFinding, Severity
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisTool,
)


def make_payload(available=True, paths=None, line_ranges=None):
    return AgentContextPayload(
        available=available,
        reason=None if available else "context_unavailable",
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        code_section="CODE",
        paths=paths if paths is not None else ["a.py"],
        line_ranges=(
            line_ranges if line_ranges is not None else {"a.py": [(1, 10)]}
        ),
    )


def make_finding(
    category=Category.BUG,
    file_path="a.py",
    start=1,
    end=1,
    rule_id="R1",
    title="Title",
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
        description="description",
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


class TestAgentFindings:
    def setup_method(self):
        self.validator = Validator()

    def test_verified_finding_is_kept(self):
        finding = make_finding()

        outcome = self.validator.validate(
            make_payload(), [finding], []
        )

        assert outcome.findings == [finding]
        assert outcome.dropped_findings == {}

    def test_missing_payload_drops_agent_findings_with_reason(self):
        outcome = self.validator.validate(None, [make_finding()], [])

        assert outcome.findings == []
        assert outcome.dropped_findings == {REASON_NO_CONTEXT: 1}

    def test_unavailable_payload_drops_agent_findings(self):
        outcome = self.validator.validate(
            make_payload(available=False), [make_finding()], []
        )

        assert outcome.findings == []
        assert outcome.dropped_findings == {REASON_NO_CONTEXT: 1}

    def test_unknown_path_is_dropped(self):
        outcome = self.validator.validate(
            make_payload(), [make_finding(file_path="b.py")], []
        )

        assert outcome.findings == []
        assert outcome.dropped_findings == {REASON_PATH_NOT_ALLOWED: 1}

    def test_out_of_range_is_dropped(self):
        outcome = self.validator.validate(
            make_payload(), [make_finding(start=20, end=22)], []
        )

        assert outcome.dropped_findings == {REASON_LINE_RANGE: 1}

    def test_inverted_range_is_dropped(self):
        outcome = self.validator.validate(
            make_payload(), [make_finding(start=8, end=3)], []
        )

        assert outcome.dropped_findings == {REASON_LINE_RANGE: 1}

    def test_spanning_two_ranges_is_dropped(self):
        payload = make_payload(
            line_ranges={"a.py": [(1, 3), (10, 12)]}
        )

        outcome = self.validator.validate(
            payload, [make_finding(start=2, end=11)], []
        )

        assert outcome.dropped_findings == {REASON_LINE_RANGE: 1}

    def test_blank_evidence_is_dropped(self):
        blank = make_finding().model_copy(update={"title": "   "})

        outcome = self.validator.validate(make_payload(), [blank], [])

        assert outcome.dropped_findings == {REASON_BLANK_EVIDENCE: 1}

    def test_duplicate_is_dropped_keeping_first(self):
        first = make_finding(rule_id="R1")
        duplicate = make_finding(rule_id="r1")

        outcome = self.validator.validate(
            make_payload(), [first, duplicate], []
        )

        assert outcome.findings == [first]
        assert outcome.dropped_findings == {REASON_DUPLICATE: 1}

    def test_differing_title_is_not_merged(self):
        first = make_finding(title="One")
        second = make_finding(title="Two")

        outcome = self.validator.validate(
            make_payload(), [first, second], []
        )

        assert len(outcome.findings) == 2


class TestStaticFindings:
    def setup_method(self):
        self.validator = Validator()

    def test_valid_static_finding_is_kept_and_verified(self):
        finding = make_static()

        outcome = self.validator.validate(make_payload(), [], [finding])

        assert outcome.static_findings == [finding]
        assert outcome.static_unverified == 0
        assert outcome.dropped_static == {}

    def test_static_finding_needs_no_llm_style_fields(self):
        # StaticAnalysisFinding has no title / description / confidence at
        # all; the validator must never demand them.
        finding = make_static()

        outcome = self.validator.validate(make_payload(), [], [finding])

        assert outcome.static_findings == [finding]

    def test_static_finding_outside_payload_is_kept_unverified(self):
        finding = make_static(file_path="b.py")

        outcome = self.validator.validate(make_payload(), [], [finding])

        assert outcome.static_findings == [finding]
        assert outcome.static_unverified == 1
        assert outcome.unverified_reasons == {
            UNVERIFIED_NOT_IN_PAYLOAD: 1
        }

    def test_static_range_outside_payload_ranges_is_unverified(self):
        finding = make_static(start=50, end=51)

        outcome = self.validator.validate(make_payload(), [], [finding])

        assert outcome.static_findings == [finding]
        assert outcome.unverified_reasons == {
            UNVERIFIED_NOT_IN_PAYLOAD: 1
        }

    def test_static_without_payload_is_kept_unverified(self):
        finding = make_static()

        outcome = self.validator.validate(None, [], [finding])

        assert outcome.static_findings == [finding]
        assert outcome.unverified_reasons == {
            UNVERIFIED_NO_PAYLOAD: 1
        }

    def test_invalid_static_invariants_are_dropped(self):
        blank_rule = make_static().model_construct(
            tool=StaticAnalysisTool.RUFF,
            rule_id="   ",
            category=Category.QUALITY,
            severity=Severity.INFO,
            message="m",
            file_path="a.py",
            start_line=1,
            end_line=1,
        )
        bad_range = make_static().model_construct(
            tool=StaticAnalysisTool.RUFF,
            rule_id="R",
            category=Category.QUALITY,
            severity=Severity.INFO,
            message="m",
            file_path="a.py",
            start_line=0,
            end_line=0,
        )

        outcome = self.validator.validate(
            make_payload(), [], [blank_rule, bad_range]
        )

        assert outcome.static_findings == []
        assert outcome.dropped_static == {REASON_INVALID_STATIC: 2}

    def test_duplicate_static_findings_are_deduped(self):
        first = make_static()
        second = make_static()

        outcome = self.validator.validate(
            make_payload(), [], [first, second]
        )

        assert outcome.static_findings == [first]
        assert outcome.dropped_static == {REASON_DUPLICATE: 1}


class TestSummary:
    def test_summary_counts_only_safe_values(self):
        validator = Validator()
        outcome = validator.validate(
            make_payload(),
            [make_finding(), make_finding(file_path="b.py")],
            [make_static(), make_static(file_path="c.py")],
        )

        summary = outcome.summary()

        assert summary["agent_checked"] == 2
        assert summary["agent_kept"] == 1
        assert summary["agent_dropped"] == {REASON_PATH_NOT_ALLOWED: 1}
        assert summary["static_checked"] == 2
        assert summary["static_kept"] == 2
        assert summary["static_dropped"] == {}
        assert summary["static_unverified"] == 1
        assert summary["unverified_reasons"] == {
            UNVERIFIED_NOT_IN_PAYLOAD: 1
        }