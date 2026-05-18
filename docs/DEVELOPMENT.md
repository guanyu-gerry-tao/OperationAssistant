# Development Guide

OperationAssistant has a runnable local foundation. This guide records the public development commands and conventions for the current implementation.

## Repository Status

- The backend is a Python/FastAPI app under `backend/`.
- The frontend is a React/TypeScript/Vite app under `frontend/`.
- Local PostgreSQL/pgvector and Redis run through Docker Compose.
- Curated seed data is loaded from JSON files under `data/seeds/`.
- Runbook retrieval data is loaded from Markdown files under `data/runbooks/`.
- Public docs should only describe implemented behavior as implemented. Tool calling, approval, answer verification, and eval dashboards are still planned.

## Setup

Create the Python environment and install backend dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Install frontend dependencies:

```bash
npm --prefix frontend install
```

Start data services:

```bash
docker compose up -d postgres redis
```

## Expected Local Development Flow

1. Start PostgreSQL/pgvector and Redis with Docker Compose.
2. Run `make dev` to start the backend and frontend development servers.
3. Open the Vite URL shown in the terminal.
4. Run backend tests, frontend tests, and the frontend build before opening a PR.

The backend defaults used by `make dev` are:

```bash
OA_DATABASE_URL=postgresql://operation_assistant:operation_assistant@127.0.0.1:15432/operation_assistant
OA_REDIS_URL=redis://127.0.0.1:16379/0
```

Fallback backend command:

```bash
OA_DATABASE_URL=postgresql://operation_assistant:operation_assistant@127.0.0.1:15432/operation_assistant \
OA_REDIS_URL=redis://127.0.0.1:16379/0 \
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Fallback frontend command:

```bash
npm --prefix frontend run dev
```

## Testing Expectations

- Each milestone should add tests for the behavior it introduces.
- Baseline and improved modes should remain runnable when they are used to compare retrieval, investigation, safety, cache, or evaluation behavior.
- CI should begin with small smoke checks and expand as the implementation becomes real.

Current checks:

```bash
.venv/bin/python -m pytest tests/backend -q
npm --prefix frontend test
npm --prefix frontend run build
```

`make test` runs the same current checks.

Retrieval eval commands:

```bash
.venv/bin/python scripts/eval_retrieval.py --strategy lexical --limit 30
.venv/bin/python scripts/eval_retrieval.py --strategy hybrid_rerank_rewrite --limit 30
```

The eval runner writes local JSON and Markdown artifacts under `evals/results/retrieval/`. Those output artifacts are intentionally ignored because they are generated from the tracked eval cases.

## Retrieval Development Notes

- The default user-facing strategy is `hybrid_rerank_rewrite`.
- The `lexical` strategy must remain runnable as a baseline for tests and evals.
- The current embedding provider is deterministic and local so tests, demos, and evals do not require an external API key.
- Retrieval should return source citations with `source_id`, `source_title`, `source_path`, and `chunk_id`.
- Retrieval is not allowed to execute diagnostic tools, apply remediation, or approve risky actions.

## PR And Milestone Workflow

- PRs should map to coherent milestone steps.
- Public PR descriptions should focus on engineering behavior, validation, and remaining limitations.
- Private milestone notes and reports should stay outside public files and public navigation.

## Public And Private Documentation Boundary

- Public files are written in English and should avoid private positioning, private planning rationale, and non-public reference material.
- Internal planning files are intentionally kept outside the public documentation surface.
- If a detail only exists to guide private planning, keep it out of public docs, code comments, package metadata, PR descriptions, and public issue text.
