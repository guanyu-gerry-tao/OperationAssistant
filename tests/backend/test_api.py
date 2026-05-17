from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_returns_service_and_dependency_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "operation-assistant-api",
        "dependencies": {
            "database": "not_configured",
            "redis": "not_configured",
        },
    }


def test_seed_incidents_endpoint_returns_curated_incidents() -> None:
    response = client.get("/api/incidents")

    assert response.status_code == 200
    body = response.json()
    assert len(body["incidents"]) >= 3
    assert body["incidents"][0]["id"] == "INC-1001"
    assert body["incidents"][0]["severity"] == "high"
    assert "symptom" in body["incidents"][0]


def test_incident_detail_includes_placeholder_investigation() -> None:
    response = client.get("/api/incidents/INC-1001")

    assert response.status_code == 200
    body = response.json()
    assert body["incident"]["id"] == "INC-1001"
    assert body["investigation"]["status"] == "placeholder"
    assert body["investigation"]["next_capability"] == "M2 retrieval and citations"
