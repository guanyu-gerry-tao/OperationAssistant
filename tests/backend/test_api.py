import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings, get_settings
from backend.app.main import app


client = TestClient(app)
EXPECTED_INCIDENT_FIELDS = {
    "id",
    "title",
    "severity",
    "service",
    "status",
    "started_at",
    "symptom",
    "customer_impact",
    "likely_area",
}


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Clear cached settings so each test controls its own environment."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_returns_not_configured_when_dependencies_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force bootstrap settings so a developer's local .env cannot change this test.
    monkeypatch.setattr(
        "backend.app.main.get_settings",
        lambda: Settings(database_url=None, redis_url=None),
    )

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


def test_health_returns_unavailable_when_dependencies_cannot_be_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Point both dependencies at closed local ports so the API reports unavailable.
    monkeypatch.setenv(
        "OA_DATABASE_URL",
        "postgresql://operation_assistant:operation_assistant@127.0.0.1:1/operation_assistant",
    )
    monkeypatch.setenv("OA_REDIS_URL", "redis://127.0.0.1:1/0")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["dependencies"] == {
        "database": "unavailable",
        "redis": "unavailable",
    }


def test_seed_incidents_endpoint_returns_all_curated_incidents() -> None:
    response = client.get("/api/incidents")

    # The endpoint should return all curated incidents with the fields the UI needs.
    assert response.status_code == 200
    body = response.json()
    incidents = body["incidents"]
    incident_ids = [incident["id"] for incident in incidents]
    assert incident_ids == ["INC-1001", "INC-1002", "INC-1003"]
    assert all(EXPECTED_INCIDENT_FIELDS.issubset(set(incident)) for incident in incidents)


def test_incident_detail_includes_placeholder_investigation_for_known_incident() -> None:
    response = client.get("/api/incidents/INC-1001")

    # A known incident includes both seed details and the honest M1 placeholder.
    assert response.status_code == 200
    body = response.json()
    assert body["incident"]["id"] == "INC-1001"
    assert body["investigation"]["status"] == "placeholder"
    assert body["investigation"]["next_capability"] == "M2 retrieval and citations"


def test_incident_detail_returns_not_found_for_unknown_incident() -> None:
    response = client.get("/api/incidents/INC-9999")

    # Unknown seed ids should be translated into the public HTTP error contract.
    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
