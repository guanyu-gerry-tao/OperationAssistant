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

    return list(payload["incidents"])


def get_seed_incident(incident_id: str) -> dict[str, Any] | None:
    """Return one curated incident by id, or None when it is unknown."""

    for incident in load_seed_incidents():
        if incident["id"] == incident_id:
            return incident

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
