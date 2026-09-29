"""Tests for TaskMessage model."""

import pytest
from pydantic import ValidationError

from app.worker.models import TaskMessage


def test_parse_valid_message():
    msg = TaskMessage(
        taskId=1,
        owner="owner",
        repo="repo",
        prNumber=42,
        commitSha="abc123",
    )

    assert msg.taskId == 1
    assert msg.owner == "owner"
    assert msg.repo == "repo"
    assert msg.prNumber == 42
    assert msg.commitSha == "abc123"


def test_parse_from_valid_json():
    data = {
        "taskId": 1,
        "owner": "owner",
        "repo": "repo",
        "prNumber": 42,
        "commitSha": "abc123",
    }

    msg = TaskMessage(**data)

    assert msg.taskId == 1
    assert msg.owner == "owner"
    assert msg.repo == "repo"
    assert msg.prNumber == 42
    assert msg.commitSha == "abc123"


def test_parse_fails_when_task_id_missing():
    data = {
        "owner": "owner",
        "repo": "repo",
        "prNumber": 42,
        "commitSha": "abc123",
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_parse_fails_when_owner_missing():
    data = {
        "taskId": 1,
        "repo": "repo",
        "prNumber": 42,
        "commitSha": "abc123",
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_parse_fails_when_repo_missing():
    data = {
        "taskId": 1,
        "owner": "owner",
        "prNumber": 42,
        "commitSha": "abc123",
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_parse_fails_when_pr_number_missing():
    data = {
        "taskId": 1,
        "owner": "owner",
        "repo": "repo",
        "commitSha": "abc123",
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_parse_fails_when_commit_sha_missing():
    data = {
        "taskId": 1,
        "owner": "owner",
        "repo": "repo",
        "prNumber": 42,
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_parse_fails_when_task_id_is_string():
    data = {
        "taskId": "not-a-number",
        "owner": "owner",
        "repo": "repo",
        "prNumber": 42,
        "commitSha": "abc123",
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_parse_fails_when_pr_number_is_string():
    data = {
        "taskId": 1,
        "owner": "owner",
        "repo": "repo",
        "prNumber": "not-a-number",
        "commitSha": "abc123",
    }

    with pytest.raises(ValidationError):
        TaskMessage(**data)


def test_model_fields_match_java_producer():
    msg = TaskMessage(
        taskId=99,
        owner="zhangyu1108l",
        repo="CodeSentinel",
        prNumber=7,
        commitSha="abc123def456",
    )

    d = msg.model_dump()
    assert d == {
        "taskId": 99,
        "owner": "zhangyu1108l",
        "repo": "CodeSentinel",
        "prNumber": 7,
        "commitSha": "abc123def456",
    }