PYTHON := .venv/bin/python
BACKEND_PORT := 8000
FRONTEND_PORT := 5173
DATABASE_URL := postgresql://operation_assistant:operation_assistant@127.0.0.1:15432/operation_assistant
REDIS_URL := redis://127.0.0.1:16379/0

.PHONY: install dev test test-backend test-frontend build-frontend eval-smoke eval-llm-dry-run

install:
	$(PYTHON) -m pip install -e '.[dev]'
	npm --prefix frontend install

dev:
	@echo "Starting backend on http://127.0.0.1:$(BACKEND_PORT)"
	@echo "Starting frontend on http://127.0.0.1:$(FRONTEND_PORT)"
	@OA_DATABASE_URL=$(DATABASE_URL) OA_REDIS_URL=$(REDIS_URL) $(PYTHON) -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port $(BACKEND_PORT) & \
	BACKEND_PID=$$!; \
	trap 'kill $$BACKEND_PID' EXIT INT TERM; \
	npm --prefix frontend run dev

test: test-backend test-frontend build-frontend

test-backend:
	$(PYTHON) -m pytest tests/backend -q

test-frontend:
	npm --prefix frontend test

build-frontend:
	npm --prefix frontend run build

eval-smoke:
	$(PYTHON) scripts/eval_all.py --arm baseline --limit 12 --output-dir evals/tmp/ci-baseline --check-thresholds
	$(PYTHON) scripts/eval_all.py --arm improved --limit 12 --output-dir evals/tmp/ci-improved --check-thresholds

eval-llm-dry-run:
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm llm_only --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm rag_only --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm rag_tools --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm rag_tools_verifier --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm safety_monitor_only --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm safety_enforce --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm cache_off --limit 30 --output-dir evals/tmp/m5_5_dry_run
	$(PYTHON) scripts/eval_llm.py --provider deterministic --arm cache_on --limit 30 --output-dir evals/tmp/m5_5_dry_run
