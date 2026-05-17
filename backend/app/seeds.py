import json
from pathlib import Path
from typing import Any


SEED_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "seeds"
INCIDENTS_PATH = SEED_DIRECTORY / "incidents.json"


def load_seed_incidents() -> list[dict[str, Any]]:
    """Load curated incident seed records from the repository data folder."""

    # Keep M1 simple: JSON files are the source for the API until DB ingestion lands.
    with INCIDENTS_PATH.open(encoding="utf-8") as seed_file:
        payload = json.load(seed_file)

    # The seed file stores records under "incidents" so future seed groups can share the folder.
    return list(payload["incidents"])


def get_seed_incident(incident_id: str) -> dict[str, Any] | None:
    """Return one curated incident by id, or None when it is unknown."""

    # Scan the small curated seed list directly; a database lookup belongs to a later milestone.
    for incident in load_seed_incidents():
        if incident["id"] == incident_id:
            return incident

    # Return None so the API layer can translate the miss into an HTTP 404.
    return None


def build_placeholder_investigation(incident: dict[str, Any]) -> dict[str, Any]:
    """Build the static investigation placeholder shown before M2 retrieval exists."""

    # The placeholder is deliberately honest: M1 displays seed context only.
    return {
        "status": "placeholder",
        "summary": (
            "M1 provides the runnable incident shell. Retrieval, citations, "
            "tool calls, and verification are planned for later milestones."
        ),
        "primary_signal": incident["symptom"],
        "next_capability": "M2 retrieval and citations",
    }
