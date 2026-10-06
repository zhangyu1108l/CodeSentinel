"""Tests for the Phase 6.2 File Context builder."""

from app.context import file_context_builder
from app.context.diff_parser import parse_patch
from app.context.file_context_builder import (
    NOTE_BINARY_CONTENT,
    NOTE_CONTENT_IGNORED_FOR_REMOVED,
    NOTE_LINE_COUNT_BELOW_ADDITIONS,
    NOTE_NO_CONTENT,
    NOTE_RANGE_BEYOND_FILE_LENGTH,
    NOTE_REVISION_MISMATCH,
    SKIP_BINARY_CONTENT,
    SKIP_CONTENT_UNAVAILABLE,
    SKIP_FILE_REMOVED,
    SKIP_PATH_MISMATCH,
    build_file_context,
    build_file_contexts,
    count_lines,
    split_lines,
)
from app.schemas.code_context import (
    ChangedRange,
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
    Language,
)

JAVA_MODIFIED_PATCH = "\n".join(
    [
        "@@ -2,3 +2,4 @@",
        " public class Demo {",
        "-    int size = 1;",
        "+    int size = 2;",
        "+    int extra = 3;",
        " }",
    ]
)

JAVA_MODIFIED_CONTENT = (
    "\n".join(
        [
            "package cn.codesentinel.demo;",
            "public class Demo {",
            "    int size = 2;",
            "    int extra = 3;",
            "}",
        ]
    )
    + "\n"
)

PYTHON_ADDED_PATCH = "\n".join(
    [
        "@@ -0,0 +1,3 @@",
        "+import os",
        "+",
        '+VALUE = os.getenv("X")',
    ]
)

PYTHON_ADDED_CONTENT = 'import os\n\nVALUE = os.getenv("X")\n'

JAVA_DELETED_PATCH = "\n".join(
    [
        "@@ -1,2 +0,0 @@",
        "-package cn.codesentinel.legacy;",
        "-public class Legacy {}",
    ]
)


def modified_diff(previous_path=None):
    return parse_patch(
        "src/main/java/cn/Demo.java",
        JAVA_MODIFIED_PATCH,
        "modified",
        previous_path=previous_path,
    )


def added_diff():
    return parse_patch("agent/app/demo.py", PYTHON_ADDED_PATCH, "added")


def removed_diff():
    return parse_patch("agent/app/legacy.py", JAVA_DELETED_PATCH, "removed")


def renamed_diff(patch=JAVA_MODIFIED_PATCH, previous_path="src/main/java/cn/Old.java"):
    return parse_patch(
        "src/main/java/cn/Demo.java",
        patch,
        "renamed",
        previous_path=previous_path,
    )


def make_content(path="src/main/java/cn/Demo.java", content=JAVA_MODIFIED_CONTENT, **overrides):
    data = {"path": path, "content": content}
    data.update(overrides)
    return FileContent(**data)


class TestSplitLines:
    def test_empty_string(self):
        assert split_lines("") == []

    def test_single_line_without_newline(self):
        assert split_lines("a") == ["a"]

    def test_single_line_with_newline(self):
        assert split_lines("a\n") == ["a"]

    def test_multiple_lines_with_final_newline(self):
        assert split_lines("a\nb\nc\n") == ["a", "b", "c"]

    def test_multiple_lines_without_final_newline(self):
        assert split_lines("a\nb\nc") == ["a", "b", "c"]

    def test_crlf_is_normalized(self):
        assert split_lines("a\r\nb\r\n") == ["a", "b"]

    def test_lone_cr_is_normalized(self):
        assert split_lines("a\rb\r") == ["a", "b"]

    def test_only_newline_is_one_empty_line(self):
        assert split_lines("\n") == [""]

    def test_blank_lines_are_kept(self):
        assert split_lines("a\n\nb\n") == ["a", "", "b"]

    def test_trailing_blank_line_is_kept(self):
        assert split_lines("a\n\n") == ["a", ""]

    def test_vertical_tab_is_not_a_line_break(self):
        assert split_lines("a\x0bb") == ["a\x0bb"]

    def test_form_feed_is_not_a_line_break(self):
        assert split_lines("a\x0cb") == ["a\x0cb"]

    def test_unicode_line_separator_is_not_a_line_break(self):
        assert split_lines("a\u2028b") == ["a\u2028b"]

    def test_differs_from_splitlines_on_form_feed(self):
        assert len("a\x0cb".splitlines()) == 2
        assert len(split_lines("a\x0cb")) == 1


class TestCountLines:
    def test_empty_file(self):
        assert count_lines("") == 0

    def test_single_line(self):
        assert count_lines("a\n") == 1

    def test_no_final_newline(self):
        assert count_lines("a\nb") == 2

    def test_crlf_file(self):
        assert count_lines("a\r\nb\r\nc\r\n") == 3

    def test_java_fixture_matches_diff_line_numbers(self):
        assert count_lines(JAVA_MODIFIED_CONTENT) == 5

    def test_python_fixture_matches_added_lines(self):
        diff = added_diff()
        assert count_lines(PYTHON_ADDED_CONTENT) == diff.additions == 3


class TestAddedFile:
    def test_content_is_attached(self):
        context = build_file_context(
            added_diff(), make_content("agent/app/demo.py", PYTHON_ADDED_CONTENT)
        )
        assert context.content_available is True
        assert context.line_count == 3
        assert context.skipped_reason is None
        assert context.notes == []

    def test_diff_data_is_preserved(self):
        context = build_file_context(
            added_diff(), make_content("agent/app/demo.py", PYTHON_ADDED_CONTENT)
        )
        assert context.file_diff.status is FileStatus.ADDED
        assert context.file_diff.language is Language.PYTHON
        assert context.file_diff.additions == 3
        assert context.file_diff.changed_ranges == [
            ChangedRange(start_line=1, end_line=3)
        ]

    def test_content_object_is_kept(self):
        content = make_content("agent/app/demo.py", PYTHON_ADDED_CONTENT, revision="def456")
        context = build_file_context(added_diff(), content)
        assert context.content is content
        assert context.content.revision == "def456"

    def test_missing_content_degrades(self):
        context = build_file_context(added_diff())
        assert context.content_available is False
        assert context.line_count == 0
        assert context.skipped_reason == SKIP_CONTENT_UNAVAILABLE
        assert NOTE_NO_CONTENT in context.notes

    def test_fewer_lines_than_additions_is_noted(self):
        context = build_file_context(
            added_diff(), make_content("agent/app/demo.py", "import os\n")
        )
        assert context.content_available is True
        assert context.line_count == 1
        assert NOTE_LINE_COUNT_BELOW_ADDITIONS in context.notes

    def test_empty_new_file(self):
        patch = "\n".join(["@@ -0,0 +1,1 @@", "+"])
        diff = parse_patch("agent/app/empty.py", patch, "added")
        context = build_file_context(diff, make_content("agent/app/empty.py", "\n"))
        assert context.content_available is True
        assert context.line_count == 1
        assert context.notes == []


class TestModifiedFile:
    def test_content_is_attached(self):
        context = build_file_context(modified_diff(), make_content())
        assert context.content_available is True
        assert context.line_count == 5
        assert context.skipped_reason is None
        assert context.notes == []

    def test_language_and_status(self):
        context = build_file_context(modified_diff(), make_content())
        assert context.file_diff.language is Language.JAVA
        assert context.file_diff.status is FileStatus.MODIFIED

    def test_missing_content_keeps_diff(self):
        diff = modified_diff()
        context = build_file_context(diff)
        assert context.content_available is False
        assert context.skipped_reason == SKIP_CONTENT_UNAVAILABLE
        assert context.file_diff == diff
        assert context.file_diff.changed_ranges == [
            ChangedRange(start_line=3, end_line=4)
        ]

    def test_fetch_error_is_recorded(self):
        content = FileContent(
            path="src/main/java/cn/Demo.java",
            content=None,
            error="file not found at head revision",
        )
        context = build_file_context(modified_diff(), content)
        assert context.content_available is False
        assert context.line_count == 0
        assert context.skipped_reason == SKIP_CONTENT_UNAVAILABLE
        assert "file not found at head revision" in context.notes
        assert context.content is content

    def test_empty_file_content(self):
        diff = parse_patch("src/main/java/cn/Demo.java", JAVA_MODIFIED_PATCH, "modified")
        context = build_file_context(diff, make_content(content=""))
        assert context.content_available is True
        assert context.line_count == 0
        assert NOTE_RANGE_BEYOND_FILE_LENGTH in context.notes

    def test_crlf_source_counts_like_lf(self):
        crlf = JAVA_MODIFIED_CONTENT.replace("\n", "\r\n")
        context = build_file_context(modified_diff(), make_content(content=crlf))
        assert context.line_count == 5
        assert context.notes == []


class TestRemovedFile:
    def test_no_content_is_expected(self):
        context = build_file_context(removed_diff())
        assert context.content_available is False
        assert context.line_count == 0
        assert context.skipped_reason == SKIP_FILE_REMOVED
        assert context.content is None
        assert context.notes == [
            "removed lines have no new-side position"
        ]

    def test_diff_is_still_available(self):
        context = build_file_context(removed_diff())
        assert context.file_diff.status is FileStatus.REMOVED
        assert context.file_diff.deletions == 2
        assert len(context.file_diff.hunks) == 1

    def test_provided_content_is_ignored(self):
        context = build_file_context(
            removed_diff(),
            make_content("agent/app/legacy.py", "stale = True\n"),
        )
        assert context.content_available is False
        assert context.content is None
        assert context.line_count == 0
        assert NOTE_CONTENT_IGNORED_FOR_REMOVED in context.notes

    def test_fetch_error_is_recorded(self):
        content = FileContent(
            path="agent/app/legacy.py", content=None, error="404 from contents api"
        )
        context = build_file_context(removed_diff(), content)
        assert "404 from contents api" in context.notes
        assert NOTE_CONTENT_IGNORED_FOR_REMOVED not in context.notes


class TestRenamedFile:
    def test_content_at_new_path_is_attached(self):
        context = build_file_context(renamed_diff(), make_content())
        assert context.content_available is True
        assert context.line_count == 5
        assert context.skipped_reason is None
        assert context.file_diff.previous_path == "src/main/java/cn/Old.java"
        assert context.file_diff.path == "src/main/java/cn/Demo.java"

    def test_pure_rename_without_patch(self):
        diff = renamed_diff(patch=None)
        context = build_file_context(diff, make_content())
        assert diff.patch_available is False
        assert context.content_available is True
        assert context.line_count == 5
        assert "patch unavailable" in context.notes

    def test_missing_content_degrades(self):
        context = build_file_context(renamed_diff())
        assert context.content_available is False
        assert context.skipped_reason == SKIP_CONTENT_UNAVAILABLE
        assert NOTE_NO_CONTENT in context.notes

    def test_content_under_previous_path_is_rejected(self):
        content = make_content(path="src/main/java/cn/Old.java")
        context = build_file_context(renamed_diff(), content)
        assert context.content_available is False
        assert context.content is None
        assert context.skipped_reason == SKIP_PATH_MISMATCH
        assert any(SKIP_PATH_MISMATCH in note for note in context.notes)


class TestCopiedAndUnknownStatus:
    def test_copied_file_with_content(self):
        diff = parse_patch(
            "src/main/java/cn/Copy.java",
            JAVA_MODIFIED_PATCH,
            "copied",
            previous_path="src/main/java/cn/Demo.java",
        )
        context = build_file_context(
            diff, make_content("src/main/java/cn/Copy.java")
        )
        assert context.content_available is True
        assert context.line_count == 5

    def test_unknown_status_with_content(self):
        diff = parse_patch("src/main/java/cn/Demo.java", JAVA_MODIFIED_PATCH, "weird")
        context = build_file_context(diff, make_content())
        assert context.content_available is True
        assert "unrecognized file status: weird" in context.notes

    def test_unknown_status_without_content(self):
        diff = parse_patch("src/main/java/cn/Demo.java", JAVA_MODIFIED_PATCH, "")
        context = build_file_context(diff)
        assert context.content_available is False
        assert context.skipped_reason == SKIP_CONTENT_UNAVAILABLE
        assert NOTE_NO_CONTENT in context.notes

    def test_explicit_unknown_status_enum(self):
        diff = FileDiff(path="src/main/java/cn/Demo.java", status=FileStatus.UNKNOWN)
        context = build_file_context(diff, make_content())
        assert context.content_available is True


class TestPathGuard:
    def test_mismatched_path_is_rejected(self):
        context = build_file_context(
            modified_diff(), make_content(path="src/main/java/cn/Other.java")
        )
        assert context.content_available is False
        assert context.content is None
        assert context.line_count == 0
        assert context.skipped_reason == SKIP_PATH_MISMATCH
        assert any("src/main/java/cn/Other.java" in note for note in context.notes)

    def test_matching_path_is_accepted(self):
        context = build_file_context(
            modified_diff(), make_content(path="src/main/java/cn/Demo.java")
        )
        assert context.content_available is True


class TestRevisionGuard:
    def test_matching_revision_has_no_note(self):
        content = make_content(revision="def456")
        context = build_file_context(modified_diff(), content, expected_revision="def456")
        assert NOTE_REVISION_MISMATCH not in context.notes
        assert context.content_available is True

    def test_mismatched_revision_is_noted_but_used(self):
        content = make_content(revision="abc123")
        context = build_file_context(modified_diff(), content, expected_revision="def456")
        assert NOTE_REVISION_MISMATCH in context.notes
        assert context.content_available is True
        assert context.line_count == 5

    def test_no_expected_revision_has_no_note(self):
        content = make_content(revision="abc123")
        context = build_file_context(modified_diff(), content)
        assert NOTE_REVISION_MISMATCH not in context.notes

    def test_missing_content_revision_has_no_note(self):
        context = build_file_context(
            modified_diff(), make_content(), expected_revision="def456"
        )
        assert NOTE_REVISION_MISMATCH not in context.notes


class TestConsistencyChecks:
    def test_changed_range_beyond_file_length_is_noted(self):
        diff = FileDiff(
            path="src/main/java/cn/Demo.java",
            status=FileStatus.MODIFIED,
            language=Language.JAVA,
            changed_ranges=[ChangedRange(start_line=50, end_line=60)],
            patch_available=True,
        )
        context = build_file_context(diff, make_content())
        assert NOTE_RANGE_BEYOND_FILE_LENGTH in context.notes
        assert context.content_available is True
        assert context.file_diff.changed_ranges == [
            ChangedRange(start_line=50, end_line=60)
        ]

    def test_range_inside_file_has_no_note(self):
        context = build_file_context(modified_diff(), make_content())
        assert NOTE_RANGE_BEYOND_FILE_LENGTH not in context.notes

    def test_range_equal_to_line_count_has_no_note(self):
        diff = FileDiff(
            path="src/main/java/cn/Demo.java",
            status=FileStatus.MODIFIED,
            changed_ranges=[ChangedRange(start_line=5, end_line=5)],
        )
        context = build_file_context(diff, make_content())
        assert NOTE_RANGE_BEYOND_FILE_LENGTH not in context.notes


class TestBinaryContent:
    def test_nul_byte_is_rejected(self):
        context = build_file_context(
            modified_diff(), make_content(content="public\x00class\x00")
        )
        assert context.content_available is False
        assert context.line_count == 0
        assert context.skipped_reason == SKIP_BINARY_CONTENT
        assert NOTE_BINARY_CONTENT in context.notes

    def test_binary_file_without_patch_and_content(self):
        diff = parse_patch("infra/logo.png", None, "added")
        context = build_file_context(diff)
        assert diff.patch_available is False
        assert context.content_available is False
        assert context.skipped_reason == SKIP_CONTENT_UNAVAILABLE
        assert "patch unavailable" in context.notes


class TestNotesHandling:
    def test_diff_notes_are_preserved_first(self):
        diff = parse_patch("infra/logo.png", None, "weird")
        context = build_file_context(diff)
        assert context.notes[0] == "unrecognized file status: weird"
        assert context.notes[1] == "patch unavailable"
        assert context.notes[-1] == NOTE_NO_CONTENT

    def test_input_diff_is_not_mutated(self):
        diff = modified_diff()
        before = list(diff.notes)
        build_file_context(diff)
        build_file_context(diff, make_content())
        assert diff.notes == before

    def test_notes_are_not_duplicated_across_calls(self):
        diff = modified_diff()
        first = build_file_context(diff)
        second = build_file_context(diff)
        assert first.notes == second.notes
        assert first.notes.count(NOTE_NO_CONTENT) == 1

    def test_note_lists_are_not_shared(self):
        first = build_file_context(modified_diff())
        second = build_file_context(modified_diff())
        first.notes.append("extra")
        assert "extra" not in second.notes


class TestBuildFileContexts:
    def test_empty_input(self):
        assert build_file_contexts([]) == []

    def test_order_matches_input(self):
        diffs = [added_diff(), modified_diff(), removed_diff()]
        contexts = build_file_contexts(diffs)
        assert [c.file_diff.path for c in contexts] == [
            "agent/app/demo.py",
            "src/main/java/cn/Demo.java",
            "agent/app/legacy.py",
        ]

    def test_contents_are_matched_by_path(self):
        diffs = [added_diff(), modified_diff()]
        contexts = build_file_contexts(
            diffs,
            {
                "agent/app/demo.py": make_content(
                    "agent/app/demo.py", PYTHON_ADDED_CONTENT
                ),
                "src/main/java/cn/Demo.java": make_content(),
            },
        )
        assert [c.content_available for c in contexts] == [True, True]
        assert [c.line_count for c in contexts] == [3, 5]

    def test_missing_contents_degrades_every_file(self):
        contexts = build_file_contexts([added_diff(), modified_diff()])
        assert all(c.content_available is False for c in contexts)
        assert all(
            c.skipped_reason == SKIP_CONTENT_UNAVAILABLE for c in contexts
        )

    def test_none_contents_is_same_as_empty(self):
        assert build_file_contexts([added_diff()], None) == build_file_contexts(
            [added_diff()], {}
        )

    def test_partial_contents(self):
        contexts = build_file_contexts(
            [added_diff(), modified_diff()],
            {"src/main/java/cn/Demo.java": make_content()},
        )
        assert contexts[0].content_available is False
        assert contexts[1].content_available is True

    def test_extra_contents_are_ignored(self):
        contexts = build_file_contexts(
            [modified_diff()],
            {
                "src/main/java/cn/Demo.java": make_content(),
                "src/main/java/cn/Unrelated.java": make_content(
                    "src/main/java/cn/Unrelated.java"
                ),
            },
        )
        assert len(contexts) == 1

    def test_mixed_batch_does_not_raise(self):
        diffs = [
            added_diff(),
            modified_diff(),
            removed_diff(),
            renamed_diff(),
            parse_patch("infra/logo.png", None, "added"),
        ]
        contexts = build_file_contexts(
            diffs,
            {
                "agent/app/demo.py": make_content(
                    "agent/app/demo.py", PYTHON_ADDED_CONTENT
                ),
                "agent/app/legacy.py": make_content(
                    "agent/app/legacy.py", "stale = True\n"
                ),
            },
        )
        assert len(contexts) == 5
        assert [c.content_available for c in contexts] == [
            True,
            False,
            False,
            False,
            False,
        ]
        assert contexts[2].skipped_reason == SKIP_FILE_REMOVED

    def test_expected_revision_is_applied_to_all_files(self):
        contexts = build_file_contexts(
            [modified_diff()],
            {"src/main/java/cn/Demo.java": make_content(revision="abc123")},
            expected_revision="def456",
        )
        assert NOTE_REVISION_MISMATCH in contexts[0].notes

    def test_duplicate_paths_use_same_content(self):
        contexts = build_file_contexts(
            [modified_diff(), modified_diff()],
            {"src/main/java/cn/Demo.java": make_content()},
        )
        assert all(c.content_available for c in contexts)


class TestPhaseBoundary:
    def test_structure_fields_stay_empty(self):
        context = build_file_context(modified_diff(), make_content())
        assert context.structure is None
        assert context.changed_symbols == []
        assert context.enclosing_class is None
        assert context.snippets == []

    def test_size_control_is_not_applied_by_this_builder(self):
        import app.schemas.code_context as schema

        assert hasattr(schema, "ContextBudget")
        assert hasattr(schema, "ContextStats")
        assert hasattr(schema, "Truncation")

        context = build_file_context(modified_diff(), make_content())
        assert context.stats is None
        assert context.truncation is None

    def test_builder_exposes_only_file_context_api(self):
        public = [
            name
            for name in dir(file_context_builder)
            if not name.startswith("_")
        ]
        assert "build_file_context" in public
        assert "build_file_contexts" in public
        assert "count_lines" in public
        assert not any("token" in name.lower() for name in public)
        assert not any("truncate" in name.lower() for name in public)


class TestBuilderContract:
    def test_returns_file_context(self):
        context = build_file_context(modified_diff(), make_content())
        assert isinstance(context, FileContext)

    def test_round_trip_model_validate(self):
        context = build_file_context(modified_diff(), make_content())
        assert FileContext.model_validate(context.model_dump()) == context

    def test_context_without_content_round_trips(self):
        context = build_file_context(removed_diff())
        restored = FileContext.model_validate(context.model_dump())
        assert restored.content is None
        assert restored.content_available is False
        assert restored.skipped_reason == SKIP_FILE_REMOVED

    def test_json_dump_serializes_content(self):
        data = build_file_context(modified_diff(), make_content()).model_dump(
            mode="json"
        )
        assert data["content"]["path"] == "src/main/java/cn/Demo.java"
        assert data["line_count"] == 5
        assert data["content_available"] is True
