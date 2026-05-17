from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.db import check_database_status, check_redis_status
from backend.app.seeds import (
    build_placeholder_investigation,
    get_seed_incident,
    load_seed_incidents,
)


app = FastAPI(title="OperationAssistant API", version="0.1.0")

# Allow the local Vite dev server to call the API during M1 demos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def read_health() -> dict[str, object]:
    """Return service health and dependency reachability."""

    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "dependencies": {
            "database": check_database_status(settings),
            "redis": check_redis_status(settings),
        },
    }


@app.get("/api/incidents")
def list_incidents() -> dict[str, list[dict[str, object]]]:
    """Return curated incident seed records for the UI shell."""

    return {"incidents": load_seed_incidents()}


@app.get("/api/incidents/{incident_id}")
def read_incident(incident_id: str) -> dict[str, object]:
    """Return one curated incident with a static investigation placeholder."""

    incident = get_seed_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "incident": incident,
        "investigation": build_placeholder_investigation(incident),
    }
