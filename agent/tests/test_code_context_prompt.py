"""Tests for the Phase 6.7.5 Code Context prompt rendering.

Covers the renderer (CodeContext -> prompt text), the build_messages
wiring and the degraded variant. Fixtures reuse the real Phase 6.7.3
builder plus the Phase 6.6 budget, so the tests exercise the same context
the ReviewService produces.
"""

import pytest

from app.context.code_context_builder import CodeContextBuilder
from app.context.context_size_controller import (
    DEFAULT_BUDGET,
    aggregate_stats,
    aggregate_truncation,
    apply_context_budget_to_files,
)
from app.prompts.code_context import (
    render_code_context,
    render_context_unavailable,
)
from app.prompts.review import SYSTEM_PROMPT, build_messages
from app.schemas.code_context import (
    CodeContext,
    ContextBudget,
    FileContext,
    FileDiff,
    Language,
    MethodContext,
)
from app.schemas.pr_context import PrContext
from app.schemas.review import ReviewTaskRequest

COMMIT_SHA = "abc123"

JAVA_SOURCE = "\n".join(
    [
        "class Service {",
        "    private int count;",
        "    public void changed() {",
        "        count++;",
        "    }",
        "    public void helper() { }",
        "}",
    ]
) + "\n"

JAVA_PATCH = "\n".join(
    [
        "@@ -2,4 +2,4 @@",
        "     private int count;",
        "     public void changed() {",
        "-        count++;",
        "+        count += 2;",
        "     }",
    ]
)

REMOVED_PATCH = "\n".join(["@@ -1,2 +0,0 @@", "-class Gone {", "-}"])

PYTHON_SOURCE = "\n".join(
    [
        "def changed():",
        "    return 1",
        "",
        "def helper():",
        "    return 2",
    ]
) + "\n"

PYTHON_PATCH = "\n".join(
    [
        "@@ -1,2 +1,2 @@",
        " def changed():",
        "-    return 1",
        "+    return 3",
    ]
)


def make_file(**overrides):
    data = {
        "path": "src/Service.java",
        "previousPath": None,
        "status": "modified",
        "additions": 1,
        "deletions": 1,
        "changes": 2,
        "patch": JAVA_PATCH,
        "blobUrl": None,
        "content_available": True,
        "content_truncated": False,
        "content_reason": None,
        "content": JAVA_SOURCE,
    }
    data.update(overrides)
    return data


def unavailable_file(path, reason, **overrides):
    data = {
        "path": path,
        "patch": None,
        "content_available": False,
        "content_reason": reason,
        "content": None,
    }
    data.update(overrides)
    return make_file(**data)


def make_pr_context(files):
    return PrContext.model_validate(
        {
            "taskId": 7,
            "owner": "owner",
            "repo": "repo",
            "prNumber": 42,
            "commitSha": COMMIT_SHA,
            "title": "Change counter behaviour",
            "state": "open",
            "baseRef": "main",
            "headRef": "feature/counter",
            "files": files,
        }
    )


def build_context(files):
    return CodeContextBuilder().build(make_pr_context(files))


def budget_context(context, budget=DEFAULT_BUDGET):
    files = apply_context_budget_to_files(context.files, budget)
    return context.model_copy(
        update={
            "files": files,
            "stats": aggregate_stats(files),
            "truncation": aggregate_truncation(files),
        }
    )


def render(files, budget=DEFAULT_BUDGET):
    return render_code_context(budget_context(build_context(files), budget))


def make_request(**overrides):
    data = {
        "task_id": 7,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": COMMIT_SHA,
        "files": [],
    }
    data.update(overrides)
    return ReviewTaskRequest(**data)


def available_report():
    return {"available": True, "degraded": False, "reason": None}


def build_messages_with_context(files):
    context = budget_context(build_context(files))
    return build_messages(make_request(), context, available_report())


class TestNormalRendering:
    def test_contains_repository_pr_and_sha(self):
        text = render([make_file()])
        assert "repository: owner/repo" in text
        assert "pr_number: 42" in text
        assert f"head_sha: {COMMIT_SHA}" in text

    def test_contains_file_header_and_metadata(self):
        text = render([make_file()])
        assert "=== File 1/1: src/Service.java ===" in text
        assert "status: MODIFIED" in text
        assert "language: JAVA" in text
        assert "changes: +1 -1" in text
        assert "enclosing_class: Service" in text

    def test_contains_patch(self):
        text = render([make_file()])
        assert "@@ -2,4 +2,4 @@" in text
        assert "-        count++;" in text
        assert "+        count += 2;" in text

    def test_contains_changed_method_code(self):
        text = render([make_file()])
        assert "changed methods (touched by this diff):" in text
        assert "public void changed()" in text
        assert "count++;" in text
        assert "changed lines: 4-4" in text

    def test_contains_related_code(self):
        text = render([make_file()])
        assert "related code (structurally related members" in text
        assert "SIBLING_OF_CHANGED_METHOD" in text
        assert "public void helper() { }" in text
        assert "private int count;" in text

    def test_contains_classes_and_changed_symbols(self):
        text = render([make_file()])
        assert "classes: CLASS Service" in text
        assert "changed_symbols: METHOD changed" in text

    def test_contains_content_availability(self):
        text = render([make_file()])
        assert f"content: available (7 lines at revision {COMMIT_SHA}" in text

    def test_context_is_marked_as_selection(self):
        text = render([make_file()])
        assert "not the whole repository" in text

    def test_context_stats_are_rendered(self):
        text = render([make_file()])
        assert "context_stats:" in text
        assert "estimated_tokens=" in text
        assert "related_kept=" in text

    def test_base_sha_is_omitted_when_none(self):
        text = render([make_file()])
        assert "base_sha:" not in text

    def test_base_sha_is_rendered_when_present(self):
        context = budget_context(build_context([make_file()]))
        context = context.model_copy(update={"base_sha": "base123"})
        assert "base_sha: base123" in render_code_context(context)

    def test_head_sha_is_omitted_when_none(self):
        context = budget_context(build_context([make_file()]))
        context = context.model_copy(update={"head_sha": None})
        text = render_code_context(context)
        assert "head_sha:" not in text

    def test_python_file_uses_python_fence(self):
        files = [
            make_file(
                path="src/service.py",
                patch=PYTHON_PATCH,
                content=PYTHON_SOURCE,
            )
        ]
        text = render(files)
        assert "```python" in text
        assert "def changed():" in text
        assert "+    return 3" in text

    def test_message_structure_is_system_and_user(self):
        messages = build_messages_with_context([make_file()])
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_user_message_keeps_request_header(self):
        messages = build_messages_with_context([make_file()])
        user = messages[1]["content"]
        assert "task_id: 7" in user
        assert "repository: owner/repo" in user
        assert "pr_number: 42" in user
        assert f"commit_sha: {COMMIT_SHA}" in user
        assert "Changed files:" in user


class TestMultiFileRendering:
    def test_all_files_render_in_input_order(self):
        files = [
            make_file(),
            make_file(
                path="src/service.py",
                patch=PYTHON_PATCH,
                content=PYTHON_SOURCE,
            ),
        ]
        text = render(files)
        first = text.index("=== File 1/2: src/Service.java ===")
        second = text.index("=== File 2/2: src/service.py ===")
        assert first < second

    def test_file_boundaries_are_distinct(self):
        files = [
            make_file(),
            make_file(path="src/Other.java"),
        ]
        text = render(files)
        assert "=== File 1/2: src/Service.java ===" in text
        assert "=== File 2/2: src/Other.java ===" in text

    def test_every_file_block_is_closed_by_next_header(self):
        files = [make_file(), make_file(path="src/Other.java")]
        text = render(files)
        block = text.split("=== File 2/2")[1]
        assert "src/Other.java" in block


class TestUnavailableContent:
    @pytest.mark.parametrize(
        "reason",
        [
            "unsupported_language",
            "too_large",
            "binary",
            "fetch_failed:403",
            "fetch_failed:404",
            "fetch_failed:500",
            "fetch_failed:unknown",
        ],
    )
    def test_reason_is_rendered(self, reason):
        text = render([unavailable_file("src/X.java", reason)])
        assert f"content: unavailable (reason: {reason})" in text

    def test_removed_reason_is_rendered(self):
        text = render(
            [
                unavailable_file(
                    "src/Gone.java",
                    "removed",
                    status="removed",
                    patch=REMOVED_PATCH,
                )
            ]
        )
        assert "content: unavailable (reason: removed)" in text

    def test_removed_patch_is_still_rendered(self):
        text = render(
            [
                unavailable_file(
                    "src/Gone.java",
                    "removed",
                    status="removed",
                    patch=REMOVED_PATCH,
                )
            ]
        )
        assert "-class Gone {" in text

    def test_no_fabricated_code_for_unavailable_content(self):
        text = render([unavailable_file("src/X.java", "too_large")])
        assert "```" not in text
        assert "changed methods" not in text
        assert "related code" not in text

    def test_binary_never_renders_a_fence(self):
        text = render([unavailable_file("assets/logo.png", "binary")])
        assert "```" not in text

    def test_none_is_never_rendered_as_code(self):
        text = render([unavailable_file("src/X.java", "fetch_failed:404")])
        assert "None" not in text
        assert "diff: unavailable" in text

    def test_unavailable_file_does_not_break_available_sibling(self):
        files = [
            unavailable_file("src/X.java", "binary"),
            make_file(),
        ]
        text = render(files)
        assert "content: unavailable (reason: binary)" in text
        assert "public void changed()" in text

    def test_unavailable_file_keeps_its_path_and_status(self):
        text = render([unavailable_file("src/X.java", "too_large")])
        assert "=== File 1/1: src/X.java ===" in text
        assert "status: MODIFIED" in text


class TestTruncation:
    def test_truncated_context_is_declared(self):
        budget = ContextBudget(
            max_item_chars=10**6,
            max_related_chars=0,
            max_file_chars=10**6,
        )
        text = render([make_file()], budget=budget)
        assert "Context truncation" in text
        assert "INCOMPLETE" in text
        assert "related budget exceeded" in text
        assert "related:METHOD:helper" in text

    def test_not_truncated_context_has_no_declaration(self):
        text = render([make_file()])
        assert "Context truncation" not in text
        assert "INCOMPLETE" not in text

    def test_trimmed_related_item_is_flagged(self):
        context = budget_context(build_context([make_file()]))
        file_context = context.files[0]
        trimmed = file_context.related_code[0].model_copy(
            update={"truncated": True}
        )
        file_context = file_context.model_copy(
            update={"related_code": [trimmed]}
        )
        context = context.model_copy(update={"files": [file_context]})
        text = render_code_context(context)
        assert (
            "trimmed to its declaration header by the context budget" in text
        )

    def test_stats_expose_dropped_related(self):
        budget = ContextBudget(
            max_item_chars=10**6,
            max_related_chars=0,
            max_file_chars=10**6,
        )
        text = render([make_file()], budget=budget)
        assert "related_dropped=2" in text


class TestFenceSafety:
    def test_code_with_backticks_gets_a_longer_fence(self):
        file_context = FileContext(
            file_diff=FileDiff(path="src/A.java"),
            methods=[
                MethodContext(
                    name="m",
                    start_line=1,
                    end_line=2,
                    language=Language.JAVA,
                    code="String s = \"```\";",
                )
            ],
        )
        context = CodeContext(
            repository="owner/repo",
            pr_number=1,
            head_sha=COMMIT_SHA,
            files=[file_context],
        )
        text = render_code_context(context)
        assert "````java" in text
        assert "\n````" in text


class TestSystemRules:
    def test_file_path_rule_present(self):
        assert '"file_path"' in SYSTEM_PROMPT
        assert "Never report a file that was not" in SYSTEM_PROMPT

    def test_line_number_rule_present(self):
        assert '"start_line"' in SYSTEM_PROMPT
        assert "Never invent a line number" in SYSTEM_PROMPT

    def test_truncation_rule_present(self):
        assert "content unavailable" in SYSTEM_PROMPT
        assert "truncated" in SYSTEM_PROMPT
        assert "missing code is not evidence" in SYSTEM_PROMPT

    def test_existing_rules_are_kept(self):
        assert 'If no real issue is found, return {"findings": []}.' in (
            SYSTEM_PROMPT
        )
        assert "Never fabricate findings" in SYSTEM_PROMPT
        assert "Write all finding field values in English." in SYSTEM_PROMPT
        assert '"category"' in SYSTEM_PROMPT
        assert '"severity"' in SYSTEM_PROMPT


class TestDegradedPrompt:
    def test_degraded_states_pr_context_unavailable(self):
        messages = build_messages(
            make_request(),
            None,
            {"available": False, "degraded": True, "reason": "http_error:404"},
        )
        user = messages[1]["content"]
        assert "PR context unavailable" in user
        assert "http_error:404" in user

    def test_degraded_never_fabricates_code(self):
        messages = build_messages(
            make_request(),
            None,
            {"available": False, "degraded": True, "reason": "ConnectError"},
        )
        user = messages[1]["content"]
        assert "```" not in user
        assert "Code context provided" not in user
        assert "None" not in user

    def test_degraded_unknown_reason_falls_back(self):
        messages = build_messages(
            make_request(),
            None,
            {"available": False, "degraded": True, "reason": None},
        )
        assert "reason: unknown" in messages[1]["content"]

    def test_not_configured_keeps_legacy_note(self):
        messages = build_messages(
            make_request(),
            None,
            {
                "available": False,
                "degraded": False,
                "reason": "not_configured",
            },
        )
        assert messages == build_messages(make_request())
        assert "no file content" in messages[1]["content"]

    def test_available_report_without_context_falls_back(self):
        messages = build_messages(make_request(), None, available_report())
        assert "no file content" in messages[1]["content"]


class TestRenderUnavailableHelper:
    def test_reason_is_kept(self):
        text = render_context_unavailable("ReadTimeout")
        assert "PR context unavailable" in text
        assert "ReadTimeout" in text

    def test_missing_reason_becomes_unknown(self):
        assert "reason: unknown" in render_context_unavailable(None)