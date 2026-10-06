"""Tests for the Phase 6.1 Code Context data contract."""

import pytest
from pydantic import ValidationError

from app.schemas.code_context import (
    ChangedRange,
    CodeContext,
    CodeSnippet,
    DiffLine,
    DiffLineKind,
    FileContext,
    FileDiff,
    FileStatus,
    FileStructure,
    Hunk,
    Language,
    SnippetReason,
    SymbolKind,
    SymbolRef,
    SymbolSource,
)

HUNK_HEADER = "@@ -48,3 +48,4 @@"


def make_diff_line(**overrides):
    data = {"kind": DiffLineKind.CONTEXT, "text": "    return user;"}
    data.update(overrides)
    return DiffLine(**data)


def make_symbol(**overrides):
    data = {
        "kind": SymbolKind.METHOD,
        "name": "findById",
        "start_line": 48,
        "end_line": 63,
    }
    data.update(overrides)
    return SymbolRef(**data)


def make_hunk(**overrides):
    data = {
        "header": HUNK_HEADER,
        "old_start": 48,
        "old_count": 3,
        "new_start": 48,
        "new_count": 4,
        "lines": [
            make_diff_line(old_line_no=48, new_line_no=48),
            make_diff_line(
                kind=DiffLineKind.ADDED, text="        return user;", new_line_no=49
            ),
        ],
    }
    data.update(overrides)
    return Hunk(**data)


def make_file_diff(**overrides):
    data = {
        "path": "src/main/java/cn/UserRepository.java",
        "status": FileStatus.MODIFIED,
        "language": Language.JAVA,
        "additions": 1,
        "deletions": 0,
        "hunks": [make_hunk()],
        "changed_ranges": [ChangedRange(start_line=49, end_line=49)],
        "patch_available": True,
    }
    data.update(overrides)
    return FileDiff(**data)


def make_file_context(**overrides):
    data = {"file_diff": make_file_diff()}
    data.update(overrides)
    return FileContext(**data)


def make_code_context(**overrides):
    data = {
        "repository": "zhangyu1108l/CodeSentinel",
        "pr_number": 42,
        "base_sha": "abc123",
        "head_sha": "def456",
        "files": [make_file_context()],
    }
    data.update(overrides)
    return CodeContext(**data)


class TestEnums:
    def test_language_values(self):
        assert {item.value for item in Language} == {"JAVA", "PYTHON", "OTHER"}

    def test_file_status_values(self):
        assert {item.value for item in FileStatus} == {
            "ADDED",
            "MODIFIED",
            "REMOVED",
            "RENAMED",
            "COPIED",
            "UNKNOWN",
        }

    def test_diff_line_kind_values(self):
        assert {item.value for item in DiffLineKind} == {
            "ADDED",
            "REMOVED",
            "CONTEXT",
        }

    def test_symbol_kind_values(self):
        assert {item.value for item in SymbolKind} == {
            "CLASS",
            "METHOD",
            "FUNCTION",
        }

    def test_symbol_source_values(self):
        assert {item.value for item in SymbolSource} == {"AST", "HEURISTIC"}

    def test_snippet_reason_values(self):
        assert {item.value for item in SnippetReason} == {
            "SURROUNDING",
            "SYMBOL",
        }

    def test_language_is_string_enum(self):
        assert Language.JAVA == "JAVA"
        assert Language("PYTHON") is Language.PYTHON

    def test_invalid_language_value(self):
        with pytest.raises(ValueError):
            Language("KOTLIN")


class TestDiffLine:
    def test_defaults(self):
        line = DiffLine(kind=DiffLineKind.CONTEXT)
        assert line.text == ""
        assert line.old_line_no is None
        assert line.new_line_no is None

    def test_kind_is_required(self):
        with pytest.raises(ValidationError):
            DiffLine()

    def test_invalid_kind(self):
        with pytest.raises(ValidationError):
            DiffLine(kind="CHANGED")

    def test_added_line_has_new_side_only(self):
        line = make_diff_line(
            kind=DiffLineKind.ADDED, text="+x", new_line_no=49
        )
        assert line.new_line_no == 49
        assert line.old_line_no is None

    def test_removed_line_has_old_side_only(self):
        line = make_diff_line(
            kind=DiffLineKind.REMOVED, text="-x", old_line_no=49, new_line_no=None
        )
        assert line.old_line_no == 49
        assert line.new_line_no is None

    def test_context_line_has_both_sides(self):
        line = make_diff_line(old_line_no=48, new_line_no=48)
        assert line.old_line_no == 48
        assert line.new_line_no == 48

    def test_string_kind_is_coerced(self):
        assert DiffLine(kind="ADDED").kind is DiffLineKind.ADDED


class TestHunk:
    def test_header_is_required(self):
        with pytest.raises(ValidationError):
            Hunk()

    def test_defaults(self):
        hunk = Hunk(header=HUNK_HEADER)
        assert hunk.old_start == 0
        assert hunk.old_count == 0
        assert hunk.new_start == 0
        assert hunk.new_count == 0
        assert hunk.lines == []

    def test_default_line_lists_are_not_shared(self):
        first = Hunk(header=HUNK_HEADER)
        second = Hunk(header=HUNK_HEADER)
        first.lines.append(make_diff_line())
        assert second.lines == []

    def test_nested_lines(self):
        hunk = make_hunk()
        assert len(hunk.lines) == 2
        assert hunk.lines[1].kind is DiffLineKind.ADDED

    def test_lines_accept_dicts(self):
        hunk = Hunk(
            header=HUNK_HEADER,
            lines=[{"kind": "CONTEXT", "text": "a", "new_line_no": 1}],
        )
        assert hunk.lines[0].kind is DiffLineKind.CONTEXT


class TestChangedRange:
    def test_both_bounds_required(self):
        with pytest.raises(ValidationError):
            ChangedRange(start_line=1)
        with pytest.raises(ValidationError):
            ChangedRange(end_line=1)

    def test_single_line_range(self):
        changed = ChangedRange(start_line=49, end_line=49)
        assert changed.start_line == changed.end_line == 49

    def test_multi_line_range(self):
        changed = ChangedRange(start_line=49, end_line=52)
        assert (changed.start_line, changed.end_line) == (49, 52)


class TestSymbolRef:
    def test_required_fields(self):
        for missing in ("kind", "name", "start_line", "end_line"):
            data = {
                "kind": SymbolKind.METHOD,
                "name": "findById",
                "start_line": 48,
                "end_line": 63,
            }
            del data[missing]
            with pytest.raises(ValidationError):
                SymbolRef(**data)

    def test_defaults(self):
        symbol = make_symbol()
        assert symbol.signature == ""
        assert symbol.source is SymbolSource.HEURISTIC
        assert symbol.confidence == 0.0

    def test_source_can_be_ast(self):
        symbol = make_symbol(source=SymbolSource.AST, confidence=1.0)
        assert symbol.source is SymbolSource.AST
        assert symbol.confidence == 1.0

    def test_source_string_is_coerced(self):
        assert make_symbol(source="AST").source is SymbolSource.AST

    def test_invalid_source(self):
        with pytest.raises(ValidationError):
            make_symbol(source="GUESS")

    def test_confidence_boundaries(self):
        assert make_symbol(confidence=0.0).confidence == 0.0
        assert make_symbol(confidence=1.0).confidence == 1.0
        assert make_symbol(confidence=0.85).confidence == 0.85

    def test_confidence_above_one_is_rejected(self):
        with pytest.raises(ValidationError):
            make_symbol(confidence=1.5)

    def test_confidence_below_zero_is_rejected(self):
        with pytest.raises(ValidationError):
            make_symbol(confidence=-0.1)

    def test_signature_is_kept(self):
        symbol = make_symbol(signature="public User findById(String id)")
        assert symbol.signature == "public User findById(String id)"

    def test_symbol_kinds(self):
        assert make_symbol(kind=SymbolKind.CLASS).kind is SymbolKind.CLASS
        assert make_symbol(kind=SymbolKind.FUNCTION).kind is SymbolKind.FUNCTION


class TestFileStructure:
    def test_defaults(self):
        structure = FileStructure()
        assert structure.language is Language.OTHER
        assert structure.namespace == ""
        assert structure.imports == []
        assert structure.symbols == []
        assert structure.parse_ok is False
        assert structure.notes == []

    def test_default_lists_are_not_shared(self):
        first = FileStructure()
        second = FileStructure()
        first.imports.append("java.util.List")
        assert second.imports == []

    def test_nested_symbols(self):
        structure = FileStructure(
            language=Language.JAVA,
            namespace="cn.codesentinel",
            imports=["java.util.List"],
            symbols=[make_symbol()],
            parse_ok=True,
        )
        assert structure.symbols[0].name == "findById"
        assert structure.parse_ok is True


class TestCodeSnippet:
    def test_defaults(self):
        snippet = CodeSnippet(start_line=38, end_line=73)
        assert snippet.lines == []
        assert snippet.reason is SnippetReason.SURROUNDING

    def test_bounds_required(self):
        with pytest.raises(ValidationError):
            CodeSnippet()

    def test_symbol_reason(self):
        snippet = CodeSnippet(
            start_line=48,
            end_line=63,
            lines=["    public User findById(String id) {"],
            reason=SnippetReason.SYMBOL,
        )
        assert snippet.reason is SnippetReason.SYMBOL
        assert len(snippet.lines) == 1


class TestFileDiff:
    def test_path_is_required(self):
        with pytest.raises(ValidationError):
            FileDiff()

    def test_defaults(self):
        diff = FileDiff(path="src/Foo.java")
        assert diff.status is FileStatus.UNKNOWN
        assert diff.language is Language.OTHER
        assert diff.previous_path is None
        assert diff.additions == 0
        assert diff.deletions == 0
        assert diff.hunks == []
        assert diff.changed_ranges == []
        assert diff.patch_available is False
        assert diff.notes == []

    def test_default_lists_are_not_shared(self):
        first = FileDiff(path="a/A.java")
        second = FileDiff(path="b/B.java")
        first.notes.append("note")
        assert second.notes == []

    def test_full_construction(self):
        diff = make_file_diff()
        assert diff.hunks[0].header == HUNK_HEADER
        assert diff.changed_ranges[0].start_line == 49
        assert diff.patch_available is True

    def test_renamed_keeps_previous_path(self):
        diff = make_file_diff(
            status=FileStatus.RENAMED, previous_path="src/OldRepository.java"
        )
        assert diff.previous_path == "src/OldRepository.java"

    def test_binary_file_without_patch(self):
        diff = FileDiff(
            path="infra/logo.png",
            status=FileStatus.ADDED,
            notes=["patch unavailable"],
        )
        assert diff.patch_available is False
        assert diff.hunks == []


class TestFileContext:
    def test_file_diff_is_required(self):
        with pytest.raises(ValidationError):
            FileContext()

    def test_defaults(self):
        context = make_file_context()
        assert context.structure is None
        assert context.content_available is False
        assert context.changed_symbols == []
        assert context.enclosing_class is None
        assert context.snippets == []
        assert context.skipped_reason is None
        assert context.notes == []

    def test_nested_file_diff(self):
        context = make_file_context()
        assert context.file_diff.language is Language.JAVA
        assert context.file_diff.changed_ranges[0].end_line == 49

    def test_with_structure_and_snippets(self):
        context = make_file_context(
            structure=FileStructure(
                language=Language.JAVA,
                namespace="cn.codesentinel",
                symbols=[make_symbol()],
                parse_ok=True,
            ),
            content_available=True,
            changed_symbols=[make_symbol(source=SymbolSource.AST, confidence=1.0)],
            enclosing_class="UserRepository",
            snippets=[CodeSnippet(start_line=38, end_line=73)],
        )
        assert context.content_available is True
        assert context.enclosing_class == "UserRepository"
        assert context.structure.symbols[0].kind is SymbolKind.METHOD
        assert context.changed_symbols[0].source is SymbolSource.AST
        assert context.snippets[0].reason is SnippetReason.SURROUNDING

    def test_skipped_file(self):
        context = make_file_context(
            skipped_reason="binary file", notes=["content unavailable"]
        )
        assert context.skipped_reason == "binary file"


class TestCodeContext:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            CodeContext(pr_number=1)
        with pytest.raises(ValidationError):
            CodeContext(repository="owner/repo")

    def test_defaults(self):
        context = CodeContext(repository="owner/repo", pr_number=42)
        assert context.base_sha is None
        assert context.head_sha is None
        assert context.files == []
        assert context.notes == []

    def test_default_file_list_is_not_shared(self):
        first = CodeContext(repository="owner/repo", pr_number=1)
        second = CodeContext(repository="owner/repo", pr_number=2)
        first.files.append(make_file_context())
        assert second.files == []

    def test_invalid_pr_number(self):
        with pytest.raises(ValidationError):
            CodeContext(repository="owner/repo", pr_number="not-a-number")

    def test_nested_structure_depth(self):
        context = make_code_context()
        line = context.files[0].file_diff.hunks[0].lines[1]
        assert line.kind is DiffLineKind.ADDED
        assert line.new_line_no == 49

    def test_multiple_files(self):
        context = make_code_context(
            files=[
                make_file_context(),
                make_file_context(
                    file_diff=make_file_diff(
                        path="agent/app/main.py",
                        language=Language.PYTHON,
                    )
                ),
            ]
        )
        assert len(context.files) == 2
        assert context.files[1].file_diff.language is Language.PYTHON

    def test_invalid_nested_file(self):
        with pytest.raises(ValidationError):
            make_code_context(files=["not-a-file-context"])

    def test_notes(self):
        context = make_code_context(notes=["2 files skipped"])
        assert context.notes == ["2 files skipped"]

    def test_round_trip_model_validate(self):
        context = make_code_context()
        assert CodeContext.model_validate(context.model_dump()) == context

    def test_json_dump_uses_string_enums(self):
        data = make_code_context().model_dump(mode="json")
        assert data["files"][0]["file_diff"]["language"] == "JAVA"
        assert data["files"][0]["file_diff"]["status"] == "MODIFIED"
        assert data["files"][0]["file_diff"]["hunks"][0]["lines"][1]["kind"] == "ADDED"

    def test_round_trip_from_json_payload(self):
        payload = make_code_context().model_dump(mode="json")
        restored = CodeContext.model_validate(payload)
        assert restored.files[0].file_diff.status is FileStatus.MODIFIED
        assert restored.files[0].file_diff.hunks[0].lines[1].kind is (
            DiffLineKind.ADDED
        )
