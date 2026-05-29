from fastapi.testclient import TestClient
from backend.mcp_server.server import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "sonic-ai-v2-backend"
