# Changelog

All notable changes to this project will be documented in this file. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [0.1.0]. 2026-05-06

Initial public release.

### Added

- **Agent core**: classify → retrieve → draft → escalate orchestrator with per-stage Claude Sonnet 4.6 calls and tool-forced JSON via Anthropic tool-use.
- **Single LLM wrapper** (`inbox_agent.llm.client.LLMClient`) owning retries, exponential backoff on transient errors, schema-repair on Pydantic validation failure, exact cost from `response.usage`, Langfuse tracing, structured logging.
- **HTTP API** (FastAPI): `POST /classify`, `POST /draft`, `POST /escalate-decision`, `POST /run`, `POST /ingest-faq`, `GET /traces`, `GET /health`.
- **FAQ pipeline**: `httpx` fetch → `trafilatura` extract → paragraph-aware chunker → Voyage `voyage-3` embeddings → `pgvector` cosine retrieval with similarity floor.
- **Versioned prompts** (`apps/api/prompts/*.v<semver>.md`) with frontmatter validation and tightening on validation-error retry.
- **Trace persistence**: dual-write to local Postgres `traces` table (dashboard source of truth) and Langfuse (deep timeline). Each row deep-links to Langfuse.
- **Next.js 15 web app** with try-it page (5 sample tickets) and live dashboard (counts, p95 latency, avg cost, escalation rate, recent traces).
- **Eval harness**: 50-item golden set (`evals/golden_set.jsonl`), Haiku 4.5 LLM-as-judge with calibrated rubric, scorecard with classification accuracy, escalation accuracy, judge mean score, hallucination rate, p50/p95 latency, cost.
- **CI** (`.github/workflows/ci.yml`): ruff format + check, mypy strict, pytest with 75% coverage gate, docker build, Next.js lint + typecheck + build.
- **Eval workflow** (`.github/workflows/evals.yml`): smoke (10 items) on default PRs, full (50 items) on PRs labeled `eval` or merges to main, sticky PR comment with diff vs, main, fails on any metric regression > 5%.
- **Tests**: respx-mocked Anthropic responses, ≥3 integration tests, 1 docker-compose e2e test, architectural test enforcing the single-LLM-wrapper invariant.
- **Modal deployment** (`apps/api/modal_app.py`) with `make deploy-modal` + `make smoke-modal`.
- **Docs**: README with Mermaid architecture diagram, ARCHITECTURE.md with 15 design decisions, DEMO_SCRIPT.md (90-second Loom script), this CHANGELOG.

### Notes

- Pricing tables in `inbox_agent.llm.cost` reflect Anthropic public pricing as of May 2026.
- `tiktoken` is included only for pre-call token estimation; actual billing uses `response.usage` exactly.
- Langfuse is optional; the tracer is a no-op when keys are absent so the demo runs without it.
