"""Tests for the PR Context DTOs (Phase 6.7.2)."""

import pytest
from pydantic import ValidationError

from app.schemas.pr_context import PrContext, PrContextFile

JAVA_FILE = {
    "path": "src/App.java",
    "previousPath": None,
    "status": "modified",
    "additions": 3,
    "deletions": 1,
    "changes": 4,
    "patch": "@@ -1 +1 @@",
    "blobUrl": "https://github.com/owner/repo/blob/abc/src/App.java",
    "content_available": True,
    "content_truncated": False,
    "content_reason": None,
    "content": "class App {}",
}

JAVA_FILE_REMOVED = {
    "path": "src/Old.java",
    "previousPath": "src/Legacy.java",
    "status": "removed",
    "additions": 0,
    "deletions": 5,
    "changes": 5,
    "patch": None,
    "blobUrl": "https://github.com/owner/repo/blob/abc/src/Old.java",
    "content_available": False,
    "content_truncated": False,
    "content_reason": "removed",
    "content": None,
}

JAVA_RESPONSE = {
    "taskId": 7,
    "owner": "owner",
    "repo": "repo",
    "prNumber": 42,
    "commitSha": "abc123",
    "title": "Add review context",
    "state": "open",
    "baseRef": "main",
    "headRef": "feature/context",
    "files": [JAVA_FILE, JAVA_FILE_REMOVED],
}


def java_response(**overrides):
    payload = {**JAVA_RESPONSE, **overrides}
    return payload


class TestPrContextFile:
    def test_parses_full_java_entry(self):
        item = PrContextFile.model_validate(JAVA_FILE)
        assert item.path == "src/App.java"
        assert item.status == "modified"
        assert item.additions == 3
        assert item.deletions == 1
        assert item.changes == 4
        assert item.patch == "@@ -1 +1 @@"
        assert item.blobUrl == "https://github.com/owner/repo/blob/abc/src/App.java"
        assert item.previousPath is None

    def test_snake_case_content_fields_are_mapped(self):
        item = PrContextFile.model_validate(JAVA_FILE)
        assert item.content_available is True
        assert item.content_truncated is False
        assert item.content_reason is None
        assert item.content == "class App {}"

    def test_camel_case_content_flags_are_not_accepted(self):
        # The contract fixes these three fields to snake_case, so a camel
        # variant must not silently enable the flag.
        item = PrContextFile.model_validate(
            {
                "path": "a/A.java",
                "status": "modified",
                "contentAvailable": True,
                "contentTruncated": True,
                "contentReason": "binary",
            }
        )
        assert item.content_available is False
        assert item.content_truncated is False
        assert item.content_reason is None

    def test_previous_path_is_preserved(self):
        item = PrContextFile.model_validate(JAVA_FILE_REMOVED)
        assert item.previousPath == "src/Legacy.java"

    def test_unavailable_content_keeps_reason(self):
        item = PrContextFile.model_validate(JAVA_FILE_REMOVED)
        assert item.content is None
        assert item.content_available is False
        assert item.content_reason == "removed"

    @pytest.mark.parametrize(
        "reason",
        [
            "removed",
            "unsupported_language",
            "too_large",
            "binary",
            "fetch_failed:403",
            "fetch_failed:404",
            "fetch_failed:500",
            "fetch_failed:unknown",
        ],
    )
    def test_reason_values_are_kept_verbatim(self, reason):
        item = PrContextFile.model_validate(
            {**JAVA_FILE_REMOVED, "content_reason": reason}
        )
        assert item.content_reason == reason

    def test_empty_file_content_is_not_unavailable(self):
        item = PrContextFile.model_validate(
            {
                **JAVA_FILE,
                "content": "",
                "content_available": True,
                "content_reason": None,
            }
        )
        assert item.content == ""
        assert item.content_available is True
        assert item.content_reason is None

    def test_missing_optional_fields_use_defaults(self):
        item = PrContextFile.model_validate(
            {"path": "a/A.java", "status": "modified"}
        )
        assert item.previousPath is None
        assert item.additions == 0
        assert item.deletions == 0
        assert item.changes == 0
        assert item.patch is None
        assert item.blobUrl is None
        assert item.content_available is False
        assert item.content_truncated is False
        assert item.content_reason is None
        assert item.content is None

    def test_path_is_required(self):
        with pytest.raises(ValidationError):
            PrContextFile.model_validate({"status": "modified"})

    def test_status_is_required(self):
        with pytest.raises(ValidationError):
            PrContextFile.model_validate({"path": "a/A.java"})

    def test_invalid_counter_type_is_rejected(self):
        with pytest.raises(ValidationError):
            PrContextFile.model_validate(
                {"path": "a/A.java", "status": "modified", "additions": "many"}
            )

    def test_round_trip_model_validate(self):
        item = PrContextFile.model_validate(JAVA_FILE_REMOVED)
        assert PrContextFile.model_validate(item.model_dump()) == item


class TestPrContext:
    def test_parses_full_java_response(self):
        context = PrContext.model_validate(JAVA_RESPONSE)
        assert context.taskId == 7
        assert context.owner == "owner"
        assert context.repo == "repo"
        assert context.prNumber == 42
        assert context.commitSha == "abc123"
        assert context.title == "Add review context"
        assert context.state == "open"
        assert context.baseRef == "main"
        assert context.headRef == "feature/context"
        assert len(context.files) == 2

    def test_files_keep_the_java_order(self):
        context = PrContext.model_validate(JAVA_RESPONSE)
        assert [file.path for file in context.files] == [
            "src/App.java",
            "src/Old.java",
        ]

    def test_nested_file_types(self):
        context = PrContext.model_validate(JAVA_RESPONSE)
        assert isinstance(context.files[0], PrContextFile)
        assert context.files[0].content == "class App {}"
        assert context.files[1].content is None
        assert context.files[1].content_reason == "removed"

    def test_empty_files(self):
        context = PrContext.model_validate(java_response(files=[]))
        assert context.files == []

    def test_nullable_metadata_fields(self):
        context = PrContext.model_validate(
            java_response(
                title=None, state=None, baseRef=None, headRef=None
            )
        )
        assert context.title is None
        assert context.state is None
        assert context.baseRef is None
        assert context.headRef is None

    def test_required_identity_fields(self):
        for missing in ("taskId", "owner", "repo", "prNumber", "commitSha"):
            payload = java_response()
            del payload[missing]
            with pytest.raises(ValidationError):
                PrContext.model_validate(payload)

    def test_invalid_pr_number_type_is_rejected(self):
        with pytest.raises(ValidationError):
            PrContext.model_validate(java_response(prNumber="not-a-number"))

    def test_default_file_list_is_not_shared(self):
        first = PrContext.model_validate(java_response(files=[]))
        second = PrContext.model_validate(java_response(files=[]))
        first.files.append(PrContextFile.model_validate(JAVA_FILE))
        assert second.files == []

    def test_round_trip_model_validate(self):
        context = PrContext.model_validate(JAVA_RESPONSE)
        assert PrContext.model_validate(context.model_dump()) == context

    def test_json_round_trip_keeps_snake_case_keys(self):
        context = PrContext.model_validate(JAVA_RESPONSE)
        data = context.model_dump(mode="json")
        assert data["files"][0]["content_available"] is True
        assert data["files"][1]["content_reason"] == "removed"
        assert data["files"][1]["previousPath"] == "src/Legacy.java"
        assert data["prNumber"] == 42