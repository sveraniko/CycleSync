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
    assert "search" in payload["dependencies"]
    assert "labs_triage" in payload
    assert "mode" in payload["labs_triage"]
    assert "provider_configured" in payload["labs_triage"]
    assert "catalog_source" in payload
    assert "reminders_foundation" in payload
    assert "commerce" in payload
    assert "mode" in payload["commerce"]
    assert "provider_registry" in payload["commerce"]
