"""Tests for POST /api/reviews."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_request_body(**overrides):
    data = {
        "task_id": 1,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "files": [],
    }
    data.update(overrides)
    return data


def test_valid_request_returns_200():
    response = client.post("/api/reviews", json=make_request_body())
    assert response.status_code == 200


def test_response_is_review_task_result():
    response = client.post("/api/reviews", json=make_request_body(task_id=99))
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == 99
    assert data["status"] == "COMPLETED"
    assert isinstance(data["report"], dict)
    assert isinstance(data["findings"], list)


def test_findings_not_empty():
    response = client.post("/api/reviews", json=make_request_body())
    assert len(response.json()["findings"]) >= 1


def test_mock_finding_fields_complete():
    response = client.post("/api/reviews", json=make_request_body())
    finding = response.json()["findings"][0]
    for field in (
        "category",
        "severity",
        "confidence",
        "rule_id",
        "title",
        "file_path",
        "start_line",
        "end_line",
        "description",
        "reason",
        "suggestion",
        "references",
    ):
        assert field in finding
    assert finding["category"] == "QUALITY"
    assert finding["severity"] == "LOW"
    assert 0 <= finding["confidence"] <= 1


def test_missing_task_id_returns_422():
    data = make_request_body()
    del data["task_id"]
    response = client.post("/api/reviews", json=data)
    assert response.status_code == 422


def test_missing_repository_returns_422():
    data = make_request_body()
    del data["repository"]
    response = client.post("/api/reviews", json=data)
    assert response.status_code == 422


def test_health_still_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"
