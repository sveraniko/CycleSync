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
    assert "operational_reliability" in payload
    assert "job_counts" in payload["operational_reliability"]
    assert "outbox_counts" in payload["operational_reliability"]
    assert "dead_letter_count" in payload["operational_reliability"]
    assert "outbox_pending_lag_seconds" in payload["operational_reliability"]
    assert "commerce" in payload
    assert "mode" in payload["commerce"]
    assert "provider_registry" in payload["commerce"]
    assert "provider_attempts" in payload["commerce"]
    assert "provider_succeeded" in payload["commerce"]
    assert "provider_failed" in payload["commerce"]
