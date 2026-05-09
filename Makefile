.PHONY: help bootstrap demo install-api install-web dev-api dev-web db-up db-down \
        migrate test test-unit test-integration test-e2e lint format typecheck \
        evals evals-smoke build deploy-modal smoke-modal clean ci

SHELL := /bin/bash
API_DIR := apps/api
WEB_DIR := apps/web

# Pretty help.
help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Bootstrap ────────────────────────────────────────────────
bootstrap: install-api install-web ## Install all dependencies (API + web).
	@echo "✓ Bootstrap complete. Copy .env.example -> .env and fill keys."

install-api: ## Install Python deps via uv.
	cd $(API_DIR) && uv pip install -e ".[dev]"

install-web: ## Install JS deps via pnpm.
	cd $(WEB_DIR) && pnpm install --frozen-lockfile

# ─── One-shot demo ────────────────────────────────────────────
# `bootstrap` first so `alembic` is on PATH on a truly fresh clone.
demo: bootstrap ## Boot Postgres, run migrations, start API + web (one command).
	@cp -n .env.example .env || true
	docker compose up -d postgres
	cd $(API_DIR) && alembic upgrade head
	@echo ""
	@echo "Postgres:  postgresql://inbox:inbox@localhost:5432/inbox_agent"
	@echo "API:       http://localhost:8000  (run 'make dev-api')"
	@echo "Web:       http://localhost:3000  (run 'make dev-web')"

dev-api: ## Run API with reload.
	cd $(API_DIR) && uvicorn inbox_agent.main:app --reload --host 0.0.0.0 --port 8000

dev-web: ## Run Next.js dev server.
	cd $(WEB_DIR) && pnpm dev

# ─── Database ─────────────────────────────────────────────────
db-up: ## Start Postgres only.
	docker compose up -d postgres

db-down: ## Stop and remove all containers (keeps volume).
	docker compose down

migrate: ## Apply migrations.
	cd $(API_DIR) && alembic upgrade head

# ─── Quality gates ────────────────────────────────────────────
lint: ## ruff check + format check.
	cd $(API_DIR) && .venv/bin/ruff format --check . && .venv/bin/ruff check .

format: ## Apply ruff format.
	cd $(API_DIR) && ruff format . && ruff check --fix .

typecheck: ## mypy strict.
	cd $(API_DIR) && .venv/bin/mypy --strict src

test: ## Unit + integration (no docker), with coverage gate.
	cd $(API_DIR) && .venv/bin/pytest tests/unit tests/integration -v

test-unit: ## Unit tests only (no coverage gate).
	cd $(API_DIR) && .venv/bin/pytest tests/unit -v --no-cov

test-integration: ## Integration tests with respx-mocked LLM calls (no coverage gate).
	cd $(API_DIR) && .venv/bin/pytest tests/integration -v -m integration --no-cov

test-e2e: ## Boots compose stack and runs e2e tests.
	cd $(API_DIR) && pytest tests/e2e -v -m e2e

# ─── Evals ────────────────────────────────────────────────────
# Run from repo root so `evals/` (top-level package) is importable.
evals: ## Full 50-item eval suite. Requires ANTHROPIC_API_KEY.
	python -m evals.run_evals --golden evals/golden_set.jsonl \
	  --out evals/results/scorecard.json --full

evals-smoke: ## 10-item smoke set (CI default).
	python -m evals.run_evals --golden evals/golden_set.jsonl \
	  --out evals/results/scorecard.json --smoke

# ─── Deployment ───────────────────────────────────────────────
build: ## Build API Docker image.
	cd $(API_DIR) && docker build -t inbox-agent:latest .

deploy-modal: ## Run migrations then deploy API to Modal.
	cd $(API_DIR) && modal run modal_app.py::migrate
	cd $(API_DIR) && modal deploy modal_app.py

smoke-modal: ## Smoke-test deployed Modal endpoint. Requires MODAL_URL env.
	@test -n "$$MODAL_URL" || (echo "MODAL_URL not set" && exit 1)
	curl -fsS "$$MODAL_URL/health" | jq .

clean: ## Remove caches and build artefacts.
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(API_DIR)/dist $(API_DIR)/build $(API_DIR)/*.egg-info
	rm -rf $(WEB_DIR)/.next $(WEB_DIR)/.turbo

ci: lint typecheck test ## Full CI: lint + typecheck + tests.
