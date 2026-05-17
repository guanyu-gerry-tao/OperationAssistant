CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    service TEXT NOT NULL,
    symptom TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS runbook_metadata (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    service TEXT NOT NULL,
    source_path TEXT NOT NULL,
    incident_pattern TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_sample_records (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(id),
    tool_name TEXT NOT NULL,
    record_type TEXT NOT NULL,
    payload JSONB NOT NULL
);
