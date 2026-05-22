from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_json_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "ok",
        "service": "sonic-ai-v2-backend",
        "version": "0.1.0",
    }
