# OperationAssistant

OperationAssistant is an AI operations assistant for investigating service incidents with retrieval, read-only diagnostic tools, evidence checks, safety controls, and evaluation reports.

The project is designed around a practical operations workflow: an engineer asks why an incident happened, the assistant retrieves relevant runbooks, calls diagnostic tools, checks whether the answer is grounded, and presents traceable evidence before suggesting a safe next step.

## What It Demonstrates

- Python/FastAPI backend for incident investigation, retrieval, tool execution, verification, safety checks, approval requests, and eval reporting.
- React/TypeScript frontend for seed incidents, investigation answers, citations, tool timelines, verifier status, approval flows, and quality summaries.
- PostgreSQL with pgvector for document chunks and retrieval storage.
- Redis-backed local infrastructure for cache and job-ready service wiring.
- RAG workflows with lexical and hybrid retrieval modes, query rewriting, metadata filtering, deterministic embeddings, and reranking.
- Function-calling style read-only tools with JSON Schema compatible contracts.
- Guardrails for prompt injection detection, PII redaction, unsafe replay/action classification, permissions, and human approval gates.
- Evaluation runners for retrieval, tool use, safety, full quality gates, and optional OpenAI-compatible LLM mechanism evaluations.

## Architecture

```text
React Investigation UI
        |
        v
FastAPI Backend
        |
        +--> Retrieval: runbook chunks + pgvector-backed storage
        +--> Tool Executor: read-only incident, metric, failed-event, and trace tools
        +--> Verifier: citation and tool-evidence checks
        +--> Guardrails: prompt injection, PII, unsafe action classification
        +--> Approval Flow: action-like plans require human approval
        |
        v
Eval Runners: retrieval, investigation, safety, full quality, LLM mechanism
```

The default local workflow is safe by design: read-only tools can run automatically, action-like requests are converted into approval-required plans, and evals can run through deterministic providers or real OpenAI-compatible providers when configured through local environment variables.

## Implemented Capabilities

### Retrieval and Grounding

- Runbook corpus under `data/runbooks/`.
- Retrieval preview API for source citations.
- `lexical` baseline retrieval mode.
- `hybrid_rerank_rewrite` retrieval mode with deterministic embeddings, query rewriting, metadata filtering, and reranking.
- Product verifier that checks final answers against retrieved citations and tool outputs.

### Investigation Workflow

- Synchronous investigation endpoint at `/api/investigations`.
- `rag_only` baseline mode and default `agent_tools` mode.
- Read-only diagnostic tools for incident summaries, service metrics, failed events, and trace-like sample records.
- JSON Schema compatible tool contracts.
- Frontend answer view with citations, tool call timeline, trace viewer, verifier badge, and final answer.

### Safety and Approval

- Prompt injection detection.
- PII redaction.
- Unsafe replay/action classification.
- Permission checks for read-only, planning, and action-like requests.
- Human approval requests for simulated remediation plans.
- Audit endpoints and replayable traces for investigation review.

### Evaluation

- Retrieval eval cases under `evals/retrieval/`.
- Tool-use eval cases under `evals/tool_use/`.
- Safety eval cases under `evals/safety/`.
- Unified full-quality eval runner with baseline and improved arms.
- Independent deterministic eval judge for quality scoring.
- Optional LLM-backed mechanism eval with deterministic and OpenAI-compatible provider modes.
- Eval reports include prompt, model, tool, guardrail, cache-input, latency, cost, and metadata snapshots where available.

## Validation

The project includes backend tests, frontend checks, eval smoke tests, and provider-gated evaluation paths:

- Pytest coverage for backend endpoints, retrieval, tools, verification, safety, and eval helpers.
- Frontend build and UI checks for the investigation flow.
- GitHub Actions for backend, frontend, and fast eval smoke checks.
- Local eval runners for retrieval, investigation, safety, full quality, and LLM mechanism comparisons.

The LLM mechanism eval can compare arms such as `llm_only`, `rag_only`, `rag_tools`, `rag_tools_verifier`, `safety_monitor_only`, `safety_enforce`, `cache_off`, and `cache_on`. Real provider calls are only used when keys are supplied through local environment variables; deterministic mode remains available for dry runs and CI-friendly checks.

## Tech Stack

- Backend: Python and FastAPI.
- Frontend: React and TypeScript.
- Data: PostgreSQL with pgvector, plus Redis for local cache/job infrastructure.
- AI workflow: RAG, hybrid retrieval, reranking, function calling, verifier checks, guardrails, approval gates.
- Evaluation: deterministic eval judge, OpenAI-compatible provider adapter, JSON/Markdown reports.
- Infrastructure: Docker Compose.
- Testing and delivery: pytest, frontend checks, GitHub Actions.

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

Start backend and frontend development servers:

```bash
make dev
```

Fallback backend/frontend commands:

```bash
OA_DATABASE_URL=postgresql://operation_assistant:operation_assistant@127.0.0.1:15432/operation_assistant \
OA_REDIS_URL=redis://127.0.0.1:16379/0 \
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

npm --prefix frontend run dev
```

Run the standard checks:

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
.venv/bin/python scripts/eval_all.py --arm improved --limit 12 --check-thresholds
```

Run the LLM mechanism eval in deterministic mode:

```bash
.venv/bin/python scripts/eval_llm.py --provider deterministic --arm rag_tools --limit 20
```

Run the LLM mechanism eval with an OpenAI-compatible provider:

```bash
OPENAI_API_KEY=<your-key> OPENAI_MODEL=<model-name> \
.venv/bin/python scripts/eval_llm.py --provider openai --arm rag_tools --limit 20 --max-cost-usd 1.00
```

Run fast CI-style eval smoke locally:

```bash
make eval-smoke
```

## API Surface

Core endpoints include:

```text
GET  /health
GET  /api/incidents
GET  /api/incidents/{incident_id}
GET  /api/retrieval
POST /api/investigations
GET  /api/investigations/{trace_id}
GET  /api/investigations/{trace_id}/trace
GET  /api/evals/latest
GET  /api/approvals/{approval_id}
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
```

## Documentation

- `data/runbooks/` contains local runbook source material.
- `evals/` contains labeled retrieval, tool-use, safety, and full-quality datasets.
- `scripts/` contains retrieval, investigation, safety, full-quality, and LLM mechanism eval runners.
- `backend/app/` contains retrieval, tool execution, verification, guardrails, approval, provider, and workflow modules.
