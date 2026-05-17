import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app


EXPECTED_TABLE_COLUMNS = {
    "incidents": {
        "id": ("text", "NO"),
        "title": ("text", "NO"),
        "severity": ("text", "NO"),
        "service": ("text", "NO"),
        "symptom": ("text", "NO"),
        "customer_impact": ("text", "NO"),
        "likely_area": ("text", "NO"),
        "status": ("text", "NO"),
        "started_at": ("timestamp with time zone", "NO"),
    },
    "runbook_metadata": {
        "id": ("text", "NO"),
        "title": ("text", "NO"),
        "service": ("text", "NO"),
        "source_path": ("text", "NO"),
        "incident_pattern": ("text", "NO"),
    },
    "tool_sample_records": {
        "id": ("text", "NO"),
        "incident_id": ("text", "NO"),
        "tool_name": ("text", "NO"),
        "record_type": ("text", "NO"),
        "payload": ("jsonb", "NO"),
    },
}


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Clear cached settings so dependency smoke tests read fresh environment values."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_reports_ok_for_real_postgres_and_redis() -> None:
    # Skip unless the caller explicitly points the test at real local dependencies.
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


def test_foundation_migration_matches_seed_table_shapes() -> None:
    # Skip unless the caller explicitly points the test at a disposable Postgres database.
    database_url = os.getenv("OA_DATABASE_URL")
    if database_url is None:
        pytest.skip("Migration smoke test requires OA_DATABASE_URL.")

    # Apply the M1 migration exactly as operators would apply it in a fresh database.
    migration_sql = Path("backend/migrations/001_foundation.sql").read_text(encoding="utf-8")

    with psycopg.connect(database_url) as connection:
        connection.execute(migration_sql)
        # Read schema metadata so the test can compare actual database column contracts.
        rows = connection.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = ANY(%s)
            ORDER BY table_name, ordinal_position
            """,
            (list(EXPECTED_TABLE_COLUMNS.keys()),),
        ).fetchall()
        foreign_key_rows = connection.execute(
            """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'tool_sample_records'
            """
        ).fetchall()

    # Re-group rows by table to make each expected column assertion easy to read.
    columns_by_table = {
        table_name: {
            column_name: (data_type, is_nullable)
            for row_table_name, column_name, data_type, is_nullable in rows
            if row_table_name == table_name
        }
        for table_name in EXPECTED_TABLE_COLUMNS
    }
    for table_name, expected_columns in EXPECTED_TABLE_COLUMNS.items():
        for column_name, expected_contract in expected_columns.items():
            assert columns_by_table[table_name][column_name] == expected_contract

    # The tool sample table must stay linked to incidents so seed evidence is traceable.
    assert ("tool_sample_records", "incident_id", "incidents", "id") in foreign_key_rows
