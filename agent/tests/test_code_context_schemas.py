"""Tests for the Phase 6 Code Context data contract."""

import pytest
from pydantic import ValidationError

from app.schemas.code_context import (
    ChangedRange,
    ClassContext,
    CodeContext,
    CodeSnippet,
    DiffLine,
    DiffLineKind,
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
    FileStructure,
    Hunk,
    Language,
    MethodContext,
    RelatedCodeContext,
    RelatedKind,
    RelatedReason,
    SnippetReason,
    SymbolKind,
    SymbolRef,
    SymbolSource,
    TypeKind,
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


def make_method_context(**overrides):
    data = {
        "name": "findById",
        "start_line": 14,
        "end_line": 18,
        "kind": SymbolKind.METHOD,
        "language": Language.JAVA,
        "signature": "public User findById(String id)",
        "code": "    public User findById(String id) {\n        return null;\n    }",
        "source": SymbolSource.HEURISTIC,
        "confidence": 0.9,
        "changed_ranges": [ChangedRange(start_line=16, end_line=16)],
    }
    data.update(overrides)
    return MethodContext(**data)


def make_class_context(**overrides):
    data = {
        "name": "UserRepository",
        "start_line": 5,
        "end_line": 43,
        "kind": TypeKind.CLASS,
        "language": Language.JAVA,
        "depth": 0,
        "signature": "public class UserRepository",
        "code": "public class UserRepository {\n}",
        "source": SymbolSource.HEURISTIC,
        "confidence": 0.9,
    }
    data.update(overrides)
    return ClassContext(**data)


def make_related_code(**overrides):
    data = {
        "path": "src/main/java/cn/UserRepository.java",
        "name": "findById",
        "start_line": 20,
        "end_line": 24,
        "reason": RelatedReason.SIBLING_OF_CHANGED_METHOD,
        "kind": RelatedKind.METHOD,
        "owner_class": "UserRepository",
        "code": "    public User findById(String id) {\n        return null;\n    }",
        "source": SymbolSource.HEURISTIC,
        "confidence": 0.9,
    }
    data.update(overrides)
    return RelatedCodeContext(**data)


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


def make_file_content(**overrides):
    data = {
        "path": "src/main/java/cn/UserRepository.java",
        "revision": "def456",
        "content": "package cn.codesentinel;\n",
    }
    data.update(overrides)
    return FileContent(**data)


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

    def test_type_kind_values(self):
        assert {item.value for item in TypeKind} == {
            "CLASS",
            "INTERFACE",
            "ENUM",
            "RECORD",
            "ANNOTATION_TYPE",
        }

    def test_invalid_type_kind(self):
        with pytest.raises(ValueError):
            TypeKind("TRAIT")

    def test_related_kind_values(self):
        assert {item.value for item in RelatedKind} == {
            "METHOD",
            "CONSTRUCTOR",
            "FIELD",
            "NESTED_TYPE",
        }

    def test_related_reason_values(self):
        assert {item.value for item in RelatedReason} == {
            "SIBLING_OF_CHANGED_METHOD",
            "MEMBER_OF_CHANGED_CLASS",
        }

    def test_invalid_related_kind(self):
        with pytest.raises(ValueError):
            RelatedKind("IMPORT")

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


class TestMethodContext:
    def test_required_fields(self):
        for missing in ("name", "start_line", "end_line"):
            data = {"name": "run", "start_line": 1, "end_line": 2}
            del data[missing]
            with pytest.raises(ValidationError):
                MethodContext(**data)

    def test_defaults(self):
        method = MethodContext(name="run", start_line=1, end_line=2)
        assert method.kind is SymbolKind.METHOD
        assert method.language is Language.OTHER
        assert method.signature == ""
        assert method.code == ""
        assert method.source is SymbolSource.HEURISTIC
        assert method.confidence == 0.0
        assert method.changed_ranges == []

    def test_full_construction(self):
        method = make_method_context()
        assert method.name == "findById"
        assert (method.start_line, method.end_line) == (14, 18)
        assert method.kind is SymbolKind.METHOD
        assert method.language is Language.JAVA
        assert method.changed_ranges == [ChangedRange(start_line=16, end_line=16)]

    def test_function_kind(self):
        method = make_method_context(kind=SymbolKind.FUNCTION, language=Language.PYTHON)
        assert method.kind is SymbolKind.FUNCTION
        assert method.language is Language.PYTHON

    def test_default_range_list_is_not_shared(self):
        first = MethodContext(name="a", start_line=1, end_line=1)
        second = MethodContext(name="b", start_line=2, end_line=2)
        first.changed_ranges.append(ChangedRange(start_line=1, end_line=1))
        assert second.changed_ranges == []

    def test_confidence_boundaries(self):
        assert make_method_context(confidence=0.0).confidence == 0.0
        assert make_method_context(confidence=1.0).confidence == 1.0

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            make_method_context(confidence=1.5)
        with pytest.raises(ValidationError):
            make_method_context(confidence=-0.1)

    def test_invalid_kind(self):
        with pytest.raises(ValidationError):
            make_method_context(kind="MODULE")

    def test_source_can_be_ast(self):
        method = make_method_context(source=SymbolSource.AST, confidence=1.0)
        assert method.source is SymbolSource.AST

    def test_multiple_changed_ranges(self):
        method = make_method_context(
            changed_ranges=[
                ChangedRange(start_line=15, end_line=15),
                ChangedRange(start_line=17, end_line=18),
            ]
        )
        assert len(method.changed_ranges) == 2

    def test_round_trip_model_validate(self):
        method = make_method_context()
        assert MethodContext.model_validate(method.model_dump()) == method

    def test_enclosing_class_defaults_to_none(self):
        assert make_method_context().enclosing_class is None

    def test_enclosing_class_can_be_set(self):
        method = make_method_context(enclosing_class="UserRepository")
        assert method.enclosing_class == "UserRepository"

    def test_enclosing_class_accepts_none(self):
        method = make_method_context(enclosing_class=None)
        assert method.enclosing_class is None


class TestClassContext:
    def test_required_fields(self):
        for missing in ("name", "start_line", "end_line"):
            data = {"name": "Repo", "start_line": 1, "end_line": 3}
            del data[missing]
            with pytest.raises(ValidationError):
                ClassContext(**data)

    def test_defaults(self):
        context = ClassContext(name="Repo", start_line=1, end_line=3)
        assert context.kind is TypeKind.CLASS
        assert context.language is Language.OTHER
        assert context.depth == 0
        assert context.signature == ""
        assert context.code == ""
        assert context.source is SymbolSource.HEURISTIC
        assert context.confidence == 0.0

    def test_full_construction(self):
        context = make_class_context()
        assert context.name == "UserRepository"
        assert (context.start_line, context.end_line) == (5, 43)
        assert context.kind is TypeKind.CLASS
        assert context.language is Language.JAVA
        assert context.confidence == 0.9

    def test_type_kinds(self):
        for kind in TypeKind:
            assert make_class_context(kind=kind).kind is kind

    def test_invalid_kind(self):
        with pytest.raises(ValidationError):
            make_class_context(kind="TRAIT")

    def test_nested_depth(self):
        assert make_class_context(depth=2).depth == 2

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            make_class_context(confidence=1.5)
        with pytest.raises(ValidationError):
            make_class_context(confidence=-0.1)

    def test_round_trip_model_validate(self):
        context = make_class_context()
        assert ClassContext.model_validate(context.model_dump()) == context

    def test_json_dump_uses_string_enums(self):
        data = make_class_context(
            kind=TypeKind.INTERFACE, language=Language.JAVA
        ).model_dump(mode="json")
        assert data["kind"] == "INTERFACE"
        assert data["language"] == "JAVA"
        assert data["source"] == "HEURISTIC"


class TestRelatedCodeContext:
    def test_required_fields(self):
        for missing in ("path", "name", "start_line", "end_line", "reason"):
            data = {
                "path": "src/main/java/cn/Demo.java",
                "name": "helper",
                "start_line": 3,
                "end_line": 5,
                "reason": RelatedReason.SIBLING_OF_CHANGED_METHOD,
            }
            del data[missing]
            with pytest.raises(ValidationError):
                RelatedCodeContext(**data)

    def test_defaults(self):
        item = RelatedCodeContext(
            path="src/main/java/cn/Demo.java",
            name="helper",
            start_line=3,
            end_line=5,
            reason=RelatedReason.SIBLING_OF_CHANGED_METHOD,
        )
        assert item.kind is RelatedKind.METHOD
        assert item.owner_class is None
        assert item.code == ""
        assert item.source is SymbolSource.HEURISTIC
        assert item.confidence == 0.0

    def test_full_construction(self):
        item = make_related_code()
        assert item.path == "src/main/java/cn/UserRepository.java"
        assert item.name == "findById"
        assert (item.start_line, item.end_line) == (20, 24)
        assert item.reason is RelatedReason.SIBLING_OF_CHANGED_METHOD
        assert item.kind is RelatedKind.METHOD
        assert item.owner_class == "UserRepository"
        assert item.code.startswith("    public User findById")

    def test_every_kind_is_accepted(self):
        for kind in RelatedKind:
            assert make_related_code(kind=kind).kind is kind

    def test_member_of_changed_class_reason(self):
        item = make_related_code(reason=RelatedReason.MEMBER_OF_CHANGED_CLASS)
        assert item.reason is RelatedReason.MEMBER_OF_CHANGED_CLASS

    def test_invalid_kind(self):
        with pytest.raises(ValidationError):
            make_related_code(kind="IMPORT")

    def test_invalid_reason(self):
        with pytest.raises(ValidationError):
            make_related_code(reason="SAME_VARIABLE_NAME")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            make_related_code(confidence=1.5)
        with pytest.raises(ValidationError):
            make_related_code(confidence=-0.1)

    def test_round_trip_model_validate(self):
        item = make_related_code()
        assert RelatedCodeContext.model_validate(item.model_dump()) == item

    def test_json_dump_uses_string_enums(self):
        data = make_related_code(
            kind=RelatedKind.NESTED_TYPE,
            reason=RelatedReason.MEMBER_OF_CHANGED_CLASS,
        ).model_dump(mode="json")
        assert data["kind"] == "NESTED_TYPE"
        assert data["reason"] == "MEMBER_OF_CHANGED_CLASS"
        assert data["source"] == "HEURISTIC"


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


class TestFileContent:
    def test_path_is_required(self):
        with pytest.raises(ValidationError):
            FileContent()

    def test_defaults(self):
        content = FileContent(path="src/main/java/cn/Demo.java")
        assert content.revision is None
        assert content.content is None
        assert content.error is None

    def test_minimal_construction(self):
        content = FileContent(path="agent/app/demo.py", content="import os\n")
        assert content.path == "agent/app/demo.py"
        assert content.content == "import os\n"

    def test_empty_content_is_allowed(self):
        content = FileContent(path="agent/app/empty.py", content="")
        assert content.content == ""
        assert content.content is not None

    def test_unavailable_content_with_error(self):
        content = FileContent(
            path="agent/app/legacy.py", content=None, error="404 from contents api"
        )
        assert content.content is None
        assert content.error == "404 from contents api"

    def test_invalid_path_type(self):
        with pytest.raises(ValidationError):
            FileContent(path=None)

    def test_invalid_content_type(self):
        with pytest.raises(ValidationError):
            FileContent(path="a/A.java", content=123)

    def test_round_trip_model_validate(self):
        content = make_file_content()
        assert FileContent.model_validate(content.model_dump()) == content

    def test_json_dump(self):
        data = make_file_content().model_dump(mode="json")
        assert data["revision"] == "def456"
        assert data["content"] == "package cn.codesentinel;\n"


class TestFileContext:
    def test_file_diff_is_required(self):
        with pytest.raises(ValidationError):
            FileContext()

    def test_defaults(self):
        context = make_file_context()
        assert context.structure is None
        assert context.content is None
        assert context.line_count == 0
        assert context.content_available is False
        assert context.changed_symbols == []
        assert context.methods == []
        assert context.classes == []
        assert context.related_code == []
        assert context.enclosing_class is None
        assert context.snippets == []
        assert context.skipped_reason is None
        assert context.notes == []

    def test_default_method_list_is_not_shared(self):
        first = make_file_context()
        second = make_file_context()
        first.methods.append(make_method_context())
        assert second.methods == []

    def test_with_methods(self):
        context = make_file_context(
            methods=[make_method_context()],
            changed_symbols=[make_symbol()],
            content=make_file_content(),
            line_count=1,
            content_available=True,
        )
        assert len(context.methods) == 1
        assert context.methods[0].name == "findById"
        assert context.methods[0].changed_ranges == [
            ChangedRange(start_line=16, end_line=16)
        ]
        assert context.changed_symbols[0].name == "findById"
        assert context.enclosing_class is None
        assert context.structure is None

    def test_default_class_list_is_not_shared(self):
        first = make_file_context()
        second = make_file_context()
        first.classes.append(make_class_context())
        assert second.classes == []

    def test_with_classes_and_linked_method(self):
        context = make_file_context(
            classes=[make_class_context(), make_class_context(name="Nested", depth=1)],
            methods=[make_method_context(enclosing_class="Nested")],
            enclosing_class="Nested",
            content_available=True,
            line_count=43,
        )
        assert [item.name for item in context.classes] == [
            "UserRepository",
            "Nested",
        ]
        assert [item.depth for item in context.classes] == [0, 1]
        assert context.methods[0].enclosing_class == "Nested"
        assert context.enclosing_class == "Nested"

    def test_default_related_code_list_is_not_shared(self):
        first = make_file_context()
        second = make_file_context()
        first.related_code.append(make_related_code())
        assert second.related_code == []

    def test_with_related_code(self):
        context = make_file_context(
            methods=[make_method_context()],
            classes=[make_class_context()],
            related_code=[
                make_related_code(),
                make_related_code(
                    name="repository",
                    kind=RelatedKind.FIELD,
                    start_line=6,
                    end_line=6,
                    confidence=0.8,
                ),
            ],
        )
        assert [item.name for item in context.related_code] == [
            "findById",
            "repository",
        ]
        assert [item.kind for item in context.related_code] == [
            RelatedKind.METHOD,
            RelatedKind.FIELD,
        ]
        assert all(
            item.owner_class == "UserRepository" for item in context.related_code
        )

    def test_nested_file_diff(self):
        context = make_file_context()
        assert context.file_diff.language is Language.JAVA
        assert context.file_diff.changed_ranges[0].end_line == 49

    def test_with_content(self):
        context = make_file_context(
            content=make_file_content(), line_count=1, content_available=True
        )
        assert context.content_available is True
        assert context.line_count == 1
        assert context.content.path == context.file_diff.path
        assert context.content.revision == "def456"

    def test_content_accepts_dict(self):
        context = make_file_context(
            content={"path": "src/main/java/cn/UserRepository.java", "content": "x"}
        )
        assert isinstance(context.content, FileContent)
        assert context.content.content == "x"

    def test_unavailable_content_with_error(self):
        context = make_file_context(
            content=FileContent(
                path="src/main/java/cn/UserRepository.java",
                content=None,
                error="too large",
            ),
            content_available=False,
            skipped_reason="file content unavailable",
        )
        assert context.content_available is False
        assert context.line_count == 0
        assert context.content.error == "too large"

    def test_invalid_content_type(self):
        with pytest.raises(ValidationError):
            make_file_context(content="not-a-file-content")

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

    def test_round_trip_with_file_content(self):
        context = make_code_context(
            files=[
                make_file_context(
                    content=make_file_content(),
                    line_count=1,
                    content_available=True,
                )
            ]
        )
        restored = CodeContext.model_validate(context.model_dump(mode="json"))
        assert restored.files[0].content_available is True
        assert restored.files[0].line_count == 1
        assert restored.files[0].content.content == "package cn.codesentinel;\n"
        assert restored.files[0].content.revision == "def456"

    def test_round_trip_with_methods(self):
        context = make_code_context(
            files=[make_file_context(methods=[make_method_context()])]
        )
        restored = CodeContext.model_validate(context.model_dump(mode="json"))
        method = restored.files[0].methods[0]
        assert method.kind is SymbolKind.METHOD
        assert method.language is Language.JAVA
        assert method.source is SymbolSource.HEURISTIC
        assert method.changed_ranges == [ChangedRange(start_line=16, end_line=16)]

    def test_round_trip_with_classes(self):
        context = make_code_context(
            files=[
                make_file_context(
                    classes=[make_class_context()],
                    methods=[make_method_context(enclosing_class="UserRepository")],
                    enclosing_class="UserRepository",
                    content_available=True,
                    line_count=43,
                )
            ]
        )
        restored = CodeContext.model_validate(context.model_dump(mode="json"))
        file_context = restored.files[0]
        assert file_context.enclosing_class == "UserRepository"
        assert file_context.classes[0].kind is TypeKind.CLASS
        assert file_context.classes[0].language is Language.JAVA
        assert file_context.methods[0].enclosing_class == "UserRepository"
        assert file_context.methods[0].changed_ranges == [
            ChangedRange(start_line=16, end_line=16)
        ]

    def test_round_trip_with_related_code(self):
        context = make_code_context(
            files=[
                make_file_context(
                    classes=[make_class_context()],
                    methods=[make_method_context(enclosing_class="UserRepository")],
                    related_code=[make_related_code()],
                    enclosing_class="UserRepository",
                    content_available=True,
                )
            ]
        )
        restored = CodeContext.model_validate(context.model_dump(mode="json"))
        item = restored.files[0].related_code[0]
        assert item.name == "findById"
        assert item.kind is RelatedKind.METHOD
        assert item.reason is RelatedReason.SIBLING_OF_CHANGED_METHOD
        assert item.owner_class == "UserRepository"
        assert item.path == restored.files[0].file_diff.path

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
