from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_up():
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["service"] == "codesentinel-ai"