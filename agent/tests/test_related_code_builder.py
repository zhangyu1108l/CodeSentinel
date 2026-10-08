"""Tests for the Phase 6.5 Related Code builder."""

from app.context.class_context_builder import attach_class_contexts
from app.context.diff_parser import parse_patch
from app.context.file_context_builder import build_file_context
from app.context.method_context_builder import attach_method_contexts
from app.context.related_code_builder import (
    CONFIDENCE_JAVA_FIELD,
    CONFIDENCE_PYTHON_ATTRIBUTE,
    KIND_PRIORITY,
    attach_related_code,
    build_related_code,
)
from app.schemas.code_context import (
    FileContent,
    FileContext,
    Language,
    RelatedCodeContext,
    RelatedKind,
    RelatedReason,
)

JAVA_PATH = "src/main/java/cn/Service.java"

JAVA_SOURCE = "\n".join(
    [
        "package cn.codesentinel;",
        "",
        "public class Service {",
        "",
        "    private final Repo repo;",
        "    private int counter = 0;",
        "",
        "    public Service(Repo repo) {",
        "        this.repo = repo;",
        "    }",
        "",
        "    public void changed() {",
        "        repo.save();",
        "    }",
        "",
        "    private void helperA() {",
        "        counter++;",
        "    }",
        "",
        "    public static class Nested {",
        "        private int inner;",
        "",
        "        void innerMethod() { }",
        "    }",
        "}",
    ]
) + "\n"

JAVA_METHOD_PATCH = "\n".join(
    [
        "@@ -12,3 +12,3 @@",
        "     public void changed() {",
        "-        repo.save();",
        "+        repo.saveAll();",
        "     }",
    ]
)

JAVA_FIELD_PATCH = "\n".join(
    [
        "@@ -5,1 +5,1 @@",
        "-    private final Repo repo;",
        "+    private final Repo repository;",
    ]
)

JAVA_NESTED_PATCH = "\n".join(
    [
        "@@ -23,1 +23,1 @@",
        "-        void innerMethod() { }",
        "+        void innerMethod() { inner++; }",
    ]
)

JAVA_TWO_METHOD_PATCH = "\n".join(
    [
        "@@ -12,3 +12,3 @@",
        "     public void changed() {",
        "-        repo.save();",
        "+        repo.saveAll();",
        "     }",
        "@@ -16,3 +16,3 @@",
        "     private void helperA() {",
        "-        counter++;",
        "+        counter += 2;",
        "     }",
    ]
)

JAVA_ANONYMOUS_SOURCE = "\n".join(
    [
        "public class Outer {",
        "",
        "    private Runnable task = new Runnable() {",
        "        public void run() {",
        "            go();",
        "        }",
        "    };",
        "",
        "    public void helper() { }",
        "}",
    ]
) + "\n"

JAVA_ANONYMOUS_METHOD_SOURCE = "\n".join(
    [
        "public class Outer {",
        "    private final Repo repo;",
        "",
        "    public void task() {",
        "        run(new Runnable() {",
        "            public void inner() {",
        "                go();",
        "            }",
        "        });",
        "    }",
        "",
        "    public void helper() { }",
        "}",
    ]
) + "\n"

PYTHON_PATH = "agent/app/service.py"

PYTHON_SOURCE = "\n".join(
    [
        "import os",
        "",
        "CONSTANT = 3",
        "",
        "",
        "class Service:",
        "    repo = None",
        "    limit: int = 10",
        "",
        "    def __init__(self, repo):",
        "        self.repo = repo",
        "",
        "    def changed(self):",
        "        local = 1",
        "        return local",
        "",
        "    def helper(self):",
        "        return 2",
        "",
        "    class Nested:",
        "        attr = 1",
        "",
        "        def inner(self):",
        "            return 3",
        "",
        "",
        "def top_level():",
        "    module_local = 1",
        "    return module_local",
    ]
) + "\n"

PYTHON_METHOD_PATCH = "\n".join(
    [
        "@@ -13,3 +13,3 @@",
        "     def changed(self):",
        "-        local = 1",
        "+        local = 2",
        "         return local",
    ]
)

PYTHON_ATTRIBUTE_PATCH = "\n".join(
    ["@@ -7,1 +7,1 @@", "-    repo = None", "+    repo = Repo()"]
)

PYTHON_NESTED_PATCH = "\n".join(
    [
        "@@ -23,2 +23,2 @@",
        "         def inner(self):",
        "-            return 3",
        "+            return 4",
    ]
)

PYTHON_TOP_LEVEL_PATCH = "\n".join(
    [
        "@@ -27,3 +27,3 @@",
        " def top_level():",
        "-    module_local = 1",
        "+    module_local = 2",
        "     return module_local",
    ]
)


def java_pipeline(patch=JAVA_METHOD_PATCH, source=JAVA_SOURCE, path=JAVA_PATH):
    return pipeline(patch, source, path)


def python_pipeline(patch=PYTHON_METHOD_PATCH, source=PYTHON_SOURCE, path=PYTHON_PATH):
    return pipeline(patch, source, path)


def pipeline(patch, source, path, status="modified"):
    diff = parse_patch(path, patch, status)
    context = build_file_context(diff, FileContent(path=path, content=source))
    return attach_class_contexts(attach_method_contexts(context))


def bare_context(patch, source, path):
    diff = parse_patch(path, patch, "modified")
    return build_file_context(diff, FileContent(path=path, content=source))


def summary(items):
    return [(item.kind, item.name) for item in items]


def ranges(items):
    return [(item.name, item.start_line, item.end_line) for item in items]


class TestJavaRelatedCode:
    def test_changed_method_yields_class_members(self):
        related = build_related_code(java_pipeline())
        assert summary(related) == [
            (RelatedKind.METHOD, "helperA"),
            (RelatedKind.FIELD, "repo"),
            (RelatedKind.FIELD, "counter"),
            (RelatedKind.CONSTRUCTOR, "Service"),
            (RelatedKind.NESTED_TYPE, "Nested"),
        ]

    def test_changed_method_itself_is_excluded(self):
        related = build_related_code(java_pipeline())
        assert "changed" not in [item.name for item in related]

    def test_enclosing_class_code_is_not_copied(self):
        related = build_related_code(java_pipeline())
        assert all(item.name != "Service" or item.kind is not RelatedKind.NESTED_TYPE
                   for item in related)
        assert not any(item.code == JAVA_SOURCE.strip() for item in related)

    def test_reason_is_sibling_of_changed_method(self):
        related = build_related_code(java_pipeline())
        assert all(
            item.reason is RelatedReason.SIBLING_OF_CHANGED_METHOD
            for item in related
        )

    def test_owner_class_is_the_anchor(self):
        related = build_related_code(java_pipeline())
        assert all(item.owner_class == "Service" for item in related)

    def test_path_is_the_changed_file(self):
        related = build_related_code(java_pipeline())
        assert all(item.path == JAVA_PATH for item in related)

    def test_confidence_and_source(self):
        related = build_related_code(java_pipeline())
        by_kind = {item.kind: item for item in related}
        assert by_kind[RelatedKind.FIELD].confidence == CONFIDENCE_JAVA_FIELD
        assert by_kind[RelatedKind.METHOD].confidence == 0.9
        assert all(item.source.value == "HEURISTIC" for item in related)

    def test_code_is_exact_slice(self):
        lines = JAVA_SOURCE.split("\n")
        for item in build_related_code(java_pipeline()):
            assert item.code == "\n".join(
                lines[item.start_line - 1 : item.end_line]
            )

    def test_field_ranges(self):
        related = build_related_code(java_pipeline())
        fields = {item.name: (item.start_line, item.end_line) for item in related}
        assert fields["repo"] == (5, 5)
        assert fields["counter"] == (6, 6)

    def test_constructor_range(self):
        related = build_related_code(java_pipeline())
        constructor = next(
            item for item in related if item.kind is RelatedKind.CONSTRUCTOR
        )
        assert (constructor.start_line, constructor.end_line) == (8, 10)

    def test_nested_type_range_and_code(self):
        related = build_related_code(java_pipeline())
        nested = next(
            item for item in related if item.kind is RelatedKind.NESTED_TYPE
        )
        assert nested.name == "Nested"
        assert (nested.start_line, nested.end_line) == (20, 24)
        assert nested.code.startswith("    public static class Nested {")

    def test_members_of_nested_class_are_not_pulled_into_outer(self):
        related = build_related_code(java_pipeline())
        assert "innerMethod" not in [item.name for item in related]
        assert "inner" not in [item.name for item in related]

    def test_changed_field_becomes_anchor(self):
        related = build_related_code(java_pipeline(patch=JAVA_FIELD_PATCH))
        assert summary(related) == [
            (RelatedKind.METHOD, "changed"),
            (RelatedKind.METHOD, "helperA"),
            (RelatedKind.FIELD, "counter"),
            (RelatedKind.CONSTRUCTOR, "Service"),
            (RelatedKind.NESTED_TYPE, "Nested"),
        ]

    def test_changed_field_itself_is_excluded(self):
        related = build_related_code(java_pipeline(patch=JAVA_FIELD_PATCH))
        assert "repo" not in [item.name for item in related]

    def test_reason_is_member_of_changed_class(self):
        related = build_related_code(java_pipeline(patch=JAVA_FIELD_PATCH))
        assert all(
            item.reason is RelatedReason.MEMBER_OF_CHANGED_CLASS
            for item in related
        )

    def test_nested_class_change_only_uses_nested_members(self):
        related = build_related_code(java_pipeline(patch=JAVA_NESTED_PATCH))
        assert summary(related) == [(RelatedKind.FIELD, "inner")]
        assert all(item.owner_class == "Nested" for item in related)

    def test_two_changed_methods_produce_no_duplicates(self):
        related = build_related_code(java_pipeline(patch=JAVA_TWO_METHOD_PATCH))
        keys = [(item.name, item.start_line, item.end_line) for item in related]
        assert len(keys) == len(set(keys))
        assert summary(related) == [
            (RelatedKind.FIELD, "repo"),
            (RelatedKind.FIELD, "counter"),
            (RelatedKind.CONSTRUCTOR, "Service"),
            (RelatedKind.NESTED_TYPE, "Nested"),
        ]

    def test_ordering_is_stable(self):
        first = build_related_code(java_pipeline())
        second = build_related_code(java_pipeline())
        assert first == second
        priorities = [KIND_PRIORITY[item.kind] for item in first]
        assert priorities == sorted(priorities)

    def test_ordering_within_kind_is_by_line(self):
        related = build_related_code(java_pipeline(patch=JAVA_FIELD_PATCH))
        methods = [item for item in related if item.kind is RelatedKind.METHOD]
        assert [item.start_line for item in methods] == sorted(
            item.start_line for item in methods
        )


class TestJavaFieldDetection:
    def related(self, source, patch):
        context = pipeline(patch, source, "src/main/java/cn/Demo.java")
        return build_related_code(context)

    def test_annotated_field_includes_annotation_line(self):
        source = "\n".join(
            [
                "public class Demo {",
                "    @Value",
                "    private int port;",
                "",
                "    void changed() { }",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -5,1 +5,1 @@", "-    void changed() { }", "+    void changed() { log(); }"])
        fields = [i for i in self.related(source, patch) if i.kind is RelatedKind.FIELD]
        assert [(f.name, f.start_line, f.end_line) for f in fields] == [("port", 2, 3)]

    def test_multiline_field_declaration(self):
        source = "\n".join(
            [
                "public class Demo {",
                "    private static final Map<String, String> M = Map.of(",
                '            "a",',
                '            "b");',
                "",
                "    void changed() { }",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -6,1 +6,1 @@", "-    void changed() { }", "+    void changed() { log(); }"])
        fields = [i for i in self.related(source, patch) if i.kind is RelatedKind.FIELD]
        assert [(f.name, f.start_line, f.end_line) for f in fields] == [("M", 2, 4)]

    def test_array_and_multiple_declarators(self):
        source = "\n".join(
            [
                "public class Demo {",
                "    private int[] counts = new int[3];",
                "    private String a, b;",
                "",
                "    void changed() { }",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -5,1 +5,1 @@", "-    void changed() { }", "+    void changed() { log(); }"])
        fields = [i for i in self.related(source, patch) if i.kind is RelatedKind.FIELD]
        assert [f.name for f in fields] == ["counts", "a"]

    def test_local_variable_is_not_a_field(self):
        source = "\n".join(
            [
                "public class Demo {",
                "    private int real;",
                "",
                "    void changed() {",
                "        String local = \"x\";",
                "    }",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -5,1 +5,1 @@", '-        String local = "x";', '+        String local = "y";'])
        names = [i.name for i in self.related(source, patch)]
        assert "local" not in names

    def test_static_initializer_is_not_a_field(self):
        source = "\n".join(
            [
                "public class Demo {",
                "    private static int value;",
                "",
                "    static {",
                "        value = 1;",
                "    }",
                "",
                "    void changed() { }",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -8,1 +8,1 @@", "-    void changed() { }", "+    void changed() { log(); }"])
        fields = [i for i in self.related(source, patch) if i.kind is RelatedKind.FIELD]
        assert [f.name for f in fields] == ["value"]

    def test_interface_constant_is_a_field(self):
        source = "\n".join(
            [
                "public interface Demo {",
                "    int MAX = 10;",
                "    void changed();",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -3,1 +3,1 @@", "-    void changed();", "+    void changed(int x);"])
        fields = [i for i in self.related(source, patch) if i.kind is RelatedKind.FIELD]
        assert [f.name for f in fields] == ["MAX"]

    def test_enum_field_belongs_to_enum(self):
        source = "\n".join(
            [
                "public enum Demo {",
                "    ON, OFF;",
                "",
                "    private final int weight = 1;",
                "",
                "    public boolean on() { return this == ON; }",
                "}",
            ]
        ) + "\n"
        patch = "\n".join(["@@ -6,1 +6,1 @@", "-    public boolean on() { return this == ON; }", "+    public boolean on() { return this != OFF; }"])
        related = self.related(source, patch)
        assert [(i.kind, i.name) for i in related] == [
            (RelatedKind.FIELD, "weight")
        ]

    def test_field_of_nested_class_stays_in_nested(self):
        related = build_related_code(java_pipeline(patch=JAVA_NESTED_PATCH))
        assert [item.owner_class for item in related] == ["Nested"]

    def test_method_declaration_is_not_a_field(self):
        related = build_related_code(java_pipeline())
        assert all(item.kind is not RelatedKind.FIELD or "(" not in item.code.split("=")[0]
                   for item in related)


class TestJavaAnonymousClass:
    def test_no_class_context_for_anonymous_body(self):
        context = pipeline(
            "\n".join(
                [
                    "@@ -4,3 +4,3 @@",
                    "         public void run() {",
                    "-            go();",
                    "+            go(1);",
                    "         }",
                ]
            ),
            JAVA_ANONYMOUS_SOURCE,
            "src/main/java/cn/Outer.java",
        )
        assert [item.name for item in context.classes] == ["Outer"]
        assert "Runnable" not in [item.name for item in context.classes]

    def test_change_inside_anonymous_body_pulls_no_outer_code(self):
        context = pipeline(
            "\n".join(
                [
                    "@@ -4,3 +4,3 @@",
                    "         public void run() {",
                    "-            go();",
                    "+            go(1);",
                    "         }",
                ]
            ),
            JAVA_ANONYMOUS_SOURCE,
            "src/main/java/cn/Outer.java",
        )
        assert context.methods[0].name == "run"
        assert context.methods[0].enclosing_class is None
        assert build_related_code(context) == []

    def test_anonymous_method_is_not_a_member_of_outer(self):
        context = pipeline(
            "\n".join(
                [
                    "@@ -6,3 +6,3 @@",
                    "             public void inner() {",
                    "-                go();",
                    "+                go(1);",
                    "             }",
                ]
            ),
            JAVA_ANONYMOUS_METHOD_SOURCE,
            "src/main/java/cn/Outer.java",
        )
        names = [item.name for item in build_related_code(context)]
        assert "inner" not in names
        assert "helper" in names
        assert "repo" in names


class TestPythonRelatedCode:
    def test_changed_method_yields_class_members(self):
        related = build_related_code(python_pipeline())
        assert summary(related) == [
            (RelatedKind.METHOD, "helper"),
            (RelatedKind.FIELD, "repo"),
            (RelatedKind.FIELD, "limit"),
            (RelatedKind.CONSTRUCTOR, "__init__"),
            (RelatedKind.NESTED_TYPE, "Nested"),
        ]

    def test_changed_method_itself_is_excluded(self):
        assert "changed" not in [
            item.name for item in build_related_code(python_pipeline())
        ]

    def test_constructor_is_classified(self):
        related = build_related_code(python_pipeline())
        constructor = next(
            item for item in related if item.kind is RelatedKind.CONSTRUCTOR
        )
        assert constructor.name == "__init__"
        assert (constructor.start_line, constructor.end_line) == (10, 11)

    def test_local_variable_is_not_a_class_attribute(self):
        assert "local" not in [
            item.name for item in build_related_code(python_pipeline())
        ]

    def test_module_level_constant_is_not_included(self):
        assert "CONSTANT" not in [
            item.name for item in build_related_code(python_pipeline())
        ]

    def test_annotated_attribute_without_value(self):
        related = build_related_code(python_pipeline())
        limit = next(item for item in related if item.name == "limit")
        assert (limit.start_line, limit.end_line) == (8, 8)
        assert limit.code == "    limit: int = 10"

    def test_field_confidence(self):
        related = build_related_code(python_pipeline())
        field = next(item for item in related if item.kind is RelatedKind.FIELD)
        assert field.confidence == CONFIDENCE_PYTHON_ATTRIBUTE

    def test_nested_type_range(self):
        related = build_related_code(python_pipeline())
        nested = next(
            item for item in related if item.kind is RelatedKind.NESTED_TYPE
        )
        assert (nested.start_line, nested.end_line) == (20, 24)

    def test_attribute_changed_becomes_anchor(self):
        related = build_related_code(
            python_pipeline(patch=PYTHON_ATTRIBUTE_PATCH)
        )
        assert summary(related) == [
            (RelatedKind.METHOD, "changed"),
            (RelatedKind.METHOD, "helper"),
            (RelatedKind.FIELD, "limit"),
            (RelatedKind.CONSTRUCTOR, "__init__"),
            (RelatedKind.NESTED_TYPE, "Nested"),
        ]
        assert all(
            item.reason is RelatedReason.MEMBER_OF_CHANGED_CLASS
            for item in related
        )

    def test_nested_class_method_only_sees_nested_members(self):
        related = build_related_code(python_pipeline(patch=PYTHON_NESTED_PATCH))
        assert summary(related) == [(RelatedKind.FIELD, "attr")]
        assert all(item.owner_class == "Nested" for item in related)

    def test_top_level_function_has_no_related_code(self):
        context = python_pipeline(patch=PYTHON_TOP_LEVEL_PATCH)
        assert context.methods[0].name == "top_level"
        assert context.methods[0].enclosing_class is None
        assert build_related_code(context) == []

    def test_code_is_exact_slice(self):
        lines = PYTHON_SOURCE.split("\n")
        for item in build_related_code(python_pipeline()):
            assert item.code == "\n".join(lines[item.start_line - 1 : item.end_line])

    def test_multiline_attribute(self):
        source = "\n".join(
            [
                "class Demo:",
                "    MAPPING = {",
                '        "a": 1,',
                "    }",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        patch = "\n".join(
            ["@@ -6,2 +6,2 @@", "     def changed(self):", "-        return 1", "+        return 2"]
        )
        context = pipeline(patch, source, "agent/app/demo.py")
        fields = [
            item for item in build_related_code(context) if item.kind is RelatedKind.FIELD
        ]
        assert [(f.name, f.start_line, f.end_line) for f in fields] == [
            ("MAPPING", 2, 4)
        ]

    def test_docstring_is_not_an_attribute(self):
        source = "\n".join(
            [
                "class Demo:",
                '    """Docstring."""',
                "",
                "    value = 1",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        patch = "\n".join(
            ["@@ -6,2 +6,2 @@", "     def changed(self):", "-        return 1", "+        return 2"]
        )
        context = pipeline(patch, source, "agent/app/demo.py")
        names = [item.name for item in build_related_code(context)]
        assert names == ["value"]

    def test_keyword_blocks_are_not_attributes(self):
        source = "\n".join(
            [
                "class Demo:",
                "    value = 1",
                "",
                "    def changed(self):",
                "        if self.value:",
                "            return 1",
                "        else:",
                "            return 2",
            ]
        ) + "\n"
        patch = "\n".join(
            ["@@ -2,1 +2,1 @@", "-    value = 1", "+    value = 2"]
        )
        context = pipeline(patch, source, "agent/app/demo.py")
        fields = [
            item.name
            for item in build_related_code(context)
            if item.kind is RelatedKind.FIELD
        ]
        assert fields == []

    def test_decorated_sibling_method(self):
        source = "\n".join(
            [
                "class Demo:",
                "    @staticmethod",
                "    def helper():",
                "        return 1",
                "",
                "    def changed(self):",
                "        return 2",
            ]
        ) + "\n"
        patch = "\n".join(
            ["@@ -6,2 +6,2 @@", "     def changed(self):", "-        return 2", "+        return 3"]
        )
        context = pipeline(patch, source, "agent/app/demo.py")
        related = build_related_code(context)
        assert [(i.kind, i.name, i.start_line) for i in related] == [
            (RelatedKind.METHOD, "helper", 2)
        ]


class TestDegradation:
    def test_content_unavailable(self):
        diff = parse_patch(JAVA_PATH, JAVA_METHOD_PATCH, "modified")
        context = build_file_context(diff)
        assert build_related_code(context) == []

    def test_removed_file(self):
        patch = "\n".join(["@@ -1,2 +0,0 @@", "-a = 1", "-b = 2"])
        diff = parse_patch("agent/app/legacy.py", patch, "removed")
        assert build_related_code(build_file_context(diff)) == []

    def test_empty_content(self):
        diff = parse_patch(JAVA_PATH, JAVA_METHOD_PATCH, "modified")
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=""))
        assert build_related_code(context) == []

    def test_other_language(self):
        diff = parse_patch("README.md", JAVA_METHOD_PATCH, "modified")
        context = build_file_context(
            diff, FileContent(path="README.md", content=JAVA_SOURCE)
        )
        assert build_related_code(context) == []

    def test_file_without_types(self):
        source = "def helper():\n    return 1\n"
        patch = "\n".join(["@@ -1,2 +1,2 @@", " def helper():", "-    return 1", "+    return 2"])
        context = pipeline(patch, source, "agent/app/plain.py")
        assert context.classes == []
        assert build_related_code(context) == []

    def test_change_outside_any_type(self):
        source = "import os\n\n\nclass Demo:\n    def m(self):\n        return 1\n"
        patch = "\n".join(["@@ -1,1 +1,1 @@", "-import os", "+import sys"])
        context = pipeline(patch, source, "agent/app/demo.py")
        assert build_related_code(context) == []

    def test_malformed_java_does_not_raise(self):
        source = "public class Demo {\n    private int x;\n    void m() {\n"
        patch = "\n".join(["@@ -2,1 +2,1 @@", "-    private int x;", "+    private int y;"])
        context = pipeline(patch, source, "src/main/java/cn/Demo.java")
        assert isinstance(build_related_code(context), list)

    def test_malformed_python_does_not_raise(self):
        source = "class Demo:\n    x = \n    def m(self):\n"
        patch = "\n".join(["@@ -2,1 +2,1 @@", "-    x = ", "+    x = 1"])
        context = pipeline(patch, source, "agent/app/demo.py")
        assert isinstance(build_related_code(context), list)

    def test_binary_file_without_patch_or_content(self):
        diff = parse_patch("infra/logo.png", None, "added")
        assert build_related_code(build_file_context(diff)) == []

    def test_no_changed_ranges(self):
        context = bare_context(None, JAVA_SOURCE, JAVA_PATH)
        context = attach_class_contexts(attach_method_contexts(context))
        assert build_related_code(context) == []


class TestWithoutPreviousAttachments:
    def test_works_without_method_and_class_context(self):
        context = bare_context(JAVA_METHOD_PATCH, JAVA_SOURCE, JAVA_PATH)
        assert context.methods == []
        assert context.classes == []
        related = build_related_code(context)
        assert summary(related) == [
            (RelatedKind.METHOD, "helperA"),
            (RelatedKind.FIELD, "repo"),
            (RelatedKind.FIELD, "counter"),
            (RelatedKind.CONSTRUCTOR, "Service"),
            (RelatedKind.NESTED_TYPE, "Nested"),
        ]

    def test_works_without_class_context_only(self):
        context = attach_method_contexts(
            bare_context(JAVA_METHOD_PATCH, JAVA_SOURCE, JAVA_PATH)
        )
        assert context.classes == []
        assert len(build_related_code(context)) == 5


class TestAttachRelatedCode:
    def test_returns_new_object(self):
        original = java_pipeline()
        result = attach_related_code(original)
        assert result is not original

    def test_original_is_not_mutated(self):
        original = java_pipeline()
        methods_before = list(original.methods)
        classes_before = list(original.classes)
        content_before = original.content
        attach_related_code(original)
        assert original.related_code == []
        assert original.methods == methods_before
        assert original.classes == classes_before
        assert original.content is content_before

    def test_related_code_is_filled(self):
        result = attach_related_code(java_pipeline())
        assert len(result.related_code) == 5
        assert all(isinstance(item, RelatedCodeContext) for item in result.related_code)

    def test_other_fields_are_preserved(self):
        original = java_pipeline()
        result = attach_related_code(original)
        assert result.file_diff == original.file_diff
        assert result.content == original.content
        assert result.line_count == original.line_count
        assert result.methods == original.methods
        assert result.classes == original.classes
        assert result.enclosing_class == original.enclosing_class
        assert result.changed_symbols == original.changed_symbols
        assert result.notes == original.notes
        assert result.skipped_reason == original.skipped_reason

    def test_later_phase_fields_stay_empty(self):
        result = attach_related_code(java_pipeline())
        assert result.structure is None
        assert result.snippets == []

    def test_idempotent(self):
        once = attach_related_code(java_pipeline())
        twice = attach_related_code(once)
        assert twice.related_code == once.related_code

    def test_round_trip_model_validate(self):
        result = attach_related_code(java_pipeline())
        assert FileContext.model_validate(result.model_dump()) == result

    def test_json_dump_uses_string_enums(self):
        data = attach_related_code(java_pipeline()).model_dump(mode="json")
        kinds = {item["kind"] for item in data["related_code"]}
        reasons = {item["reason"] for item in data["related_code"]}
        assert kinds == {"METHOD", "FIELD", "CONSTRUCTOR", "NESTED_TYPE"}
        assert reasons == {"SIBLING_OF_CHANGED_METHOD"}

    def test_empty_for_unavailable_content(self):
        diff = parse_patch(JAVA_PATH, JAVA_METHOD_PATCH, "modified")
        result = attach_related_code(build_file_context(diff))
        assert result.related_code == []
        assert result.skipped_reason == "file content unavailable"


class TestPythonMultilineStatements:
    """Defect A / Defect B regressions: multi line statements and headers."""

    def related(self, source, changed_line, path="agent/app/demo.py"):
        line = source.split("\n")[changed_line - 1]
        patch = "\n".join(
            [
                f"@@ -{changed_line - 1},2 +{changed_line - 1},2 @@",
                f" {source.split(chr(10))[changed_line - 2]}",
                f"-{line}",
                f"+{line}",
            ]
        )
        return build_related_code(pipeline(patch, source, path))

    def fields(self, source, changed_line):
        return [
            (item.name, item.start_line, item.end_line)
            for item in self.related(source, changed_line)
            if item.kind is RelatedKind.FIELD
        ]

    def test_multiline_call_field_yields_single_item(self):
        source = "\n".join(
            [
                "class Config:",
                "    model_config = SettingsConfigDict(",
                '        env_file=".env",',
                '        env_file_encoding="utf-8",',
                '        extra="ignore",',
                "    )",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 9) == [("model_config", 2, 6)]

    def test_multiline_container_field_yields_single_item(self):
        source = "\n".join(
            [
                "class Config:",
                "    CONFIG = {",
                '        "a": 1,',
                '        "b": 2,',
                "    }",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 8) == [("CONFIG", 2, 5)]

    def test_multiline_list_and_tuple_fields(self):
        source = "\n".join(
            [
                "class Config:",
                "    ITEMS = [",
                "        1,",
                "        2,",
                "    ]",
                "    PAIR = (",
                "        3,",
                "        4,",
                "    )",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 12) == [("ITEMS", 2, 5), ("PAIR", 6, 9)]

    def test_consecutive_fields_after_multiline_field(self):
        source = "\n".join(
            [
                "class Config:",
                "    first = make_config(",
                "        a=1,",
                "        b=2,",
                "    )",
                "    second = 2",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 9) == [("first", 2, 5), ("second", 6, 6)]

    def test_kwargs_are_not_fields(self):
        source = "\n".join(
            [
                "class Config:",
                "    first = make_config(",
                "        a=1,",
                "        b=2,",
                "    )",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        names = [item.name for item in self.related(source, 8)]
        assert "a" not in names
        assert "b" not in names

    def test_unassigned_multiline_call_yields_no_field(self):
        source = "\n".join(
            [
                "class Demo:",
                "    configure(",
                "        x=1,",
                "        y=2,",
                "    )",
                "    real = 3",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 9) == [("real", 6, 6)]

    def test_multiline_class_header_is_not_scanned(self):
        source = "\n".join(
            [
                "class Demo(",
                "    Base,",
                "    metaclass=Meta,",
                "):",
                "    field = 1",
                "",
                "    def changed(self):",
                "        return 2",
            ]
        ) + "\n"
        assert self.fields(source, 8) == [("field", 5, 5)]

    def test_multiline_header_kwargs_are_not_fields(self):
        source = "\n".join(
            [
                "class Demo(",
                "    Base,",
                "    metaclass=Meta,",
                "):",
                "    field = 1",
                "",
                "    def changed(self):",
                "        return 2",
            ]
        ) + "\n"
        names = [item.name for item in self.related(source, 8)]
        assert "metaclass" not in names
        assert "Base" not in names

    def test_single_line_header_with_base(self):
        source = "\n".join(
            [
                "class Demo(Base):",
                "    field = 1",
                "",
                "    def changed(self):",
                "        return 2",
            ]
        ) + "\n"
        assert self.fields(source, 5) == [("field", 2, 2)]

    def test_decorated_class_with_multiline_header(self):
        source = "\n".join(
            [
                "@dataclass",
                "class Demo(",
                "    Base,",
                "):",
                "    field: int = 1",
                "",
                "    def changed(self):",
                "        return 2",
            ]
        ) + "\n"
        assert self.fields(source, 8) == [("field", 5, 5)]

    def test_nested_class_header_and_fields(self):
        source = "\n".join(
            [
                "class Outer(",
                "    Base,",
                "):",
                "    outer_field = 1",
                "",
                "    class Inner(",
                "        Other,",
                "    ):",
                "        inner_field = 2",
                "",
                "        def changed(self):",
                "            return 3",
            ]
        ) + "\n"
        related = self.related(source, 12)
        assert [(item.name, item.owner_class) for item in related] == [
            ("inner_field", "Inner")
        ]

    def test_method_parameters_are_not_fields(self):
        source = "\n".join(
            [
                "class Demo:",
                "    value = 1",
                "",
                "    def changed(",
                "        self,",
                "        x=1,",
                "    ):",
                "        return x",
            ]
        ) + "\n"
        assert self.fields(source, 8) == [("value", 2, 2)]

    def test_multiline_string_attribute_yields_no_inner_field(self):
        source = "\n".join(
            [
                "class Demo:",
                '    TEXT = """',
                "fake = 1",
                '"""',
                "    real = 2",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        names = [item.name for item in self.related(source, 8)]
        assert "fake" not in names
        assert "real" in names
        assert "TEXT" in names

    def test_conditional_attribute_is_still_found(self):
        source = "\n".join(
            [
                "class Demo:",
                "    if sys.version_info >= (3, 9):",
                "        value: int = 0",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 6) == [("value", 3, 3)]

    def test_annotated_attribute_without_value(self):
        source = "\n".join(
            [
                "class Demo:",
                "    limit: int",
                "    mapping = dict(",
                "        a=1,",
                "    )",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        assert self.fields(source, 8) == [("limit", 2, 2), ("mapping", 3, 5)]

    def test_methods_and_nested_types_still_reported(self):
        source = "\n".join(
            [
                "class Demo:",
                "    field = make(",
                "        a=1,",
                "    )",
                "",
                "    def sibling(self):",
                "        return 1",
                "",
                "    class Inner:",
                "        pass",
                "",
                "    def changed(self):",
                "        return 2",
            ]
        ) + "\n"
        assert summary(self.related(source, 13)) == [
            (RelatedKind.METHOD, "sibling"),
            (RelatedKind.FIELD, "field"),
            (RelatedKind.NESTED_TYPE, "Inner"),
        ]

    def test_code_slice_matches_multiline_field(self):
        source = "\n".join(
            [
                "class Config:",
                "    model_config = SettingsConfigDict(",
                '        env_file=".env",',
                "    )",
                "",
                "    def changed(self):",
                "        return 1",
            ]
        ) + "\n"
        item = next(
            i for i in self.related(source, 7) if i.kind is RelatedKind.FIELD
        )
        assert item.code == "\n".join(source.split("\n")[1:4])


class TestRelatedCodeContract:
    def test_kind_priority_covers_every_kind(self):
        assert set(KIND_PRIORITY) == set(RelatedKind)

    def test_kind_priority_matches_documented_order(self):
        assert KIND_PRIORITY[RelatedKind.METHOD] < KIND_PRIORITY[RelatedKind.FIELD]
        assert KIND_PRIORITY[RelatedKind.FIELD] < KIND_PRIORITY[RelatedKind.CONSTRUCTOR]
        assert (
            KIND_PRIORITY[RelatedKind.CONSTRUCTOR]
            < KIND_PRIORITY[RelatedKind.NESTED_TYPE]
        )

    def test_every_item_has_a_reason_and_owner(self):
        for item in build_related_code(java_pipeline()):
            assert item.reason in set(RelatedReason)
            assert item.owner_class
            assert item.start_line <= item.end_line
            assert item.code

    def test_no_cross_file_items(self):
        for item in build_related_code(java_pipeline()):
            assert item.path == JAVA_PATH
