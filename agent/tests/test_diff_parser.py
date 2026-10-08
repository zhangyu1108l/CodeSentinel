"""Tests for the Phase 6.1 unified diff parser."""

import pytest
from pydantic import ValidationError

from app.context.diff_parser import (
    detect_language,
    merge_changed_ranges,
    parse_file_status,
    parse_hunks,
    parse_patch,
)
from app.schemas.code_context import (
    ChangedRange,
    DiffLine,
    DiffLineKind,
    FileDiff,
    FileStatus,
    Hunk,
    Language,
)

JAVA_MODIFIED_PATCH = "\n".join(
    [
        "@@ -48,3 +48,4 @@",
        "     public User findById(String id) {",
        '-        String sql = "SELECT * FROM users WHERE id = " + id;',
        '+        String sql = "SELECT * FROM users WHERE id = ?";',
        "+        Object[] args = {id};",
        "         return jdbc.queryForObject(sql, mapper);",
    ]
)

JAVA_MULTI_HUNK_PATCH = "\n".join(
    [
        "@@ -10,2 +10,3 @@",
        " import java.util.List;",
        "+import java.util.Optional;",
        " import java.util.Map;",
        "@@ -30,3 +31,3 @@",
        "     private final JdbcTemplate jdbc;",
        "-    private String cache;",
        "+    private final Map<String, User> cache;",
        "     private int size;",
    ]
)

JAVA_ADDED_PATCH = "\n".join(
    [
        "@@ -0,0 +1,3 @@",
        "+package cn.codesentinel.demo;",
        "+",
        "+public class Demo {}",
    ]
)

JAVA_DELETED_PATCH = "\n".join(
    [
        "@@ -1,3 +0,0 @@",
        "-package cn.codesentinel.demo;",
        "-",
        "-public class Demo {}",
    ]
)

PYTHON_REMOVAL_ONLY_PATCH = "\n".join(
    [
        "@@ -20,4 +20,3 @@",
        "     def run(self):",
        '-        logger.debug("start")',
        "         self.do_work()",
        "         return None",
    ]
)

PYTHON_LEADING_REMOVAL_PATCH = "\n".join(
    [
        "@@ -5,3 +5,2 @@",
        "-    legacy = True",
        "     repo = None",
        "     size = 0",
    ]
)

NO_NEWLINE_PATCH = "\n".join(
    [
        "@@ -1,2 +1,2 @@",
        " line one",
        "-line two",
        "+line two changed",
        "\\ No newline at end of file",
    ]
)

CONTEXT_ONLY_PATCH = "\n".join(["@@ -1,2 +1,2 @@", " first", " second"])

OMITTED_COUNT_PATCH = "\n".join(["@@ -1 +1 @@", "-old", "+new"])

RAW_DIFF_PATCH = "\n".join(
    [
        "diff --git a/A.java b/A.java",
        "index 1234567..89abcde 100644",
        "--- a/A.java",
        "+++ b/A.java",
        "@@ -1,1 +1,2 @@",
        " class A {}",
        "+// trailing",
    ]
)

TWO_FILE_DIFF_PATCH = "\n".join(
    [
        "@@ -1,1 +1,1 @@",
        "-old",
        "+new",
        "--- a/B.java",
        "+++ b/B.java",
    ]
)

HEADER_WITH_SECTION_PATCH = "\n".join(
    [
        "@@ -48,3 +48,4 @@ public class UserRepository {",
        "     public User findById(String id) {",
        "-        return null;",
        "+        return user;",
        "+        // adjusted",
        "     }",
    ]
)


def make_hunk(new_start, added_lines, new_count=None):
    return Hunk(
        header=f"@@ -0,0 +{new_start},{len(added_lines)} @@",
        new_start=new_start,
        new_count=len(added_lines) if new_count is None else new_count,
        lines=[
            DiffLine(
                kind=DiffLineKind.ADDED,
                text=text,
                new_line_no=new_start + offset,
            )
            for offset, text in enumerate(added_lines)
        ],
    )


class TestDetectLanguage:
    def test_java_file(self):
        assert detect_language("src/main/java/cn/Foo.java") is Language.JAVA

    def test_java_nested_and_dotted_package_dir(self):
        assert detect_language("a.b/Foo.java") is Language.JAVA

    def test_java_uppercase_extension(self):
        assert detect_language("src/Foo.JAVA") is Language.JAVA

    def test_python_file(self):
        assert detect_language("agent/app/main.py") is Language.PYTHON

    def test_python_stub_file(self):
        assert detect_language("agent/app/main.pyi") is Language.PYTHON

    def test_python_uppercase_extension(self):
        assert detect_language("agent/app/Main.PY") is Language.PYTHON

    def test_windows_style_path(self):
        assert detect_language("src\\main\\Foo.java") is Language.JAVA

    def test_markdown_is_other(self):
        assert detect_language("docs/PROJECT_DESIGN.md") is Language.OTHER

    def test_yaml_is_other(self):
        assert detect_language("infra/docker-compose.yml") is Language.OTHER

    def test_unknown_java_like_suffix_is_other(self):
        assert detect_language("src/Foo.javabc") is Language.OTHER

    def test_file_without_extension_is_other(self):
        assert detect_language("Makefile") is Language.OTHER

    def test_dotfile_is_other(self):
        assert detect_language("src/.gitignore") is Language.OTHER

    def test_empty_path_is_other(self):
        assert detect_language("") is Language.OTHER


class TestParseFileStatus:
    def test_github_statuses(self):
        assert parse_file_status("added") is FileStatus.ADDED
        assert parse_file_status("modified") is FileStatus.MODIFIED
        assert parse_file_status("removed") is FileStatus.REMOVED
        assert parse_file_status("renamed") is FileStatus.RENAMED
        assert parse_file_status("copied") is FileStatus.COPIED

    def test_uppercase_and_padded_status(self):
        assert parse_file_status("  ADDED ") is FileStatus.ADDED

    def test_changed_maps_to_modified(self):
        assert parse_file_status("changed") is FileStatus.MODIFIED

    def test_unchanged_maps_to_unknown(self):
        assert parse_file_status("unchanged") is FileStatus.UNKNOWN

    def test_unrecognized_status(self):
        assert parse_file_status("weird") is FileStatus.UNKNOWN

    def test_empty_and_none_status(self):
        assert parse_file_status("") is FileStatus.UNKNOWN
        assert parse_file_status(None) is FileStatus.UNKNOWN

    def test_enum_passthrough(self):
        assert parse_file_status(FileStatus.RENAMED) is FileStatus.RENAMED


class TestParseHunks:
    def test_empty_patch_returns_no_hunk(self):
        assert parse_hunks("") == []

    def test_single_hunk_header_fields(self):
        hunks = parse_hunks(JAVA_MODIFIED_PATCH)
        assert len(hunks) == 1
        assert hunks[0].header == "@@ -48,3 +48,4 @@"
        assert hunks[0].old_start == 48
        assert hunks[0].old_count == 3
        assert hunks[0].new_start == 48
        assert hunks[0].new_count == 4

    def test_single_hunk_line_kinds(self):
        lines = parse_hunks(JAVA_MODIFIED_PATCH)[0].lines
        assert [line.kind for line in lines] == [
            DiffLineKind.CONTEXT,
            DiffLineKind.REMOVED,
            DiffLineKind.ADDED,
            DiffLineKind.ADDED,
            DiffLineKind.CONTEXT,
        ]

    def test_single_hunk_new_side_line_numbers(self):
        lines = parse_hunks(JAVA_MODIFIED_PATCH)[0].lines
        assert [line.new_line_no for line in lines] == [48, None, 49, 50, 51]

    def test_single_hunk_old_side_line_numbers(self):
        lines = parse_hunks(JAVA_MODIFIED_PATCH)[0].lines
        assert [line.old_line_no for line in lines] == [48, 49, None, None, 50]

    def test_line_text_drops_diff_marker(self):
        lines = parse_hunks(JAVA_MODIFIED_PATCH)[0].lines
        assert lines[1].text == '        String sql = "SELECT * FROM users WHERE id = " + id;'
        assert lines[2].text == '        String sql = "SELECT * FROM users WHERE id = ?";'

    def test_multiple_hunks(self):
        hunks = parse_hunks(JAVA_MULTI_HUNK_PATCH)
        assert len(hunks) == 2
        assert hunks[0].new_start == 10
        assert hunks[1].new_start == 31

    def test_added_file_hunk(self):
        hunks = parse_hunks(JAVA_ADDED_PATCH)
        assert hunks[0].old_start == 0
        assert hunks[0].old_count == 0
        assert hunks[0].new_count == 3
        assert [line.new_line_no for line in hunks[0].lines] == [1, 2, 3]
        assert all(
            line.kind is DiffLineKind.ADDED for line in hunks[0].lines
        )

    def test_added_file_keeps_empty_added_line(self):
        lines = parse_hunks(JAVA_ADDED_PATCH)[0].lines
        assert lines[1].text == ""

    def test_deleted_file_hunk(self):
        hunks = parse_hunks(JAVA_DELETED_PATCH)
        assert hunks[0].new_start == 0
        assert hunks[0].new_count == 0
        assert [line.old_line_no for line in hunks[0].lines] == [1, 2, 3]
        assert all(line.new_line_no is None for line in hunks[0].lines)

    def test_no_newline_marker_is_skipped(self):
        lines = parse_hunks(NO_NEWLINE_PATCH)[0].lines
        assert len(lines) == 3
        assert all(not line.text.startswith("\\") for line in lines)

    def test_crlf_patch_matches_lf_patch(self):
        crlf = JAVA_MODIFIED_PATCH.replace("\n", "\r\n")
        assert parse_hunks(crlf) == parse_hunks(JAVA_MODIFIED_PATCH)

    def test_cr_only_patch_is_normalized(self):
        cr = JAVA_MODIFIED_PATCH.replace("\n", "\r")
        assert len(parse_hunks(cr)[0].lines) == 5

    def test_trailing_newline_does_not_add_context_line(self):
        assert len(parse_hunks(JAVA_MODIFIED_PATCH + "\n")[0].lines) == 5

    def test_omitted_counts_default_to_one(self):
        hunk = parse_hunks(OMITTED_COUNT_PATCH)[0]
        assert hunk.old_count == 1
        assert hunk.new_count == 1
        assert [line.kind for line in hunk.lines] == [
            DiffLineKind.REMOVED,
            DiffLineKind.ADDED,
        ]

    def test_header_section_text_is_preserved(self):
        hunk = parse_hunks(HEADER_WITH_SECTION_PATCH)[0]
        assert hunk.header == "@@ -48,3 +48,4 @@ public class UserRepository {"
        assert hunk.new_start == 48

    def test_raw_diff_headers_are_ignored(self):
        hunks = parse_hunks(RAW_DIFF_PATCH)
        assert len(hunks) == 1
        assert [line.kind for line in hunks[0].lines] == [
            DiffLineKind.CONTEXT,
            DiffLineKind.ADDED,
        ]
        assert hunks[0].lines[1].new_line_no == 2

    def test_hunk_stops_at_declared_line_count(self):
        hunks = parse_hunks(TWO_FILE_DIFF_PATCH)
        assert len(hunks) == 1
        assert len(hunks[0].lines) == 2
        assert all("---" not in line.text for line in hunks[0].lines)

    def test_malformed_header_produces_no_hunk(self):
        assert parse_hunks("@@ -x +y @@\n+added") == []

    def test_text_without_hunk_header_produces_no_hunk(self):
        assert parse_hunks("this is not a diff") == []

    def test_unknown_prefix_line_is_ignored(self):
        patch = "\n".join(["@@ -1,3 +1,3 @@", " first", "? junk", " last"])
        lines = parse_hunks(patch)[0].lines
        assert [line.kind for line in lines] == [
            DiffLineKind.CONTEXT,
            DiffLineKind.CONTEXT,
        ]

    def test_incomplete_hunk_is_tolerated(self):
        patch = "\n".join(["@@ -1,10 +1,10 @@", " only one line"])
        hunks = parse_hunks(patch)
        assert len(hunks) == 1
        assert len(hunks[0].lines) == 1


class TestMergeChangedRanges:
    def test_no_hunk(self):
        assert merge_changed_ranges([]) == []

    def test_added_lines_range(self):
        ranges = merge_changed_ranges(parse_hunks(JAVA_ADDED_PATCH))
        assert [(r.start_line, r.end_line) for r in ranges] == [(1, 3)]

    def test_replacement_uses_added_side_only(self):
        ranges = merge_changed_ranges(parse_hunks(JAVA_MODIFIED_PATCH))
        assert [(r.start_line, r.end_line) for r in ranges] == [(49, 50)]

    def test_multiple_hunks_produce_separate_ranges(self):
        ranges = merge_changed_ranges(parse_hunks(JAVA_MULTI_HUNK_PATCH))
        assert [(r.start_line, r.end_line) for r in ranges] == [
            (11, 11),
            (32, 32),
        ]

    def test_removal_only_anchors_to_preceding_new_line(self):
        ranges = merge_changed_ranges(parse_hunks(PYTHON_REMOVAL_ONLY_PATCH))
        assert [(r.start_line, r.end_line) for r in ranges] == [(20, 20)]

    def test_leading_removal_anchors_to_line_before_hunk(self):
        ranges = merge_changed_ranges(parse_hunks(PYTHON_LEADING_REMOVAL_PATCH))
        assert [(r.start_line, r.end_line) for r in ranges] == [(4, 4)]

    def test_full_file_deletion_has_no_new_side_range(self):
        assert merge_changed_ranges(parse_hunks(JAVA_DELETED_PATCH)) == []

    def test_context_only_patch_has_no_range(self):
        assert merge_changed_ranges(parse_hunks(CONTEXT_ONLY_PATCH)) == []

    def test_adjacent_ranges_are_merged(self):
        hunks = [make_hunk(10, ["a"]), make_hunk(11, ["b"])]
        ranges = merge_changed_ranges(hunks)
        assert [(r.start_line, r.end_line) for r in ranges] == [(10, 11)]

    def test_overlapping_ranges_are_merged(self):
        hunks = [make_hunk(10, ["a", "b", "c"]), make_hunk(11, ["x", "y", "z"])]
        ranges = merge_changed_ranges(hunks)
        assert [(r.start_line, r.end_line) for r in ranges] == [(10, 13)]

    def test_distant_ranges_stay_separate(self):
        hunks = [make_hunk(10, ["a"]), make_hunk(20, ["b"])]
        ranges = merge_changed_ranges(hunks)
        assert [(r.start_line, r.end_line) for r in ranges] == [
            (10, 10),
            (20, 20),
        ]

    def test_unordered_hunks_are_sorted(self):
        hunks = [make_hunk(20, ["b"]), make_hunk(10, ["a"])]
        ranges = merge_changed_ranges(hunks)
        assert [(r.start_line, r.end_line) for r in ranges] == [
            (10, 10),
            (20, 20),
        ]

    def test_duplicate_removal_anchor_is_reported_once(self):
        patch = "\n".join(
            ["@@ -20,4 +20,2 @@", "     keep = 1", "-    a = 1", "-    b = 2", "     end = 3"]
        )
        ranges = merge_changed_ranges(parse_hunks(patch))
        assert [(r.start_line, r.end_line) for r in ranges] == [(20, 20)]


class TestParsePatch:
    def test_modified_java_file(self):
        diff = parse_patch(
            "src/main/java/cn/UserRepository.java",
            JAVA_MODIFIED_PATCH,
            "modified",
        )
        assert diff.status is FileStatus.MODIFIED
        assert diff.language is Language.JAVA
        assert diff.patch_available is True
        assert diff.additions == 2
        assert diff.deletions == 1
        assert len(diff.hunks) == 1
        assert diff.changed_ranges == [ChangedRange(start_line=49, end_line=50)]
        assert diff.notes == []
        assert diff.previous_path is None

    def test_added_python_file(self):
        patch = "\n".join(["@@ -0,0 +1,2 @@", "+import os", "+import sys"])
        diff = parse_patch("agent/app/main.py", patch, "added")
        assert diff.status is FileStatus.ADDED
        assert diff.language is Language.PYTHON
        assert diff.additions == 2
        assert diff.deletions == 0
        assert diff.changed_ranges == [ChangedRange(start_line=1, end_line=2)]

    def test_deleted_file(self):
        diff = parse_patch("agent/app/legacy.py", JAVA_DELETED_PATCH, "removed")
        assert diff.status is FileStatus.REMOVED
        assert diff.deletions == 3
        assert diff.additions == 0
        assert diff.changed_ranges == []
        assert "removed lines have no new-side position" in diff.notes

    def test_renamed_file_keeps_previous_path(self):
        diff = parse_patch(
            "src/main/java/cn/NewName.java",
            JAVA_MODIFIED_PATCH,
            "renamed",
            previous_path="src/main/java/cn/OldName.java",
        )
        assert diff.status is FileStatus.RENAMED
        assert diff.path == "src/main/java/cn/NewName.java"
        assert diff.previous_path == "src/main/java/cn/OldName.java"
        assert diff.notes == []

    def test_renamed_file_without_previous_path_is_noted(self):
        diff = parse_patch("src/New.java", JAVA_MODIFIED_PATCH, "renamed")
        assert "renamed file without previous path" in diff.notes

    def test_previous_path_on_modified_file_is_kept(self):
        diff = parse_patch(
            "src/New.java",
            JAVA_MODIFIED_PATCH,
            "modified",
            previous_path="src/Old.java",
        )
        assert diff.previous_path == "src/Old.java"
        assert diff.notes == []

    def test_patch_none_does_not_raise(self):
        diff = parse_patch("src/main/java/cn/Foo.java", None, "modified")
        assert diff.patch_available is False
        assert diff.hunks == []
        assert diff.changed_ranges == []
        assert diff.additions == 0
        assert diff.deletions == 0
        assert diff.status is FileStatus.MODIFIED
        assert diff.language is Language.JAVA
        assert "patch unavailable" in diff.notes

    def test_patch_none_for_binary_file(self):
        diff = parse_patch("infra/logo.png", None, "added")
        assert diff.language is Language.OTHER
        assert diff.patch_available is False

    def test_empty_patch_is_noted(self):
        diff = parse_patch("src/Foo.java", "", "modified")
        assert diff.patch_available is False
        assert "patch is empty" in diff.notes

    def test_whitespace_patch_is_noted(self):
        diff = parse_patch("src/Foo.java", "   \n  ", "modified")
        assert diff.patch_available is False
        assert "patch is empty" in diff.notes

    def test_malformed_patch_is_tolerated(self):
        diff = parse_patch("src/Foo.java", "not a diff at all", "modified")
        assert diff.patch_available is True
        assert diff.hunks == []
        assert diff.changed_ranges == []
        assert "patch contains no hunk header" in diff.notes

    def test_partially_malformed_patch_keeps_valid_hunk(self):
        patch = "\n".join(["@@ broken @@", "@@ -1,1 +1,2 @@", " a", "+b"])
        diff = parse_patch("src/Foo.java", patch, "modified")
        assert len(diff.hunks) == 1
        assert diff.additions == 1
        assert diff.changed_ranges == [ChangedRange(start_line=2, end_line=2)]

    def test_context_only_patch_is_noted(self):
        diff = parse_patch("src/Foo.java", CONTEXT_ONLY_PATCH, "modified")
        assert diff.additions == 0
        assert diff.deletions == 0
        assert diff.changed_ranges == []
        assert "patch contains no changed line" in diff.notes

    def test_unrecognized_status_is_noted(self):
        diff = parse_patch("src/Foo.java", JAVA_MODIFIED_PATCH, "weird")
        assert diff.status is FileStatus.UNKNOWN
        assert "unrecognized file status: weird" in diff.notes

    def test_status_is_case_insensitive(self):
        diff = parse_patch("src/Foo.java", JAVA_MODIFIED_PATCH, "MODIFIED")
        assert diff.status is FileStatus.MODIFIED
        assert diff.notes == []

    def test_empty_status_is_noted(self):
        diff = parse_patch("src/Foo.java", JAVA_MODIFIED_PATCH, "")
        assert diff.status is FileStatus.UNKNOWN
        assert diff.notes == []

    def test_unsupported_language_is_still_parsed(self):
        diff = parse_patch("README.md", JAVA_MODIFIED_PATCH, "modified")
        assert diff.language is Language.OTHER
        assert diff.changed_ranges == [ChangedRange(start_line=49, end_line=50)]

    def test_multi_hunk_counts(self):
        diff = parse_patch("src/Foo.java", JAVA_MULTI_HUNK_PATCH, "modified")
        assert len(diff.hunks) == 2
        assert diff.additions == 2
        assert diff.deletions == 1

    def test_no_newline_marker_patch(self):
        diff = parse_patch("src/Foo.java", NO_NEWLINE_PATCH, "modified")
        assert diff.additions == 1
        assert diff.deletions == 1
        assert diff.changed_ranges == [ChangedRange(start_line=2, end_line=2)]


class TestParserContract:
    def test_parse_patch_returns_file_diff(self):
        diff = parse_patch("src/Foo.java", JAVA_MODIFIED_PATCH, "modified")
        assert isinstance(diff, FileDiff)

    def test_file_diff_is_schema_valid(self):
        diff = parse_patch("src/Foo.java", JAVA_MODIFIED_PATCH, "modified")
        assert FileDiff.model_validate(diff.model_dump()) == diff

    def test_missing_path_is_validation_error(self):
        with pytest.raises(ValidationError):
            parse_patch(None, JAVA_MODIFIED_PATCH, "modified")
