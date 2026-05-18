# OperationAssistant

OperationAssistant is an AI operations assistant foundation for incident investigation. It is designed to grow into a system that combines retrieval, diagnostic tool use, evidence checks, and traceable investigation steps so an operator can understand why a curated service or workflow incident happened and what a safe next action would be.

## Current Capabilities

- FastAPI backend with health and curated incident seed endpoints.
- Retrieval preview endpoint at `/api/retrieval` for runbook chunks and source citations.
- Two runnable retrieval strategies:
  - `lexical` for a simple benchmark baseline.
  - `hybrid_rerank_rewrite` as the default improved path with deterministic embeddings, query rewriting, metadata filtering, and lightweight reranking.
- React and TypeScript frontend that shows seed incidents, a static investigation placeholder, and a retrieval preview citation panel.
- Docker Compose services for PostgreSQL with pgvector and Redis.
- PostgreSQL migrations for foundation tables plus document and chunk tables with pgvector embeddings.
- Local runbook corpus under `data/runbooks/` and labeled retrieval eval cases under `evals/retrieval/`.
- Backend and frontend tests wired into GitHub Actions.

## Planned Later Capabilities

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

The current implementation is a runnable local foundation with benchmarkable runbook retrieval and source citations. It does not include live LLM calls, diagnostic tool execution, approval gates, final answer verification, or evaluation dashboards yet.

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

Run retrieval evals:

```bash
.venv/bin/python scripts/eval_retrieval.py --strategy lexical --limit 30
.venv/bin/python scripts/eval_retrieval.py --strategy hybrid_rerank_rewrite --limit 30
```
