# OperationAssistant

OperationAssistant is an AI operations assistant foundation for incident investigation. It is designed to grow into a system that combines retrieval, diagnostic tool use, evidence checks, and traceable investigation steps so an operator can understand why a curated service or workflow incident happened and what a safe next action would be.

## Current Capabilities

- FastAPI backend with health and curated incident seed endpoints.
- Retrieval preview endpoint at `/api/retrieval` for runbook chunks and source citations.
- Two runnable retrieval strategies:
  - `lexical` for a simple benchmark baseline.
  - `hybrid_rerank_rewrite` as the default improved path with deterministic embeddings, query rewriting, metadata filtering, and lightweight reranking.
- React and TypeScript frontend that shows seed incidents, investigation results, and a retrieval preview citation panel.
- Synchronous investigation endpoint at `/api/investigations` with `rag_only` baseline mode and default `agent_tools` mode.
- Read-only function-calling tools for incident summaries, service metrics, failed events, and trace-like sample records, with JSON Schema compatible function contracts.
- Product verifier checks that final answers reference retrieved citations and tool outputs.
- Frontend investigation view with a final answer, tool call timeline, trace viewer, verifier badge, and citation cards.
- Safety guardrails for prompt injection detection, PII redaction, unsafe replay/action classification, and default `safety_mode=enforce`.
- Human approval requests and audit endpoints for action-like simulated remediation plans.
- Frontend guardrail state and approval modal for approval-required investigation results.
- Safety eval runner with `monitor_only` baseline and `enforce` improved mode.
- Unified full eval runner with a 100+ labeled quality dataset, baseline/improved arms, independent deterministic eval judge, and generated JSON/Markdown reports.
- Prompt, model, tool, guardrail, and cache-input version metadata attached to full eval reports.
- Latest eval summary API and frontend quality summary panel for the most recent local full eval run.
- Lightweight append-only feedback log helpers for citation, tool-choice, safety, and missing-fact labels.
- Docker Compose services for PostgreSQL with pgvector and Redis.
- PostgreSQL migrations for foundation tables plus document and chunk tables with pgvector embeddings.
- Local runbook corpus under `data/runbooks/` and labeled retrieval eval cases under `evals/retrieval/`.
- Labeled tool-use eval cases under `evals/tool_use/` and labeled safety cases under `evals/safety/`.
- Backend, frontend, and fast eval smoke checks wired into GitHub Actions.

## Planned Later Capabilities

- Add durable semantic caching, async job handling, and richer trend dashboards.

## Planned Tech Stack

- Backend: Python and FastAPI.
- Frontend: React with TypeScript.
- Data: PostgreSQL with pgvector, plus Redis for cache and background jobs.
- Local infrastructure: Docker Compose for supporting services.
- Quality and delivery: automated tests and GitHub Actions.

## Current Status

The current implementation is a runnable local foundation with benchmarkable runbook retrieval, source citations, read-only diagnostic tool calls, product verification, traceable investigation steps, safety guardrails, and human approval gates for simulated action-like requests. It does not include live LLM calls, real write actions, semantic caching, async jobs, or evaluation dashboards yet.

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

Run investigation evals:

```bash
.venv/bin/python scripts/eval_investigation.py --mode rag_only
.venv/bin/python scripts/eval_investigation.py --mode agent_tools
```

Run safety evals:

```bash
.venv/bin/python scripts/eval_safety.py --safety-mode monitor_only
.venv/bin/python scripts/eval_safety.py --safety-mode enforce
```

Run the unified quality gate:

```bash
.venv/bin/python scripts/eval_all.py --arm baseline
.venv/bin/python scripts/eval_all.py --arm improved
```

Run the fast CI-style eval smoke locally:

```bash
make eval-smoke
```
