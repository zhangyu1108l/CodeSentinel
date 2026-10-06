"""Tests for the Phase 6.3 Method Context builder."""

from app.context.diff_parser import parse_patch
from app.context.file_context_builder import build_file_context
from app.context.method_context_builder import (
    CONFIDENCE_JAVA_BODY,
    CONFIDENCE_JAVA_CONSTRUCTOR,
    CONFIDENCE_JAVA_DECLARATION,
    CONFIDENCE_PYTHON_BLOCK,
    NOTE_NO_METHOD_MATCH,
    attach_method_contexts,
    build_method_contexts,
    find_methods,
    match_methods,
)
from app.schemas.code_context import (
    ChangedRange,
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
    Language,
    MethodContext,
    SymbolKind,
    SymbolSource,
)

JAVA_PATH = "src/main/java/cn/UserRepository.java"

JAVA_SOURCE = "\n".join(
    [
        "package cn.codesentinel.demo;",
        "",
        "import java.util.List;",
        "",
        "@Service",
        "public class UserRepository {",
        "",
        "    private final JdbcTemplate jdbc;",
        "",
        "    public UserRepository(JdbcTemplate jdbc) {",
        "        this.jdbc = jdbc;",
        "    }",
        "",
        "    @Override",
        "    public User findById(String id) {",
        '        String sql = "SELECT * FROM users WHERE id = " + id;',
        "        return jdbc.queryForObject(sql, mapper);",
        "    }",
        "",
        "    private List<User> findAll() {",
        "        for (User user : users) {",
        "            if (user != null) {",
        '                System.out.println("}");',
        "            }",
        "        }",
        "        return users;",
        "    }",
        "}",
    ]
) + "\n"

JAVA_BODY_PATCH = "\n".join(
    [
        "@@ -15,3 +15,3 @@",
        "     public User findById(String id) {",
        '-        String sql = "SELECT * FROM users WHERE id = " + id;',
        '+        String sql = "SELECT * FROM users WHERE id = ?";',
        "         return jdbc.queryForObject(sql, mapper);",
    ]
)

JAVA_SIGNATURE_PATCH = "\n".join(
    [
        "@@ -14,4 +14,4 @@",
        "     @Override",
        "-    public User findById(String id) {",
        "+    public User findById(String identifier) {",
        '         String sql = "x";',
        "         return null;",
    ]
)

PYTHON_PATH = "agent/app/service.py"

PYTHON_SOURCE = "\n".join(
    [
        "import os",
        "",
        "",
        "class Service:",
        '    """Summary',
        "def not_a_method():",
        '    """',
        "",
        "    def __init__(self, repo):",
        "        self.repo = repo",
        "",
        "    @staticmethod",
        "    async def fetch(name: str) -> str:",
        "        async with session.get(name) as resp:",
        "            return await resp.text()",
        "",
        "",
        "def helper():",
        "    if True:",
        "        for i in range(3):",
        "            try:",
        "                pass",
        "            except Exception:",
        "                pass",
        "    return 1",
        "",
        "",
        "def outer():",
        "    def inner():",
        "        return 1",
        "    return inner",
    ]
) + "\n"

PYTHON_BODY_PATCH = "\n".join(
    [
        "@@ -9,2 +9,2 @@",
        "     def __init__(self, repo):",
        "-        self.repo = repo",
        "+        self.repo = validate(repo)",
    ]
)


def changed(*pairs):
    return [ChangedRange(start_line=start, end_line=end) for start, end in pairs]


def java_methods(source=JAVA_SOURCE):
    return find_methods(source, Language.JAVA)


def python_methods(source=PYTHON_SOURCE):
    return find_methods(source, Language.PYTHON)


def names(methods):
    return [method.name for method in methods]


def by_name(methods, name):
    return next(method for method in methods if method.name == name)


def java_file_context(patch=JAVA_BODY_PATCH, source=JAVA_SOURCE, status="modified"):
    diff = parse_patch(JAVA_PATH, patch, status)
    return build_file_context(diff, FileContent(path=JAVA_PATH, content=source))


def python_file_context(patch=PYTHON_BODY_PATCH, source=PYTHON_SOURCE, status="modified"):
    diff = parse_patch(PYTHON_PATH, patch, status)
    return build_file_context(diff, FileContent(path=PYTHON_PATH, content=source))


class TestFindJavaMethods:
    def test_detects_constructor_and_methods(self):
        assert names(java_methods()) == [
            "UserRepository",
            "findById",
            "findAll",
        ]

    def test_method_range_covers_body(self):
        method = by_name(java_methods(), "findById")
        assert method.start_line == 14
        assert method.end_line == 18

    def test_range_starts_at_annotation(self):
        method = by_name(java_methods(), "findById")
        assert JAVA_SOURCE.split("\n")[method.start_line - 1] == "    @Override"

    def test_range_ends_at_closing_brace(self):
        method = by_name(java_methods(), "findAll")
        assert method.end_line == 27
        assert JAVA_SOURCE.split("\n")[method.end_line - 1] == "    }"

    def test_class_level_annotation_is_not_absorbed(self):
        method = by_name(java_methods(), "UserRepository")
        assert method.start_line == 10

    def test_class_declaration_is_not_a_method(self):
        assert "UserRepository" in names(java_methods())
        assert by_name(java_methods(), "UserRepository").start_line == 10

    def test_kind_language_and_source(self):
        method = by_name(java_methods(), "findById")
        assert method.kind is SymbolKind.METHOD
        assert method.language is Language.JAVA
        assert method.source is SymbolSource.HEURISTIC

    def test_confidence_for_method_with_body(self):
        assert by_name(java_methods(), "findById").confidence == CONFIDENCE_JAVA_BODY

    def test_confidence_for_constructor_with_modifier(self):
        method = by_name(java_methods(), "UserRepository")
        assert method.confidence == CONFIDENCE_JAVA_BODY

    def test_confidence_for_constructor_without_modifier(self):
        source = "class C {\n    C(Dep dep) {\n        this.dep = dep;\n    }\n}"
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["C"]
        assert methods[0].confidence == CONFIDENCE_JAVA_CONSTRUCTOR

    def test_signature_is_single_line_without_brace(self):
        assert by_name(java_methods(), "findById").signature == (
            "public User findById(String id)"
        )

    def test_code_is_the_exact_source_slice(self):
        method = by_name(java_methods(), "findAll")
        expected = "\n".join(JAVA_SOURCE.split("\n")[19:27])
        assert method.code == expected

    def test_code_line_count_matches_range(self):
        for method in java_methods():
            assert len(method.code.split("\n")) == (
                method.end_line - method.start_line + 1
            )

    def test_control_blocks_are_not_methods(self):
        assert names(java_methods()) == [
            "UserRepository",
            "findById",
            "findAll",
        ]

    def test_brace_inside_string_does_not_end_method(self):
        method = by_name(java_methods(), "findAll")
        assert method.end_line == 27
        assert 'System.out.println("}");' in method.code

    def test_no_changed_ranges_on_discovery(self):
        assert all(method.changed_ranges == [] for method in java_methods())


class TestJavaEdgeCases:
    def test_interface_methods_without_body(self):
        source = "\n".join(
            [
                "public interface Repo {",
                "    User findById(String id);",
                "    void save(User user);",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["findById", "save"]
        assert all(m.start_line == m.end_line for m in methods)
        assert all(m.confidence == CONFIDENCE_JAVA_DECLARATION for m in methods)

    def test_abstract_method_without_body(self):
        source = "\n".join(
            [
                "public abstract class C {",
                "    public abstract void run();",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["run"]
        assert methods[0].confidence == CONFIDENCE_JAVA_DECLARATION

    def test_multiline_signature(self):
        source = "\n".join(
            [
                "public class C {",
                "    public ResponseEntity<Void> handle(",
                "            String signature,",
                "            byte[] body) {",
                "        return ok();",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["handle"]
        assert methods[0].start_line == 2
        assert methods[0].end_line == 6
        assert methods[0].signature == (
            "public ResponseEntity<Void> handle(String signature, byte[] body)"
        )

    def test_multiline_annotation(self):
        source = "\n".join(
            [
                "public class C {",
                "    @RequestMapping(",
                '        value = "/x")',
                "    public String foo() {",
                '        return "x";',
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["foo"]
        assert methods[0].start_line == 2
        assert methods[0].end_line == 6

    def test_single_line_method(self):
        source = "public class C {\n    public int get() { return 1; }\n}"
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["get"]
        assert methods[0].start_line == 2
        assert methods[0].end_line == 2
        assert methods[0].signature == "public int get()"

    def test_static_and_generic_methods(self):
        source = "\n".join(
            [
                "public class C {",
                "    public static <T> List<T> map(List<T> in) {",
                "        return in;",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["map"]
        assert methods[0].signature == "public static <T> List<T> map(List<T> in)"

    def test_nested_generic_return_type(self):
        source = "\n".join(
            [
                "public class C {",
                "    private Map<String, List<Integer>> grouped(Map<String, List<Integer>> in) {",
                "        return in;",
                "    }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["grouped"]

    def test_annotated_parameters(self):
        source = "\n".join(
            [
                "public class C {",
                "    public void save(@Valid @Size(max = 10) String name, final int count) {",
                "        store(name, count);",
                "    }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["save"]

    def test_anonymous_inner_class_method(self):
        source = "\n".join(
            [
                "public class C {",
                "    public Runnable task() {",
                "        return new Runnable() {",
                "            @Override",
                "            public void run() {",
                "                doWork();",
                "            }",
                "        };",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["task", "run"]
        assert by_name(methods, "task").start_line == 2
        assert by_name(methods, "task").end_line == 9
        assert by_name(methods, "run").start_line == 4
        assert by_name(methods, "run").end_line == 7

    def test_enum_constant_body_is_not_a_method(self):
        source = "\n".join(
            [
                "public enum E {",
                "    VALUE(1) {",
                "        @Override",
                "        public int get() {",
                "            return 1;",
                "        }",
                "    };",
                "    private final int v;",
                "    E(int v) { this.v = v; }",
                "    public int v() { return v; }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["get", "E", "v"]
        assert "VALUE" not in names(methods)

    def test_enum_constant_with_string_argument_is_not_a_method(self):
        source = "\n".join(
            [
                "public enum E {",
                "    A(1) {",
                "        void x() { }",
                "    },",
                '    B("s");',
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["x"]

    def test_enum_constant_without_arguments_is_not_a_method(self):
        source = "\n".join(
            [
                "public enum E {",
                "    A,",
                "    B;",
                "    public int v() { return 1; }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["v"]

    def test_all_caps_constructor_is_detected(self):
        source = "\n".join(
            [
                "public class DTO {",
                "    DTO(Repo repo) {",
                "        this.repo = repo;",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["DTO"]
        assert methods[0].confidence == CONFIDENCE_JAVA_CONSTRUCTOR

    def test_no_argument_constructor(self):
        source = "public class C {\n    C() {\n        init();\n    }\n}"
        assert names(find_methods(source, Language.JAVA)) == ["C"]

    def test_inline_annotation_before_modifier(self):
        source = "\n".join(
            [
                "public class C {",
                "    @Bean public String foo() {",
                "        return null;",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["foo"]
        assert methods[0].start_line == 2
        assert methods[0].end_line == 4

    def test_inline_annotation_with_value(self):
        source = "\n".join(
            [
                "public class C {",
                '    @SuppressWarnings("unchecked") public void bar() {',
                "    }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["bar"]

    def test_call_statement_is_not_a_method(self):
        source = "\n".join(
            [
                "public class C {",
                "    void a() {",
                "        Compute.run(1);",
                "    }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["a"]

    def test_deeply_nested_generic_return_type(self):
        source = "\n".join(
            [
                "public class C {",
                "    Map<String, List<Map<Integer, String>>> deep(",
                "            Map<String, List<Map<Integer, String>>> in) {",
                "        return in;",
                "    }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["deep"]

    def test_throws_clause(self):
        source = "\n".join(
            [
                "public class C {",
                "    void read() throws IOException {",
                "        Files.read(p);",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["read"]
        assert methods[0].signature == "void read() throws IOException"

    def test_record_declaration_is_not_a_method(self):
        source = "\n".join(
            [
                "public record Point(int x, int y) {",
                "    public static Point of(int x) { return new Point(x, x); }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["of"]

    def test_statements_inside_method_are_not_methods(self):
        source = "\n".join(
            [
                "public class C {",
                "    public void run() {",
                "        doWork();",
                "        Helper.call(1);",
                "        synchronized (lock) {",
                "            count++;",
                "        }",
                "        if (flag) {",
                "            for (int i = 0; i < 3; i++) {",
                "                while (flag) { }",
                "            }",
                "        } else {",
                "            return;",
                "        }",
                "        Runnable task = () -> {",
                "            go();",
                "        };",
                "    }",
                "}",
            ]
        )
        assert names(find_methods(source, Language.JAVA)) == ["run"]

    def test_comments_are_ignored(self):
        source = "\n".join(
            [
                "public class C {",
                "    /* public void fake() { } */",
                "    // public void fake2() {",
                "    public void real() {",
                "        /* } */",
                "    }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["real"]
        assert methods[0].end_line == 6

    def test_text_block_does_not_break_brace_depth(self):
        source = "\n".join(
            [
                "public class C {",
                "    public String text() {",
                '        String s = """',
                "            public void inside() {",
                "            }",
                '        """;',
                "        return s;",
                "    }",
                "    public void after() { }",
                "}",
            ]
        )
        methods = find_methods(source, Language.JAVA)
        assert names(methods) == ["text", "after"]
        assert by_name(methods, "text").end_line == 8

    def test_empty_source(self):
        assert find_methods("", Language.JAVA) == []

    def test_source_without_declarations(self):
        assert find_methods("package a;\n\nimport b.C;\n", Language.JAVA) == []

    def test_truncated_source_does_not_raise(self):
        source = "public class C {\n    public void run() {\n        doWork();\n"
        assert find_methods(source, Language.JAVA) == []

    def test_unbalanced_closing_brace_does_not_raise(self):
        source = "}\npublic class C {\n    public void run() { }\n}"
        assert names(find_methods(source, Language.JAVA)) == ["run"]

    def test_package_private_method(self):
        source = "class C {\n    void work() { }\n}"
        assert names(find_methods(source, Language.JAVA)) == ["work"]

    def test_top_level_line_is_not_a_method(self):
        source = "Helper.call(1);\npublic class C {\n    void work() { }\n}"
        assert names(find_methods(source, Language.JAVA)) == ["work"]


class TestFindPythonMethods:
    def test_detects_methods_and_functions(self):
        assert names(python_methods()) == [
            "__init__",
            "fetch",
            "helper",
            "outer",
            "inner",
        ]

    def test_method_inside_class(self):
        method = by_name(python_methods(), "__init__")
        assert method.kind is SymbolKind.METHOD
        assert method.start_line == 9
        assert method.end_line == 10

    def test_top_level_function(self):
        method = by_name(python_methods(), "helper")
        assert method.kind is SymbolKind.FUNCTION
        assert method.start_line == 18
        assert method.end_line == 25

    def test_nested_function_is_function_not_method(self):
        method = by_name(python_methods(), "inner")
        assert method.kind is SymbolKind.FUNCTION
        assert method.start_line == 29
        assert method.end_line == 30

    def test_outer_function_contains_nested(self):
        outer = by_name(python_methods(), "outer")
        assert (outer.start_line, outer.end_line) == (28, 31)

    def test_decorator_is_included(self):
        method = by_name(python_methods(), "fetch")
        assert method.start_line == 12
        assert method.end_line == 15

    def test_async_def_signature(self):
        method = by_name(python_methods(), "fetch")
        assert method.signature == "async def fetch(name: str) -> str:"

    def test_language_and_source(self):
        method = by_name(python_methods(), "helper")
        assert method.language is Language.PYTHON
        assert method.source is SymbolSource.HEURISTIC
        assert method.confidence == CONFIDENCE_PYTHON_BLOCK

    def test_code_is_the_exact_source_slice(self):
        method = by_name(python_methods(), "helper")
        assert method.code == "\n".join(PYTHON_SOURCE.split("\n")[17:25])

    def test_class_is_not_a_method(self):
        assert "Service" not in names(python_methods())

    def test_control_blocks_are_not_methods(self):
        for keyword in ("if", "for", "try", "except", "with", "while"):
            assert keyword not in names(python_methods())

    def test_def_inside_docstring_is_ignored(self):
        assert "not_a_method" not in names(python_methods())

    def test_docstring_line_at_column_zero_does_not_end_block(self):
        methods = python_methods()
        assert by_name(methods, "__init__").end_line == 10

    def test_def_inside_string_literal_is_ignored(self):
        source = 'VALUE = "def fake():"\n\n\ndef real():\n    return 1\n'
        assert names(find_methods(source, Language.PYTHON)) == ["real"]

    def test_commented_def_is_ignored(self):
        source = "# def fake():\n#     pass\n\n\ndef real():\n    return 1\n"
        assert names(find_methods(source, Language.PYTHON)) == ["real"]

    def test_multiline_decorator(self):
        source = "\n".join(
            [
                "class C:",
                "    @app.route(",
                '        "/x",',
                "    )",
                "    def routed(self):",
                "        return 1",
            ]
        )
        methods = find_methods(source, Language.PYTHON)
        assert names(methods) == ["routed"]
        assert methods[0].start_line == 2
        assert methods[0].end_line == 6

    def test_decorator_with_continuation_line(self):
        source = "\n".join(
            [
                "class C:",
                '    @app.route("/y",',
                '               methods=["GET"])',
                "    def routed(self):",
                "        return 2",
            ]
        )
        methods = find_methods(source, Language.PYTHON)
        assert methods[0].start_line == 2
        assert methods[0].end_line == 5

    def test_one_line_function(self):
        source = "def one_liner(): return 2\n"
        methods = find_methods(source, Language.PYTHON)
        assert methods[0].start_line == 1
        assert methods[0].end_line == 1
        assert methods[0].signature == "def one_liner():"
        assert methods[0].code == "def one_liner(): return 2"

    def test_multiline_signature(self):
        source = "\n".join(
            [
                "def multi(",
                "    a,",
                "    b: int = 3,",
                "):",
                "    return a + b",
            ]
        )
        methods = find_methods(source, Language.PYTHON)
        assert methods[0].start_line == 1
        assert methods[0].end_line == 5
        assert methods[0].signature == "def multi(a, b: int = 3,):"

    def test_colon_in_default_value_does_not_end_header(self):
        source = 'def f(x: int = 3):\n    return x\n'
        methods = find_methods(source, Language.PYTHON)
        assert methods[0].signature == "def f(x: int = 3):"
        assert methods[0].end_line == 2

    def test_colon_inside_string_default_does_not_end_header(self):
        source = 'def f(x="a:b"):\n    return x\n'
        methods = find_methods(source, Language.PYTHON)
        assert methods[0].end_line == 2

    def test_trailing_comment_belongs_to_block(self):
        source = "def f():\n    return 1\n    # note\n"
        assert find_methods(source, Language.PYTHON)[0].end_line == 3

    def test_blank_lines_do_not_extend_block(self):
        source = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"
        methods = find_methods(source, Language.PYTHON)
        assert by_name(methods, "f").end_line == 2
        assert by_name(methods, "g").start_line == 5

    def test_tab_indentation(self):
        source = "class C:\n\tdef m(self):\n\t\treturn 1\n"
        methods = find_methods(source, Language.PYTHON)
        assert names(methods) == ["m"]
        assert methods[0].kind is SymbolKind.METHOD
        assert methods[0].end_line == 3

    def test_nested_class_method(self):
        source = "\n".join(
            [
                "class Outer:",
                "    class Inner:",
                "        def deep(self):",
                "            return 1",
            ]
        )
        methods = find_methods(source, Language.PYTHON)
        assert names(methods) == ["deep"]
        assert methods[0].kind is SymbolKind.METHOD

    def test_triple_quoted_body_at_column_zero(self):
        source = "\n".join(
            [
                "def text_block():",
                '    text = """',
                "zero indent content",
                '"""',
                "    return text",
            ]
        )
        methods = find_methods(source, Language.PYTHON)
        assert methods[0].start_line == 1
        assert methods[0].end_line == 5

    def test_empty_source(self):
        assert find_methods("", Language.PYTHON) == []

    def test_source_without_declarations(self):
        assert find_methods("import os\n\nVALUE = 1\n", Language.PYTHON) == []

    def test_unterminated_triple_quote_does_not_raise(self):
        source = 'def f():\n    text = """\nnever closed\n'
        assert isinstance(find_methods(source, Language.PYTHON), list)

    def test_unterminated_paren_does_not_raise(self):
        source = "def f(a, b:\n    return a\n"
        assert find_methods(source, Language.PYTHON) == []

    def test_no_changed_ranges_on_discovery(self):
        assert all(m.changed_ranges == [] for m in python_methods())


class TestUnsupportedLanguage:
    def test_other_language_has_no_methods(self):
        assert find_methods("# title\n\ntext\n", Language.OTHER) == []

    def test_markdown_content_is_not_parsed_as_python(self):
        assert find_methods(PYTHON_SOURCE, Language.OTHER) == []


class TestMatchMethods:
    def test_range_inside_body(self):
        matched = match_methods(java_methods(), changed((16, 16)))
        assert names(matched) == ["findById"]
        assert matched[0].changed_ranges == changed((16, 16))

    def test_range_on_signature_line(self):
        matched = match_methods(java_methods(), changed((15, 15)))
        assert names(matched) == ["findById"]

    def test_range_on_annotation_line(self):
        matched = match_methods(java_methods(), changed((14, 14)))
        assert names(matched) == ["findById"]

    def test_range_on_closing_brace(self):
        matched = match_methods(java_methods(), changed((18, 18)))
        assert names(matched) == ["findById"]

    def test_range_spanning_two_methods(self):
        matched = match_methods(java_methods(), changed((17, 21)))
        assert names(matched) == ["findById", "findAll"]
        assert all(m.changed_ranges == changed((17, 21)) for m in matched)

    def test_two_ranges_in_one_method_produce_one_context(self):
        matched = match_methods(java_methods(), changed((16, 16), (17, 17)))
        assert len(matched) == 1
        assert matched[0].name == "findById"
        assert matched[0].changed_ranges == changed((16, 16), (17, 17))

    def test_duplicate_ranges_are_collapsed(self):
        matched = match_methods(java_methods(), changed((16, 16), (16, 16)))
        assert len(matched) == 1
        assert matched[0].changed_ranges == changed((16, 16))

    def test_partial_overlap_from_left(self):
        matched = match_methods(java_methods(), changed((10, 15)))
        assert names(matched) == ["UserRepository", "findById"]

    def test_partial_overlap_from_right(self):
        matched = match_methods(java_methods(), changed((26, 40)))
        assert names(matched) == ["findAll"]

    def test_range_outside_any_method(self):
        assert match_methods(java_methods(), changed((3, 3))) == []

    def test_range_beyond_file_length(self):
        assert match_methods(java_methods(), changed((500, 520))) == []

    def test_no_ranges(self):
        assert match_methods(java_methods(), []) == []

    def test_no_methods(self):
        assert match_methods([], changed((16, 16))) == []

    def test_input_methods_are_not_mutated(self):
        methods = java_methods()
        match_methods(methods, changed((16, 16), (17, 17)))
        assert all(method.changed_ranges == [] for method in methods)

    def test_nested_methods_both_match(self):
        methods = python_methods()
        matched = match_methods(methods, changed((30, 30)))
        assert names(matched) == ["outer", "inner"]

    def test_python_method_match(self):
        matched = match_methods(python_methods(), changed((10, 10)))
        assert names(matched) == ["__init__"]

    def test_decorator_line_match_in_python(self):
        matched = match_methods(python_methods(), changed((12, 12)))
        assert names(matched) == ["fetch"]

    def test_order_follows_declaration_order(self):
        matched = match_methods(java_methods(), changed((11, 11), (21, 21)))
        assert names(matched) == ["UserRepository", "findAll"]


class TestBuildMethodContexts:
    def test_java_file_context(self):
        contexts = build_method_contexts(java_file_context())
        assert names(contexts) == ["findById"]
        assert contexts[0].changed_ranges == changed((16, 16))

    def test_signature_change(self):
        contexts = build_method_contexts(java_file_context(patch=JAVA_SIGNATURE_PATCH))
        assert names(contexts) == ["findById"]

    def test_python_file_context(self):
        contexts = build_method_contexts(python_file_context())
        assert names(contexts) == ["__init__"]

    def test_content_unavailable(self):
        diff = parse_patch(JAVA_PATH, JAVA_BODY_PATCH, "modified")
        context = build_file_context(diff)
        assert context.content_available is False
        assert build_method_contexts(context) == []

    def test_removed_file(self):
        patch = "\n".join(["@@ -1,2 +0,0 @@", "-a = 1", "-b = 2"])
        diff = parse_patch("agent/app/legacy.py", patch, "removed")
        context = build_file_context(diff)
        assert build_method_contexts(context) == []

    def test_renamed_file_with_content(self):
        diff = parse_patch(
            JAVA_PATH, JAVA_BODY_PATCH, "renamed", previous_path="src/Old.java"
        )
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=JAVA_SOURCE))
        assert names(build_method_contexts(context)) == ["findById"]

    def test_empty_content(self):
        diff = parse_patch(JAVA_PATH, JAVA_BODY_PATCH, "modified")
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=""))
        assert build_method_contexts(context) == []

    def test_language_other(self):
        diff = parse_patch("README.md", JAVA_BODY_PATCH, "modified")
        context = build_file_context(
            diff, FileContent(path="README.md", content=JAVA_SOURCE)
        )
        assert build_method_contexts(context) == []

    def test_range_beyond_content_does_not_raise(self):
        diff = FileDiff(
            path=JAVA_PATH,
            status=FileStatus.MODIFIED,
            language=Language.JAVA,
            changed_ranges=changed((900, 910)),
            patch_available=True,
        )
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=JAVA_SOURCE))
        assert build_method_contexts(context) == []

    def test_no_changed_ranges(self):
        diff = FileDiff(path=JAVA_PATH, status=FileStatus.MODIFIED, language=Language.JAVA)
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=JAVA_SOURCE))
        assert build_method_contexts(context) == []


class TestAttachMethodContexts:
    def test_methods_and_symbols_are_filled(self):
        context = attach_method_contexts(java_file_context())
        assert names(context.methods) == ["findById"]
        assert len(context.changed_symbols) == 1
        symbol = context.changed_symbols[0]
        assert symbol.kind is SymbolKind.METHOD
        assert symbol.name == "findById"
        assert symbol.start_line == 14
        assert symbol.end_line == 18
        assert symbol.source is SymbolSource.HEURISTIC
        assert symbol.confidence == CONFIDENCE_JAVA_BODY

    def test_diff_and_content_are_untouched(self):
        original = java_file_context()
        context = attach_method_contexts(original)
        assert context.file_diff == original.file_diff
        assert context.line_count == original.line_count
        assert context.content_available is True

    def test_class_context_is_not_produced(self):
        context = attach_method_contexts(java_file_context())
        assert context.structure is None
        assert context.enclosing_class is None
        assert context.snippets == []

    def test_input_is_not_mutated(self):
        original = java_file_context()
        attach_method_contexts(original)
        assert original.methods == []
        assert original.changed_symbols == []

    def test_existing_notes_are_preserved(self):
        diff = parse_patch(JAVA_PATH, JAVA_BODY_PATCH, "renamed")
        context = build_file_context(diff, FileContent(path=JAVA_PATH, content=JAVA_SOURCE))
        attached = attach_method_contexts(context)
        assert "renamed file without previous path" in attached.notes

    def test_unmatched_range_is_noted(self):
        diff = parse_patch("agent/app/service.py", PYTHON_BODY_PATCH, "modified")
        diff = diff.model_copy(
            update={"changed_ranges": changed((1, 1), (10, 10))}
        )
        context = build_file_context(
            diff, FileContent(path=PYTHON_PATH, content=PYTHON_SOURCE)
        )
        attached = attach_method_contexts(context)
        assert names(attached.methods) == ["__init__"]
        assert any(NOTE_NO_METHOD_MATCH in note for note in attached.notes)

    def test_note_is_added_once(self):
        diff = parse_patch(PYTHON_PATH, PYTHON_BODY_PATCH, "modified")
        diff = diff.model_copy(
            update={"changed_ranges": changed((1, 1), (10, 10))}
        )
        context = build_file_context(
            diff, FileContent(path=PYTHON_PATH, content=PYTHON_SOURCE)
        )
        first = attach_method_contexts(context)
        second = attach_method_contexts(first)
        assert len(second.notes) == len(first.notes)
        assert sum(NOTE_NO_METHOD_MATCH in note for note in second.notes) == 1
        assert names(second.methods) == names(first.methods)

    def test_no_note_when_every_range_matched(self):
        context = attach_method_contexts(java_file_context())
        assert not any(NOTE_NO_METHOD_MATCH in note for note in context.notes)

    def test_no_note_when_content_unavailable(self):
        diff = parse_patch(JAVA_PATH, JAVA_BODY_PATCH, "modified")
        context = build_file_context(diff)
        attached = attach_method_contexts(context)
        assert attached.methods == []
        assert not any(NOTE_NO_METHOD_MATCH in note for note in attached.notes)
        assert attached.skipped_reason == context.skipped_reason

    def test_removed_file_keeps_skip_reason(self):
        patch = "\n".join(["@@ -1,2 +0,0 @@", "-a = 1", "-b = 2"])
        diff = parse_patch("agent/app/legacy.py", patch, "removed")
        attached = attach_method_contexts(build_file_context(diff))
        assert attached.methods == []
        assert attached.skipped_reason is not None

    def test_round_trip_model_validate(self):
        context = attach_method_contexts(java_file_context())
        assert FileContext.model_validate(context.model_dump()) == context

    def test_methods_are_empty_by_default(self):
        assert java_file_context().methods == []


class TestMethodContextDefaults:
    def test_required_fields(self):
        method = MethodContext(name="run", start_line=1, end_line=2)
        assert method.kind is SymbolKind.METHOD
        assert method.language is Language.OTHER
        assert method.signature == ""
        assert method.code == ""
        assert method.source is SymbolSource.HEURISTIC
        assert method.confidence == 0.0
        assert method.changed_ranges == []

    def test_default_ranges_are_not_shared(self):
        first = MethodContext(name="a", start_line=1, end_line=1)
        second = MethodContext(name="b", start_line=1, end_line=1)
        first.changed_ranges.append(ChangedRange(start_line=1, end_line=1))
        assert second.changed_ranges == []
