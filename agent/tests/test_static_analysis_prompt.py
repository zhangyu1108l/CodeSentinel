"""Tests for the shared static evidence renderer (Phase 8.6).

The renderer is used by the general review prompt and by the agent
context payload; only metadata is rendered, never raw tool output.
"""

from app.prompts.review import LEGACY_NOTE, build_messages
from app.prompts.static_analysis import (
    render_static_findings,
    render_static_findings_lines,
)
from app.schemas.review import (
    Category,
    ReviewTaskRequest,
    Severity,
)
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisTool,
)


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        files=["pkg/mod.py"],
    )


def make_finding(rule_id="F401", message="unused import", tool=None):
    return StaticAnalysisFinding(
        tool=tool or StaticAnalysisTool.RUFF,
        rule_id=rule_id,
        category=Category.QUALITY,
        severity=Severity.INFO,
        message=message,
        file_path="pkg/mod.py",
        start_line=1,
        end_line=2,
    )


class TestRenderer:
    def test_line_format(self):
        section = render_static_findings_lines([make_finding()])
        assert section == (
            "- [RUFF] F401 (INFO/QUALITY) pkg/mod.py:1-2: unused import"
        )

    def test_findings_are_capped_without_omission_note(self):
        findings = [make_finding(rule_id=f"R{i}") for i in range(3)]
        section = render_static_findings_lines(findings, max_findings=2)
        assert section.count("\n") == 1
        assert "R2" not in section

    def test_omission_note_counts_dropped_findings(self):
        findings = [make_finding(rule_id=f"R{i}") for i in range(4)]
        section = render_static_findings(findings, max_findings=2)
        assert "- ... 2 more finding(s) omitted" in section

    def test_message_is_trimmed_deterministically(self):
        finding = make_finding(message="x" * 100)
        section = render_static_findings_lines(
            [finding], max_message_chars=10
        )
        assert section.endswith(": " + "x" * 10)


class TestPromptInjection:
    def test_none_and_empty_keep_the_legacy_message(self):
        request = make_request()
        baseline = build_messages(request)
        assert build_messages(request, static_findings=None) == baseline
        assert build_messages(request, static_findings=[]) == baseline
        assert baseline[1]["content"].endswith(LEGACY_NOTE)

    def test_findings_are_appended_after_the_note(self):
        request = make_request()
        messages = build_messages(
            request, static_findings=[make_finding()]
        )
        content = messages[1]["content"]
        assert content.startswith(
            build_messages(request)[1]["content"]
        )
        assert "\n\n- [RUFF] F401 (INFO/QUALITY) " in content

    def test_system_prompt_is_unchanged(self):
        request = make_request()
        with_findings = build_messages(
            request, static_findings=[make_finding()]
        )
        without = build_messages(request)
        assert with_findings[0] == without[0]