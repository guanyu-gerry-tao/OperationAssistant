# OperationAssistant

OperationAssistant is an AI operations assistant foundation for incident investigation. It is designed to grow into a system that combines retrieval, diagnostic tool use, evidence checks, and traceable investigation steps so an operator can understand why a curated service or workflow incident happened and what a safe next action would be.

## Current Foundation

- FastAPI backend with health and curated incident seed endpoints.
- React and TypeScript frontend that shows seed incidents and a static investigation placeholder.
- Docker Compose services for PostgreSQL with pgvector and Redis.
- PostgreSQL foundation migration for incidents, runbook metadata, and tool sample records.
- Backend and frontend smoke tests wired into GitHub Actions.

## Planned Later Capabilities

- Retrieve runbooks and system notes with source citations.
- Query curated incident, workflow, metric, and trace-like sample data through read-only tools.
- Produce grounded investigation summaries and remediation plans.
- Track investigation steps, retrieval results, tool calls, verification decisions, and latency/cost metadata.
- Add safety checks, approval gates for risky actions, and evaluation reports as the implementation matures.

## Planned Tech Stack

- Backend: Python and FastAPI.
- Frontend: React with TypeScript.
- Data: PostgreSQL with pgvector, plus Redis for cache and background jobs.
- Local infrastructure: Docker Compose for supporting services.
- Quality and delivery: automated tests and GitHub Actions.

## Current Status

The first implementation milestone is a runnable local foundation. It does not include live LLM calls, retrieval ranking, diagnostic tool execution, approval gates, or evaluation dashboards yet.

## Local Development

Install dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
npm --prefix frontend install
```

Start local data services:

```bash
docker compose up -d postgres redis
```

Start the backend and frontend development servers:

```bash
make dev
```

Fallback commands:

```bash
OA_DATABASE_URL=postgresql://operation_assistant:operation_assistant@127.0.0.1:15432/operation_assistant \
OA_REDIS_URL=redis://127.0.0.1:16379/0 \
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

npm --prefix frontend run dev
```

Run checks:

```bash
make test
```
