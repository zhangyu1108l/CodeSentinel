"""Tests for the Phase 6.4 Class Context builder."""

from app.context.class_context_builder import (
    CONFIDENCE_JAVA_TYPE,
    CONFIDENCE_PYTHON_TYPE,
    attach_class_contexts,
    build_class_contexts,
    enclosing_class_name,
    find_anonymous_regions,
    find_classes,
)
from app.context.diff_parser import parse_patch
from app.context.file_context_builder import build_file_context
from app.context.method_context_builder import (
    attach_method_contexts,
    find_methods,
)
from app.schemas.code_context import (
    ChangedRange,
    ClassContext,
    FileContent,
    FileContext,
    FileStatus,
    Language,
    MethodContext,
    SymbolSource,
    TypeKind,
)

JAVA_PATH = "src/main/java/cn/Outer.java"

JAVA_SOURCE = "\n".join(
    [
        "package cn.codesentinel;",
        "",
        "import java.util.List;",
        "",
        "@Service",
        "public class Outer {",
        "",
        "    private final Repo repo;",
        "",
        "    public Outer(Repo repo) {",
        "        this.repo = repo;",
        "    }",
        "",
        "    public Runnable task() {",
        "        return new Runnable() {",
        "            @Override",
        "            public void run() {",
        "                go();",
        "            }",
        "        };",
        "    }",
        "",
        "    static class Nested {",
        "        void nestedMethod() {",
        "            class Local {",
        "                void localMethod() { }",
        "            }",
        "        }",
        "    }",
        "",
        "    public interface Inner {",
        "        void declared();",
        "    }",
        "",
        "    public enum Mode {",
        "        ON, OFF;",
        "        public boolean on() { return this == ON; }",
        "    }",
        "",
        "    public record Point(int x, int y) {",
        "        public int sum() { return x + y; }",
        "    }",
        "}",
        "",
        "abstract class Base {",
        "    abstract void run();",
        "}",
        "",
        "class Second { }",
    ]
) + "\n"

JAVA_PATCH = "\n".join(
    [
        "@@ -10,3 +10,3 @@",
        "     public Outer(Repo repo) {",
        "-        this.repo = repo;",
        "+        this.repo = requireNonNull(repo);",
        "     }",
    ]
)

PYTHON_PATH = "agent/app/point.py"

PYTHON_SOURCE = "\n".join(
    [
        '"""Module docstring.',
        "",
        "class NotAClass:",
        "    pass",
        '"""',
        "",
        "import os",
        "",
        "",
        "@dataclass",
        "class Point:",
        '    """Docstring',
        "class NotAClass2:",
        '    """',
        "",
        "    x: int = 0",
        "",
        "    def __init__(self, x):",
        "        self.x = x",
        "",
        "    @staticmethod",
        "    def create():",
        "        return Point(1)",
        "",
        "    class Nested:",
        "        def nested_method(self):",
        "            class Deep:",
        "                def deep_method(self):",
        "                    return 1",
        "            return Deep()",
        "",
        "",
        "class Second:",
        "    def method(self):",
        "        return 2",
        "",
        "",
        "def top_level():",
        "    def inner_function():",
        "        return 1",
        "    return inner_function",
    ]
) + "\n"

PYTHON_PATCH = "\n".join(
    [
        "@@ -18,2 +18,2 @@",
        "     def __init__(self, x):",
        "-        self.x = x",
        "+        self.x = validate(x)",
    ]
)


def java_classes(source=JAVA_SOURCE):
    return find_classes(source, Language.JAVA)


def python_classes(source=PYTHON_SOURCE):
    return find_classes(source, Language.PYTHON)


def names(classes):
    return [item.name for item in classes]


def by_name(classes, name):
    return next(item for item in classes if item.name == name)


def source_lines(source):
    return source.split("\n")


def java_file_context(patch=JAVA_PATCH, source=JAVA_SOURCE, status="modified"):
    diff = parse_patch(JAVA_PATH, patch, status)
    return build_file_context(diff, FileContent(path=JAVA_PATH, content=source))


def python_file_context(patch=PYTHON_PATCH, source=PYTHON_SOURCE, status="modified"):
    diff = parse_patch(PYTHON_PATH, patch, status)
    return build_file_context(diff, FileContent(path=PYTHON_PATH, content=source))


def java_pipeline(patch=JAVA_PATCH, source=JAVA_SOURCE):
    return attach_class_contexts(attach_method_contexts(java_file_context(patch, source)))


def python_pipeline(patch=PYTHON_PATCH, source=PYTHON_SOURCE):
    return attach_class_contexts(
        attach_method_contexts(python_file_context(patch, source))
    )


class TestFindJavaClasses:
    def test_all_named_types_are_found(self):
        assert names(java_classes()) == [
            "Outer",
            "Nested",
            "Local",
            "Inner",
            "Mode",
            "Point",
            "Base",
            "Second",
        ]

    def test_class_range_and_kind(self):
        outer = by_name(java_classes(), "Outer")
        assert outer.kind is TypeKind.CLASS
        assert outer.start_line == 5
        assert outer.end_line == 43
        assert outer.language is Language.JAVA
        assert outer.source is SymbolSource.HEURISTIC
        assert outer.confidence == CONFIDENCE_JAVA_TYPE

    def test_start_line_includes_annotation(self):
        outer = by_name(java_classes(), "Outer")
        assert source_lines(JAVA_SOURCE)[outer.start_line - 1] == "@Service"

    def test_end_line_is_closing_brace(self):
        outer = by_name(java_classes(), "Outer")
        assert source_lines(JAVA_SOURCE)[outer.end_line - 1] == "}"

    def test_signature_excludes_brace(self):
        assert by_name(java_classes(), "Outer").signature == "public class Outer"

    def test_code_is_exact_slice(self):
        lines = source_lines(JAVA_SOURCE)
        for item in java_classes():
            assert item.code == "\n".join(lines[item.start_line - 1 : item.end_line])

    def test_code_first_and_last_line(self):
        nested = by_name(java_classes(), "Nested")
        assert nested.code.split("\n")[0] == "    static class Nested {"
        assert nested.code.split("\n")[-1] == "    }"

    def test_depth_of_top_level_and_nested(self):
        classes = java_classes()
        assert by_name(classes, "Outer").depth == 0
        assert by_name(classes, "Nested").depth == 1
        assert by_name(classes, "Local").depth == 2
        assert by_name(classes, "Base").depth == 0

    def test_static_nested_class(self):
        nested = by_name(java_classes(), "Nested")
        assert nested.kind is TypeKind.CLASS
        assert nested.signature == "static class Nested"
        assert (nested.start_line, nested.end_line) == (23, 29)

    def test_local_class_inside_method(self):
        local = by_name(java_classes(), "Local")
        assert local.depth == 2
        assert (local.start_line, local.end_line) == (25, 27)

    def test_interface(self):
        inner = by_name(java_classes(), "Inner")
        assert inner.kind is TypeKind.INTERFACE
        assert inner.depth == 1
        assert (inner.start_line, inner.end_line) == (31, 33)
        assert inner.signature == "public interface Inner"

    def test_enum(self):
        mode = by_name(java_classes(), "Mode")
        assert mode.kind is TypeKind.ENUM
        assert (mode.start_line, mode.end_line) == (35, 38)

    def test_enum_constants_are_not_classes(self):
        assert "ON" not in names(java_classes())
        assert "OFF" not in names(java_classes())

    def test_record(self):
        point = by_name(java_classes(), "Point")
        assert point.kind is TypeKind.RECORD
        assert point.signature == "public record Point(int x, int y)"
        assert (point.start_line, point.end_line) == (40, 42)

    def test_abstract_class_stays_class_kind(self):
        base = by_name(java_classes(), "Base")
        assert base.kind is TypeKind.CLASS
        assert "abstract" in base.signature
        assert (base.start_line, base.end_line) == (45, 47)

    def test_multiple_top_level_classes(self):
        top_level = [item for item in java_classes() if item.depth == 0]
        assert names(top_level) == ["Outer", "Base", "Second"]

    def test_empty_class_on_one_line(self):
        second = by_name(java_classes(), "Second")
        assert (second.start_line, second.end_line) == (49, 49)
        assert second.code == "class Second { }"

    def test_empty_class_on_two_lines(self):
        source = "class Empty {\n}\n"
        classes = find_classes(source, Language.JAVA)
        assert (classes[0].start_line, classes[0].end_line) == (1, 2)
        assert classes[0].code == "class Empty {\n}"

    def test_annotation_type(self):
        source = "public @interface Marker {\n    String value() default \"\";\n}\n"
        classes = find_classes(source, Language.JAVA)
        assert classes[0].kind is TypeKind.ANNOTATION_TYPE
        assert classes[0].name == "Marker"
        assert (classes[0].start_line, classes[0].end_line) == (1, 3)

    def test_inline_annotation_before_class(self):
        source = "public class C {\n    @Bean public class Inner {\n    }\n}\n"
        classes = find_classes(source, Language.JAVA)
        inner = by_name(classes, "Inner")
        assert inner.start_line == 2
        assert inner.depth == 1

    def test_generics_extends_implements_signature(self):
        source = "public class Box<T> extends Base<T> implements Repo, Closeable {\n}\n"
        classes = find_classes(source, Language.JAVA)
        assert classes[0].name == "Box"
        assert classes[0].signature == (
            "public class Box<T> extends Base<T> implements Repo, Closeable"
        )

    def test_sealed_permits_signature(self):
        source = "public sealed class Shape permits Circle {\n}\n"
        classes = find_classes(source, Language.JAVA)
        assert classes[0].name == "Shape"
        assert "permits Circle" in classes[0].signature

    def test_deeply_nested_classes(self):
        source = "\n".join(
            [
                "class A {",
                "    class B {",
                "        class C {",
                "            void m() { }",
                "        }",
                "    }",
                "}",
            ]
        )
        classes = find_classes(source, Language.JAVA)
        assert names(classes) == ["A", "B", "C"]
        assert [item.depth for item in classes] == [0, 1, 2]
        assert (classes[0].start_line, classes[0].end_line) == (1, 7)
        assert (classes[2].start_line, classes[2].end_line) == (3, 5)

    def test_class_in_line_comment_is_ignored(self):
        source = "// class Fake {\nclass Real {\n}\n"
        assert names(find_classes(source, Language.JAVA)) == ["Real"]

    def test_class_in_block_comment_is_ignored(self):
        source = "/* class Fake {\n*/\nclass Real {\n}\n"
        assert names(find_classes(source, Language.JAVA)) == ["Real"]

    def test_class_in_string_is_ignored(self):
        source = 'class Real {\n    String s = "class Fake {";\n}\n'
        classes = find_classes(source, Language.JAVA)
        assert names(classes) == ["Real"]
        assert classes[0].end_line == 3

    def test_class_in_text_block_is_ignored(self):
        source = "\n".join(
            [
                "class Real {",
                "    String s = \"\"\"",
                "        class Fake {",
                "        }",
                "    \"\"\";",
                "}",
            ]
        )
        classes = find_classes(source, Language.JAVA)
        assert names(classes) == ["Real"]
        assert classes[0].end_line == 6

    def test_class_literal_is_not_a_declaration(self):
        source = "\n".join(
            [
                "public class C {",
                "    void m() {",
                "        Class<?> type = String.class;",
                "    }",
                "}",
            ]
        )
        assert names(find_classes(source, Language.JAVA)) == ["C"]

    def test_record_as_variable_name_is_not_a_declaration(self):
        source = "\n".join(
            [
                "public class C {",
                "    void m() {",
                "        record = 1;",
                "        record.save(1);",
                "    }",
                "}",
            ]
        )
        assert names(find_classes(source, Language.JAVA)) == ["C"]

    def test_truncated_class_is_skipped(self):
        source = "public class C {\n    void m() {\n"
        assert find_classes(source, Language.JAVA) == []

    def test_extra_closing_brace_does_not_raise(self):
        source = "}\nclass C {\n    void m() { }\n}\n"
        assert names(find_classes(source, Language.JAVA)) == ["C"]

    def test_no_classes(self):
        assert find_classes("package a;\n\nimport b.C;\n", Language.JAVA) == []

    def test_empty_source(self):
        assert find_classes("", Language.JAVA) == []

    def test_no_duplicates(self):
        classes = java_classes()
        keys = [(item.name, item.start_line, item.end_line) for item in classes]
        assert len(keys) == len(set(keys))


class TestFindPythonClasses:
    def test_all_named_classes_are_found(self):
        assert names(python_classes()) == ["Point", "Nested", "Deep", "Second"]

    def test_class_range(self):
        point = by_name(python_classes(), "Point")
        assert (point.start_line, point.end_line) == (10, 30)
        assert point.kind is TypeKind.CLASS
        assert point.language is Language.PYTHON
        assert point.confidence == CONFIDENCE_PYTHON_TYPE

    def test_start_line_includes_decorator(self):
        point = by_name(python_classes(), "Point")
        assert source_lines(PYTHON_SOURCE)[point.start_line - 1] == "@dataclass"

    def test_signature_keeps_colon(self):
        assert by_name(python_classes(), "Point").signature == "class Point:"

    def test_code_is_exact_slice(self):
        lines = source_lines(PYTHON_SOURCE)
        for item in python_classes():
            assert item.code == "\n".join(lines[item.start_line - 1 : item.end_line])

    def test_depth(self):
        classes = python_classes()
        assert by_name(classes, "Point").depth == 0
        assert by_name(classes, "Nested").depth == 1
        assert by_name(classes, "Deep").depth == 2
        assert by_name(classes, "Second").depth == 0

    def test_nested_class_range(self):
        nested = by_name(python_classes(), "Nested")
        assert (nested.start_line, nested.end_line) == (25, 30)

    def test_multiple_top_level_classes(self):
        assert names([c for c in python_classes() if c.depth == 0]) == [
            "Point",
            "Second",
        ]

    def test_class_inside_module_docstring_is_ignored(self):
        assert "NotAClass" not in names(python_classes())

    def test_class_inside_class_docstring_is_ignored(self):
        assert "NotAClass2" not in names(python_classes())

    def test_class_inside_string_literal_is_ignored(self):
        source = 'VALUE = "class Fake:"\n\n\nclass Real:\n    pass\n'
        assert names(find_classes(source, Language.PYTHON)) == ["Real"]

    def test_class_inside_comment_is_ignored(self):
        source = "# class Fake:\n#     pass\n\n\nclass Real:\n    pass\n"
        assert names(find_classes(source, Language.PYTHON)) == ["Real"]

    def test_bases_and_metaclass(self):
        source = "class A(Base, metaclass=Meta):\n    pass\n"
        classes = find_classes(source, Language.PYTHON)
        assert classes[0].name == "A"
        assert classes[0].signature == "class A(Base, metaclass=Meta):"

    def test_multiline_header(self):
        source = "class A(\n    Base,\n):\n    pass\n"
        classes = find_classes(source, Language.PYTHON)
        assert classes[0].start_line == 1
        assert classes[0].end_line == 4
        assert classes[0].signature == "class A(Base,):"

    def test_one_line_class(self):
        source = "class A: pass\n"
        classes = find_classes(source, Language.PYTHON)
        assert (classes[0].start_line, classes[0].end_line) == (1, 1)
        assert classes[0].code == "class A: pass"

    def test_class_with_only_docstring(self):
        source = 'class A:\n    """Empty."""\n'
        classes = find_classes(source, Language.PYTHON)
        assert (classes[0].start_line, classes[0].end_line) == (1, 2)

    def test_docstring_at_column_zero_does_not_end_class(self):
        source = "\n".join(
            [
                "class A:",
                "    text = \"\"\"",
                "column zero content",
                "\"\"\"",
                "    def m(self):",
                "        return 1",
            ]
        )
        classes = find_classes(source, Language.PYTHON)
        assert (classes[0].start_line, classes[0].end_line) == (1, 6)

    def test_tab_indentation(self):
        source = "class A:\n\tdef m(self):\n\t\treturn 1\n"
        classes = find_classes(source, Language.PYTHON)
        assert (classes[0].start_line, classes[0].end_line) == (1, 3)

    def test_deeply_nested_classes(self):
        source = "\n".join(
            [
                "class A:",
                "    class B:",
                "        class C:",
                "            pass",
            ]
        )
        classes = find_classes(source, Language.PYTHON)
        assert names(classes) == ["A", "B", "C"]
        assert [item.depth for item in classes] == [0, 1, 2]
        assert (classes[0].start_line, classes[0].end_line) == (1, 4)

    def test_class_inside_function(self):
        source = "def outer():\n    class Inner:\n        pass\n    return Inner\n"
        classes = find_classes(source, Language.PYTHON)
        assert names(classes) == ["Inner"]
        assert classes[0].depth == 0

    def test_unterminated_docstring_does_not_raise(self):
        source = 'class A:\n    """never closed\n'
        assert isinstance(find_classes(source, Language.PYTHON), list)

    def test_no_classes(self):
        assert find_classes("import os\n\nVALUE = 1\n", Language.PYTHON) == []

    def test_empty_source(self):
        assert find_classes("", Language.PYTHON) == []


class TestUnsupportedLanguage:
    def test_other_language_has_no_classes(self):
        assert find_classes(JAVA_SOURCE, Language.OTHER) == []

    def test_markdown_is_not_parsed(self):
        assert find_classes("class Fake {\n", Language.OTHER) == []

    def test_other_language_has_no_anonymous_regions(self):
        assert find_anonymous_regions(JAVA_SOURCE, Language.OTHER) == []

    def test_python_has_no_anonymous_regions(self):
        assert find_anonymous_regions(PYTHON_SOURCE, Language.PYTHON) == []


class TestAnonymousClasses:
    def test_anonymous_class_is_not_a_class_context(self):
        assert "Runnable" not in names(java_classes())
        assert all(item.name != "" for item in java_classes())

    def test_anonymous_region_is_detected(self):
        assert find_anonymous_regions(JAVA_SOURCE, Language.JAVA) == [(15, 20)]

    def test_method_inside_anonymous_class_has_no_enclosing_class(self):
        classes = java_classes()
        regions = find_anonymous_regions(JAVA_SOURCE, Language.JAVA)
        method = next(
            m
            for m in find_methods(JAVA_SOURCE, Language.JAVA)
            if m.start_line == 16
        )
        assert method.name == "run"
        assert enclosing_class_name(classes, method, regions) is None

    def test_method_declaring_anonymous_class_keeps_its_class(self):
        classes = java_classes()
        regions = find_anonymous_regions(JAVA_SOURCE, Language.JAVA)
        method = next(
            m for m in find_methods(JAVA_SOURCE, Language.JAVA) if m.name == "task"
        )
        assert enclosing_class_name(classes, method, regions) == "Outer"

    def test_multiline_anonymous_header(self):
        source = "\n".join(
            [
                "class C {",
                "    void m() {",
                "        run(new Runnable(",
                "                ) {",
                "            public void run() { }",
                "        });",
                "    }",
                "}",
            ]
        )
        regions = find_anonymous_regions(source, Language.JAVA)
        assert regions == [(3, 6)]
        assert names(find_classes(source, Language.JAVA)) == ["C"]

    def test_plain_new_expression_is_not_a_region(self):
        source = "class C {\n    void m() {\n        Repo repo = new Repo();\n    }\n}\n"
        assert find_anonymous_regions(source, Language.JAVA) == []

    def test_new_with_arguments_is_not_a_region(self):
        source = 'class C {\n    void m() {\n        call(new Repo("x", 1));\n    }\n}\n'
        assert find_anonymous_regions(source, Language.JAVA) == []


class TestEnclosingClassName:
    def setup_method(self):
        self.classes = java_classes()
        self.regions = find_anonymous_regions(JAVA_SOURCE, Language.JAVA)
        self.methods = {
            (m.name, m.start_line): m for m in find_methods(JAVA_SOURCE, Language.JAVA)
        }

    def method(self, name, start_line):
        return self.methods[(name, start_line)]

    def test_constructor_belongs_to_its_class(self):
        assert enclosing_class_name(
            self.classes, self.method("Outer", 10), self.regions
        ) == "Outer"

    def test_method_belongs_to_nested_class(self):
        assert enclosing_class_name(
            self.classes, self.method("nestedMethod", 24), self.regions
        ) == "Nested"

    def test_method_belongs_to_local_class(self):
        assert enclosing_class_name(
            self.classes, self.method("localMethod", 26), self.regions
        ) == "Local"

    def test_method_belongs_to_enum(self):
        assert enclosing_class_name(
            self.classes, self.method("on", 37), self.regions
        ) == "Mode"

    def test_method_belongs_to_record(self):
        assert enclosing_class_name(
            self.classes, self.method("sum", 41), self.regions
        ) == "Point"

    def test_abstract_method_belongs_to_abstract_class(self):
        assert enclosing_class_name(
            self.classes, self.method("run", 46), self.regions
        ) == "Base"

    def test_no_classes_yields_none(self):
        method = MethodContext(name="m", start_line=1, end_line=1)
        assert enclosing_class_name([], method) is None

    def test_method_outside_every_class(self):
        method = MethodContext(name="m", start_line=100, end_line=102)
        assert enclosing_class_name(self.classes, method, self.regions) is None

    def test_innermost_class_wins(self):
        classes = [
            ClassContext(name="A", start_line=1, end_line=10),
            ClassContext(name="B", start_line=4, end_line=8),
        ]
        method = MethodContext(name="m", start_line=5, end_line=6)
        assert enclosing_class_name(classes, method) == "B"

    def test_same_start_prefers_smaller_range(self):
        classes = [
            ClassContext(name="Wide", start_line=1, end_line=10),
            ClassContext(name="Narrow", start_line=1, end_line=4),
        ]
        method = MethodContext(name="m", start_line=2, end_line=3)
        assert enclosing_class_name(classes, method) == "Narrow"

    def test_anonymous_region_inside_named_class(self):
        classes = [ClassContext(name="C", start_line=1, end_line=10)]
        method = MethodContext(name="run", start_line=4, end_line=6)
        assert enclosing_class_name(classes, method, [(3, 7)]) is None

    def test_named_class_inside_anonymous_region_wins(self):
        classes = [
            ClassContext(name="C", start_line=1, end_line=20),
            ClassContext(name="Local", start_line=5, end_line=9),
        ]
        method = MethodContext(name="m", start_line=6, end_line=7)
        assert enclosing_class_name(classes, method, [(4, 10)]) == "Local"

    def test_regions_are_optional(self):
        classes = [ClassContext(name="C", start_line=1, end_line=10)]
        method = MethodContext(name="m", start_line=2, end_line=3)
        assert enclosing_class_name(classes, method) == "C"


class TestPythonEnclosingClass:
    def setup_method(self):
        self.classes = python_classes()
        self.methods = {
            (m.name, m.start_line): m for m in find_methods(PYTHON_SOURCE, Language.PYTHON)
        }

    def method(self, name, start_line):
        return self.methods[(name, start_line)]

    def test_instance_method(self):
        assert enclosing_class_name(
            self.classes, self.method("__init__", 18)
        ) == "Point"

    def test_static_method(self):
        assert enclosing_class_name(
            self.classes, self.method("create", 21)
        ) == "Point"

    def test_nested_class_method(self):
        assert enclosing_class_name(
            self.classes, self.method("nested_method", 26)
        ) == "Nested"

    def test_deeply_nested_class_method(self):
        assert enclosing_class_name(
            self.classes, self.method("deep_method", 28)
        ) == "Deep"

    def test_second_class_method(self):
        assert enclosing_class_name(
            self.classes, self.method("method", 34)
        ) == "Second"

    def test_top_level_function_has_no_class(self):
        assert enclosing_class_name(self.classes, self.method("top_level", 38)) is None

    def test_function_nested_in_function_has_no_class(self):
        assert (
            enclosing_class_name(self.classes, self.method("inner_function", 39))
            is None
        )


class TestBuildClassContexts:
    def test_java_file_context(self):
        assert names(build_class_contexts(java_file_context())) == [
            "Outer",
            "Nested",
            "Local",
            "Inner",
            "Mode",
            "Point",
            "Base",
            "Second",
        ]

    def test_python_file_context(self):
        assert names(build_class_contexts(python_file_context())) == [
            "Point",
            "Nested",
            "Deep",
            "Second",
        ]

    def test_content_unavailable(self):
        diff = parse_patch(JAVA_PATH, JAVA_PATCH, "modified")
        context = build_file_context(diff)
        assert context.content_available is False
        assert build_class_contexts(context) == []

    def test_removed_file(self):
        patch = "\n".join(["@@ -1,2 +0,0 @@", "-a = 1", "-b = 2"])
        diff = parse_patch("agent/app/legacy.py", patch, "removed")
        assert build_class_contexts(build_file_context(diff)) == []

    def test_empty_content(self):
        diff = parse_patch(JAVA_PATH, JAVA_PATCH, "modified")
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=""))
        assert build_class_contexts(context) == []

    def test_other_language(self):
        diff = parse_patch("README.md", JAVA_PATCH, "modified")
        context = build_file_context(
            diff, FileContent(path="README.md", content=JAVA_SOURCE)
        )
        assert build_class_contexts(context) == []

    def test_renamed_file_with_content(self):
        diff = parse_patch(
            JAVA_PATH, JAVA_PATCH, "renamed", previous_path="src/Old.java"
        )
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=JAVA_SOURCE))
        assert "Outer" in names(build_class_contexts(context))

    def test_content_without_classes(self):
        diff = parse_patch(JAVA_PATH, JAVA_PATCH, "modified")
        context = build_file_context(
            diff, FileContent(path=JAVA_PATH, content="package a;\n")
        )
        assert build_class_contexts(context) == []


class TestAttachClassContexts:
    def test_classes_and_methods_are_linked(self):
        context = java_pipeline()
        assert names(context.classes) == [
            "Outer",
            "Nested",
            "Local",
            "Inner",
            "Mode",
            "Point",
            "Base",
            "Second",
        ]
        assert len(context.methods) == 1
        assert context.methods[0].name == "Outer"
        assert context.methods[0].enclosing_class == "Outer"

    def test_file_level_enclosing_class(self):
        assert java_pipeline().enclosing_class == "Outer"

    def test_python_pipeline(self):
        context = python_pipeline()
        assert context.methods[0].name == "__init__"
        assert context.methods[0].enclosing_class == "Point"
        assert context.enclosing_class == "Point"

    def test_changed_ranges_survive(self):
        context = java_pipeline()
        assert context.methods[0].changed_ranges == [
            ChangedRange(start_line=11, end_line=11)
        ]

    def test_notes_and_diff_survive(self):
        original = java_file_context()
        context = attach_class_contexts(attach_method_contexts(original))
        assert context.file_diff == original.file_diff
        assert context.line_count == original.line_count
        assert context.notes == original.notes

    def test_input_is_not_mutated(self):
        original = attach_method_contexts(java_file_context())
        before = [method.enclosing_class for method in original.methods]
        attach_class_contexts(original)
        assert [method.enclosing_class for method in original.methods] == before
        assert original.classes == []
        assert original.enclosing_class is None

    def test_no_methods_and_several_top_level_types_stay_ambiguous(self):
        context = attach_class_contexts(java_file_context())
        assert context.methods == []
        assert context.enclosing_class is None

    def test_single_top_level_type_without_methods(self):
        source = "class Only {\n    void m() { }\n}\n"
        diff = parse_patch(JAVA_PATH, None, "modified")
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=source))
        attached = attach_class_contexts(context)
        assert names(attached.classes) == ["Only"]
        assert attached.enclosing_class == "Only"

    def test_multiple_top_level_types_are_ambiguous(self):
        context = attach_class_contexts(java_file_context())
        assert context.enclosing_class is None

    def test_top_level_python_function_has_no_enclosing_class(self):
        patch = "\n".join(["@@ -38,2 +38,2 @@", " def top_level():", "-    x = 1", "+    x = 2"])
        diff = parse_patch(PYTHON_PATH, patch, "modified")
        context = build_file_context(
            diff, FileContent(path=PYTHON_PATH, content=PYTHON_SOURCE)
        )
        attached = attach_class_contexts(attach_method_contexts(context))
        assert [method.name for method in attached.methods] == [
            "top_level",
            "inner_function",
        ]
        assert all(method.enclosing_class is None for method in attached.methods)
        assert attached.enclosing_class is None
        assert len(attached.classes) == 4

    def test_methods_in_different_classes_are_ambiguous(self):
        patch = "\n".join(
            [
                "@@ -10,3 +10,3 @@",
                "     public Outer(Repo repo) {",
                "-        this.repo = repo;",
                "+        this.repo = requireNonNull(repo);",
                "     }",
                "@@ -37,1 +37,1 @@",
                "-        public boolean on() { return this == ON; }",
                "+        public boolean on() { return this != OFF; }",
            ]
        )
        context = java_pipeline(patch=patch)
        assert sorted(m.enclosing_class for m in context.methods) == ["Mode", "Outer"]
        assert context.enclosing_class is None

    def test_anonymous_method_is_not_attributed(self):
        patch = "\n".join(
            [
                "@@ -17,3 +17,3 @@",
                "             public void run() {",
                "-                go();",
                "+                go(1);",
                "             }",
            ]
        )
        context = java_pipeline(patch=patch)
        assert [method.name for method in context.methods] == ["task", "run"]
        by_method = {method.name: method for method in context.methods}
        assert by_method["run"].enclosing_class is None
        assert by_method["task"].enclosing_class == "Outer"
        assert context.enclosing_class == "Outer"

    def test_content_unavailable_keeps_everything_empty(self):
        diff = parse_patch(JAVA_PATH, JAVA_PATCH, "modified")
        context = attach_class_contexts(build_file_context(diff))
        assert context.classes == []
        assert context.methods == []
        assert context.enclosing_class is None
        assert context.skipped_reason == "file content unavailable"

    def test_removed_file_keeps_skip_reason(self):
        patch = "\n".join(["@@ -1,2 +0,0 @@", "-a = 1", "-b = 2"])
        diff = parse_patch("agent/app/legacy.py", patch, "removed")
        context = attach_class_contexts(build_file_context(diff))
        assert context.classes == []
        assert context.skipped_reason is not None

    def test_class_context_is_not_produced_for_other_language(self):
        diff = parse_patch("README.md", JAVA_PATCH, "modified")
        context = build_file_context(
            diff, FileContent(path="README.md", content=JAVA_SOURCE)
        )
        attached = attach_class_contexts(context)
        assert attached.classes == []
        assert attached.enclosing_class is None

    def test_later_phases_stay_empty(self):
        context = java_pipeline()
        assert context.structure is None
        assert context.snippets == []

    def test_changed_symbols_still_mirror_methods(self):
        context = java_pipeline()
        assert [symbol.name for symbol in context.changed_symbols] == [
            method.name for method in context.methods
        ]

    def test_round_trip_model_validate(self):
        context = java_pipeline()
        assert FileContext.model_validate(context.model_dump()) == context

    def test_json_dump_uses_type_kind_strings(self):
        data = java_pipeline().model_dump(mode="json")
        kinds = {item["kind"] for item in data["classes"]}
        assert "CLASS" in kinds
        assert "INTERFACE" in kinds
        assert "ENUM" in kinds
        assert "RECORD" in kinds

    def test_idempotent(self):
        once = java_pipeline()
        twice = attach_class_contexts(once)
        assert twice.classes == once.classes
        assert twice.enclosing_class == once.enclosing_class
        assert [m.enclosing_class for m in twice.methods] == [
            m.enclosing_class for m in once.methods
        ]


class TestHeaderEndLine:
    """Phase 6.6: header_end_line must point at the declaration header."""

    def test_single_line_java_class(self):
        assert by_name(java_classes(), "Outer").header_end_line == 6

    def test_nested_java_class(self):
        assert by_name(java_classes(), "Nested").header_end_line == 23

    def test_local_java_class(self):
        assert by_name(java_classes(), "Local").header_end_line == 25

    def test_java_interface(self):
        assert by_name(java_classes(), "Inner").header_end_line == 31

    def test_java_enum(self):
        assert by_name(java_classes(), "Mode").header_end_line == 35

    def test_java_record(self):
        assert by_name(java_classes(), "Point").header_end_line == 40

    def test_java_one_line_class(self):
        assert by_name(java_classes(), "Second").header_end_line == 49

    def test_multiline_java_declaration(self):
        source = "\n".join(
            [
                "public class Foo",
                "        extends Bar {",
                "    void run() { }",
                "}",
            ]
        )
        classes = find_classes(source, Language.JAVA)
        assert classes[0].header_end_line == 2

    def test_multiline_java_declaration_with_annotation(self):
        source = "\n".join(
            [
                "@Service",
                "public class Box<T>",
                "        implements Repo {",
                "    void run() { }",
                "}",
            ]
        )
        classes = find_classes(source, Language.JAVA)
        assert classes[0].start_line == 1
        assert classes[0].header_end_line == 3

    def test_multiline_java_record(self):
        source = "\n".join(
            [
                "public record Point(",
                "        int x,",
                "        int y) {",
                "}",
            ]
        )
        classes = find_classes(source, Language.JAVA)
        assert classes[0].header_end_line == 3

    def test_single_line_python_class(self):
        assert by_name(python_classes(), "Nested").header_end_line == 25

    def test_decorated_python_class_header(self):
        assert by_name(python_classes(), "Point").header_end_line == 11

    def test_multiline_python_declaration(self):
        source = "\n".join(
            [
                "class Demo(",
                "    Base,",
                "):",
                "    value = 1",
            ]
        )
        classes = find_classes(source, Language.PYTHON)
        assert classes[0].header_end_line == 3

    def test_header_end_line_is_inside_the_range(self):
        for item in java_classes():
            assert item.start_line <= item.header_end_line <= item.end_line
        for item in python_classes():
            assert item.start_line <= item.header_end_line <= item.end_line

    def test_header_end_line_is_always_set(self):
        assert all(item.header_end_line > 0 for item in java_classes())
        assert all(item.header_end_line > 0 for item in python_classes())
