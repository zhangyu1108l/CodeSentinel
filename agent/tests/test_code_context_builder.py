"""Tests for the Phase 6.7.3 CodeContextBuilder."""

import pytest

from app.context.code_context_builder import CodeContextBuilder
from app.schemas.code_context import (
    ChangedRange,
    CodeContext,
    FileStatus,
    Language,
)
from app.schemas.pr_context import PrContext

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

REMOVED_PATCH = "\n".join(
    ["@@ -1,2 +0,0 @@", "-class Gone {", "-}"]
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
        "blobUrl": "https://github.com/owner/repo/blob/abc123/src/Service.java",
        "content_available": True,
        "content_truncated": False,
        "content_reason": None,
        "content": JAVA_SOURCE,
    }
    data.update(overrides)
    return data


def unavailable_file(path, reason, **overrides):
    return make_file(
        path=path,
        patch=None,
        content_available=False,
        content_reason=reason,
        content=None,
        **overrides,
    )


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


def build(files):
    return CodeContextBuilder().build(make_pr_context(files))


class TestIdentity:
    def test_repository_and_numbers(self):
        context = build([make_file()])
        assert isinstance(context, CodeContext)
        assert context.repository == "owner/repo"
        assert context.pr_number == 42
        assert context.head_sha == COMMIT_SHA

    def test_base_sha_is_not_invented(self):
        assert build([make_file()]).base_sha is None

    def test_empty_files(self):
        context = build([])
        assert context.files == []
        assert context.notes == []
        assert context.stats is None
        assert context.truncation is None


class TestAvailableContent:
    def test_diff_level_is_mapped(self):
        file_context = build([make_file()]).files[0]
        assert file_context.file_diff.path == "src/Service.java"
        assert file_context.file_diff.status is FileStatus.MODIFIED
        assert file_context.file_diff.language is Language.JAVA
        assert file_context.file_diff.patch_available is True
        assert file_context.file_diff.changed_ranges == [
            ChangedRange(start_line=4, end_line=4)
        ]

    def test_content_is_mapped(self):
        file_context = build([make_file()]).files[0]
        assert file_context.content_available is True
        assert file_context.line_count == 7
        assert file_context.content is not None
        assert file_context.content.content == JAVA_SOURCE
        assert file_context.content.revision == COMMIT_SHA
        assert file_context.content.error is None
        assert file_context.skipped_reason is None

    def test_method_and_class_context_are_attached(self):
        file_context = build([make_file()]).files[0]
        assert [method.name for method in file_context.methods] == ["changed"]
        assert file_context.methods[0].changed_ranges == [
            ChangedRange(start_line=4, end_line=4)
        ]
        assert [item.name for item in file_context.classes] == ["Service"]
        assert file_context.enclosing_class == "Service"

    def test_related_code_is_attached(self):
        file_context = build([make_file()]).files[0]
        assert sorted(item.name for item in file_context.related_code) == [
            "count",
            "helper",
        ]

    def test_python_file_is_mapped(self):
        source = "def run():\n    return 1\n"
        patch = "\n".join(
            ["@@ -1,2 +1,2 @@", " def run():", "-    return 1", "+    return 2"]
        )
        context = build(
            [
                make_file(
                    path="agent/app/demo.py",
                    patch=patch,
                    content=source,
                )
            ]
        )
        file_context = context.files[0]
        assert file_context.file_diff.language is Language.PYTHON
        assert [method.name for method in file_context.methods] == ["run"]

    def test_patch_none_stays_unavailable(self):
        file_context = build([make_file(patch=None)]).files[0]
        assert file_context.file_diff.patch_available is False
        assert file_context.file_diff.changed_ranges == []
        assert "patch unavailable" in file_context.file_diff.notes
        assert file_context.content_available is True

    def test_empty_file_content_is_available(self):
        file_context = build([make_file(content="")]).files[0]
        assert file_context.content_available is True
        assert file_context.line_count == 0
        assert file_context.content.content == ""

    def test_renamed_file_keeps_previous_path(self):
        file_context = build(
            [
                make_file(
                    path="src/New.java",
                    previousPath="src/Old.java",
                    status="renamed",
                )
            ]
        ).files[0]
        assert file_context.file_diff.status is FileStatus.RENAMED
        assert file_context.file_diff.previous_path == "src/Old.java"
        assert file_context.file_diff.path == "src/New.java"
        assert file_context.content.path == "src/New.java"


class TestUnavailableContent:
    def test_removed_file(self):
        context = build(
            [
                make_file(
                    path="src/Gone.java",
                    status="removed",
                    patch=REMOVED_PATCH,
                    content_available=False,
                    content_reason="removed",
                    content=None,
                )
            ]
        )
        file_context = context.files[0]
        assert file_context.file_diff.status is FileStatus.REMOVED
        assert file_context.file_diff.deletions == 2
        assert file_context.content_available is False
        assert file_context.skipped_reason == "file removed at head revision"
        assert "removed" in file_context.notes
        assert file_context.content is None

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
    def test_reason_is_preserved(self, reason):
        file_context = build(
            [unavailable_file("src/Other.java", reason)]
        ).files[0]
        assert file_context.content_available is False
        assert file_context.skipped_reason == "file content unavailable"
        assert reason in file_context.notes
        assert file_context.content is not None
        assert file_context.content.content is None
        assert file_context.content.error == reason

    def test_unsupported_language_file(self):
        file_context = build(
            [unavailable_file("README.md", "unsupported_language")]
        ).files[0]
        assert file_context.file_diff.language is Language.OTHER
        assert "unsupported_language" in file_context.notes

    @pytest.mark.parametrize(
        "reason",
        [
            "unsupported_language",
            "too_large",
            "binary",
            "fetch_failed:403",
        ],
    )
    def test_no_code_is_fabricated(self, reason):
        file_context = build(
            [unavailable_file("src/Other.java", reason)]
        ).files[0]
        assert file_context.content.content is None
        assert file_context.line_count == 0
        assert file_context.methods == []
        assert file_context.classes == []
        assert file_context.changed_symbols == []
        assert file_context.related_code == []
        assert file_context.enclosing_class is None
        assert file_context.structure is None
        assert file_context.snippets == []

    def test_unavailable_content_does_not_fail_the_build(self):
        context = build(
            [
                make_file(),
                unavailable_file("src/Big.java", "too_large"),
                unavailable_file("src/Bad.java", "fetch_failed:403"),
            ]
        )
        assert len(context.files) == 3
        assert [file.content_available for file in context.files] == [
            True,
            False,
            False,
        ]


class TestOrderingAndImmutability:
    def test_file_order_is_preserved(self):
        context = build(
            [
                make_file(path="c/C.java"),
                make_file(path="a/A.java"),
                unavailable_file("b/B.md", "unsupported_language"),
            ]
        )
        assert [file.file_diff.path for file in context.files] == [
            "c/C.java",
            "a/A.java",
            "b/B.md",
        ]

    def test_input_pr_context_is_not_mutated(self):
        pr_context = make_pr_context([make_file()])
        before = pr_context.model_dump()
        CodeContextBuilder().build(pr_context)
        assert pr_context.model_dump() == before

    def test_build_is_deterministic(self):
        files = [make_file(), unavailable_file("src/Big.java", "too_large")]
        assert build(files) == build(files)

    def test_budget_is_not_applied_here(self):
        context = build([make_file()])
        assert context.stats is None
        assert context.truncation is None
        assert context.files[0].stats is None
        assert context.files[0].truncation is None

    def test_no_global_notes_are_invented(self):
        assert build([make_file()]).notes == []
        assert build([unavailable_file("a.md", "unsupported_language")]).notes == []