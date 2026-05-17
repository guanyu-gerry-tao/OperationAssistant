import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Clear cached settings so dependency smoke tests read fresh environment values."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_reports_ok_for_real_postgres_and_redis() -> None:
    database_url = os.getenv("OA_DATABASE_URL")
    redis_url = os.getenv("OA_REDIS_URL")
    if database_url is None or redis_url is None:
        pytest.skip("Dependency smoke test requires OA_DATABASE_URL and OA_REDIS_URL.")

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["dependencies"] == {
        "database": "ok",
        "redis": "ok",
    }


def test_foundation_migration_matches_incident_seed_shape() -> None:
    database_url = os.getenv("OA_DATABASE_URL")
    if database_url is None:
        pytest.skip("Migration smoke test requires OA_DATABASE_URL.")

    migration_sql = Path("backend/migrations/001_foundation.sql").read_text(encoding="utf-8")

    with psycopg.connect(database_url) as connection:
        connection.execute(migration_sql)
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'incidents'
            ORDER BY ordinal_position
            """
        ).fetchall()

    column_names = [row[0] for row in rows]
    assert "customer_impact" in column_names
    assert "likely_area" in column_names
