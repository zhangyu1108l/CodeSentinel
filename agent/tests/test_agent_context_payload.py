"""Tests for the bounded agent context payload (Phase 8.4)."""

import pytest

from app.agents.context_payload import (
    MAX_STATIC_MESSAGE_CHARS,
    build_agent_context,
)
from app.schemas.code_context import (
    ChangedRange,
    CodeContext,
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
    Language,
    MethodContext,
    RelatedCodeContext,
    RelatedKind,
    RelatedReason,
)
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisTool,
)

SOURCE_SENTINEL = "SENTINEL-CONTEXT-SOURCE-DO-NOT-LOG"


def make_file(
    path="a.py",
    content=None,
    line_count=0,
    changed=(),
    methods=(),
    related=(),
):
    file_diff = FileDiff(
        path=path,
        status=FileStatus.MODIFIED,
        language=Language.PYTHON,
        changed_ranges=[
            ChangedRange(start_line=start, end_line=end)
            for start, end in changed
        ],
    )
    file_context = FileContext(file_diff=file_diff)
    if content is not None:
        file_context = FileContext(
            file_diff=file_diff,
            content=FileContent(path=path, content=content),
            line_count=line_count or len(content.splitlines()),
            content_available=True,
        )
    if methods:
        file_context = file_context.model_copy(
            update={
                "methods": [
                    MethodContext(name=name, start_line=start, end_line=end)
                    for name, start, end in methods
                ]
            }
        )
    if related:
        file_context = file_context.model_copy(
            update={
                "related_code": [
                    RelatedCodeContext(
                        path=path,
                        name=name,
                        start_line=start,
                        end_line=end,
                        reason=RelatedReason.SIBLING_OF_CHANGED_METHOD,
                        kind=RelatedKind.METHOD,
                    )
                    for name, start, end in related
                ]
            }
        )
    return file_context


def make_context(files):
    return CodeContext(
        repository="owner/repo",
        pr_number=42,
        head_sha="abc123",
        files=files,
    )


def make_static_finding(path="a.py", message="message"):
    return StaticAnalysisFinding(
        tool=StaticAnalysisTool.RUFF,
        rule_id="F401",
        category=Category.QUALITY,
        severity=Severity.INFO,
        message=message,
        file_path=path,
        start_line=1,
        end_line=1,
    )


class TestBuildAgentContext:
    def test_missing_context_is_unavailable(self):
        payload = build_agent_context(None)
        assert payload.available is False
        assert payload.reason == "context_unavailable"
        assert payload.code_section == ""

    def test_empty_file_list_is_unavailable(self):
        payload = build_agent_context(make_context([]))
        assert payload.available is False
        assert payload.reason == "context_empty"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"max_files": 0},
            {"max_total_chars": 0},
            {"max_static_findings": -1},
        ],
    )
    def test_invalid_limits_are_rejected(self, kwargs):
        with pytest.raises(ValueError):
            build_agent_context(make_context([make_file()]), **kwargs)

    def test_available_content_maps_full_line_range(self):
        context = make_context(
            [make_file(content="print(1)\nprint(2)\n")]
        )

        payload = build_agent_context(context)

        assert payload.available is True
        assert payload.paths == ["a.py"]
        assert payload.line_ranges == {"a.py": [(1, 2)]}
        assert "a.py" in payload.code_section

    def test_without_content_ranges_come_from_changed_ranges(self):
        context = make_context([make_file(changed=[(5, 6), (6, 8)])])

        payload = build_agent_context(context)

        assert payload.line_ranges == {"a.py": [(5, 8)]}

    def test_methods_and_related_extend_ranges_without_content(self):
        context = make_context(
            [
                make_file(
                    changed=[(5, 6)],
                    methods=[("helper", 2, 4)],
                    related=[("other", 10, 12)],
                )
            ]
        )

        payload = build_agent_context(context)

        assert payload.line_ranges == {"a.py": [(2, 6), (10, 12)]}

    def test_file_without_any_ranges_is_not_reportable(self):
        context = make_context([make_file()])

        payload = build_agent_context(context)

        assert payload.available is False
        assert payload.reason == "no_reportable_lines"
        assert payload.paths == []

    def test_max_files_drops_extras_from_the_end(self):
        files = [
            make_file(path=f"f{index}.py", content="x = 1\n")
            for index in range(3)
        ]

        payload = build_agent_context(make_context(files), max_files=2)

        assert payload.files_included == 2
        assert payload.files_dropped == 1
        assert payload.truncated is True
        assert payload.paths == ["f0.py", "f1.py"]

    def test_total_char_budget_drops_files_until_it_fits(self):
        big = "x = 1  # " + "y" * 500 + "\n"
        files = [
            make_file(path=f"f{index}.py", content=big)
            for index in range(5)
        ]

        payload = build_agent_context(
            make_context(files), max_total_chars=1200
        )

        total = len(payload.code_section) + len(payload.static_section)
        assert total <= 1200
        assert payload.files_dropped >= 1
        assert payload.truncated is True
        assert any("truncated" in note for note in payload.notes)

    def test_static_findings_are_rendered_and_capped(self):
        findings = [make_static_finding(message=f"m{i}") for i in range(3)]

        payload = build_agent_context(
            make_context([make_file(content="x = 1\n")]),
            static_findings=findings,
            max_static_findings=2,
        )

        assert payload.static_findings_included == 2
        assert payload.static_findings_dropped == 1
        assert "F401" in payload.static_section

    def test_static_message_is_trimmed(self):
        payload = build_agent_context(
            make_context([make_file(content="x = 1\n")]),
            static_findings=[make_static_finding(message="m" * 1000)],
        )

        assert (
            "m" * (MAX_STATIC_MESSAGE_CHARS + 1)
            not in payload.static_section
        )
        assert "m" * MAX_STATIC_MESSAGE_CHARS in payload.static_section

    def test_source_is_never_logged(self, caplog):
        with caplog.at_level(
            "DEBUG", logger="codesentinel-ai.agent_context_payload"
        ):
            payload = build_agent_context(
                make_context(
                    [make_file(content=SOURCE_SENTINEL + "\n")]
                )
            )

        assert payload.available is True
        assert SOURCE_SENTINEL not in caplog.text