from fastapi.testclient import TestClient

from app.main import app


def test_live() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnostics_shape() -> None:
    with TestClient(app) as client:
        response = client.get("/health/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert "readiness" in payload
    assert "dependencies" in payload
    assert "postgres" in payload["dependencies"]
    assert "redis" in payload["dependencies"]
    assert "catalog_source" in payload
