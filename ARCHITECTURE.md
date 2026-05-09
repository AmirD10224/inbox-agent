# Architecture

This document explains the non-obvious design choices. The README explains *what* the system does; this explains *why* it's built this way.

## 1. Single LLM client wrapper

Every Anthropic call in the system goes through [apps/api/src/inbox_agent/llm/client.py](apps/api/src/inbox_agent/llm/client.py)`::LLMClient.call_with_tool`. This is enforced by [tests/unit/test_llm_client_single_entrypoint.py](apps/api/tests/unit/test_llm_client_single_entrypoint.py), which greps the source tree for `import anthropic` outside the wrapper and fails CI if it finds any.

**Why it matters:** in five months, when someone adds a new agent stage and wants to "just call Anthropic directly here," they can't. The wrapper owns retries, cost accounting, tracing, structured-output enforcement, and timeout policy. Bypass it, you bypass all five.

## 2. Forced JSON via tool-use, not prompted JSON

The agent never asks the model to "return JSON." It defines an Anthropic tool whose `input_schema` is the desired output shape and uses `tool_choice={"type": "tool", "name": ...}` to force the model to emit a `tool_use` block. The block's `input` field is the structured output, no parsing of free text, no `json.loads(stripped_markdown)` games.

The schema lives in [apps/api/src/inbox_agent/llm/tool_schemas.py](apps/api/src/inbox_agent/llm/tool_schemas.py) twice: once as the JSON Schema the model sees, once as a Pydantic model that validates what comes back. They're kept in sync by tests that assert their enums match. On a Pydantic validation failure (rare, usually a stringified number), we retry once with the validation errors appended to the user message before giving up.

## 3. Cost = `response.usage`, not tiktoken

tiktoken is OpenAI's tokenizer. Using it for Claude estimation is wrong by ~10–15%. The actual billing path uses the `usage.input_tokens` and `usage.output_tokens` returned by the API call itself, that's what Anthropic charges, exactly, tiktoken/`count_tokens_estimate` is reserved for *pre-call* gating ("this prompt will cost X if I send it") which doesn't need to be exact. Pricing tables live in [apps/api/src/inbox_agent/llm/cost.py](apps/api/src/inbox_agent/llm/cost.py).

## 4. Versioned prompts as files, not f-strings

Prompts live in [apps/api/prompts/](apps/api/prompts/) as markdown with frontmatter (`name`, `version`, `model`). The filename encodes a semver: `classify.v1.0.0.md`. The loader parses on startup, validates that both `# System` and `# User` sections exist, and caches.

**Why it matters:** when a prompt change degrades evals, you can `git blame` it. When a model upgrade requires a prompt rewrite, you bump the filename to `v2.0.0.md` and hold both, the loader picks the highest semver unless overridden. Prompt versions are carried as Langfuse trace metadata so you can correlate a regression in prod with a prompt edit.

## 5. Trace persistence: dual-write, dashboard reads local

Every `/run` writes one row to the local `traces` table and one generation span to Langfuse. The Next.js dashboard reads the local table, sub-100ms, works without network access to Langfuse, survives Langfuse outages without breaking the demo.

Each row carries the Langfuse trace ID. Click "↗" on a trace and you jump into Langfuse's deep timeline view (per-call diff, prompt cache stats, etc.). Local table covers the 80% case (counts, costs, latencies, classifications); Langfuse covers the 20% (deep debugging).

## 6. FAQ retrieval lives in Postgres

pgvector on Postgres 16 (`pgvector/pgvector:pg16` image) is the FAQ store. One service, one connection pool, one place to back up. The `faq_chunks` table has an `ivfflat` index with `lists=100`, which is right-sized for the demo (≤10k chunks); past that, the comment in the migration tells you to bump it.

Cosine similarity is the distance metric. The retriever computes `1 - cosine_distance / 2` to get a similarity score in `[0, 1]` and drops anything below `0.55`. That floor was chosen empirically against the golden set, high enough to keep noise out of the prompt, low enough to keep recall on paraphrased questions.

## 7. Three-stage agent, not one mega-prompt

A common trap is to dump the whole problem ("classify, draft, decide whether to escalate") into one prompt and hope. We don't. Each stage is a separate call with a tight, single-purpose schema:

- The classifier doesn't see the FAQ. It just needs a category.
- The drafter sees the classification, the FAQ chunks, and is told to cite or defer.
- The escalator sees the draft and is asked to second-guess it.

This **costs more** (3 calls, ~$0.008/ticket vs $0.003 for a mega-prompt) but **buys** independent calibration on each decision, isolated retries on each schema, and meaningful traces, you can see which stage failed, not just that "the agent did something wrong."

## 8. Eval LLM-as-judge: cheaper model, calibrated separately

The judge runs on Haiku 4.5, not Sonnet. Two reasons:

1. The judge does a simpler task (compare X to Y, pick a label). Haiku is sufficient.
2. Running the judge on the same model that produced the answer would be circular. Different model = independent grader.

Calibration is via the rubric in [apps/api/prompts/judge.v1.0.0.md](apps/api/prompts/judge.v1.0.0.md): "incorrect" if any unsupported fact is invented, even if the rest is fine. That bias is intentional, hallucinations in customer-facing copy are unacceptable.

## 9. Eval regression gate at the workflow boundary

Eval scoring happens in [.github/workflows/evals.yml](.github/workflows/evals.yml), not in CI. The workflow:

1. Picks **smoke** (10 items) or **full** (50 items) based on PR labels.
2. Pulls `evals/results/scorecard.json` from `main` as the baseline.
3. Runs current branch's evals.
4. Computes the diff. Posts a sticky PR comment.
5. Fails the workflow if any metric regressed > 5%.

Keeping evals out of the regular CI lane means standard PRs run fast and free; eval-changing PRs (label `eval`) get the full run.

## 10. Tests: respx, not VCR

`respx` mocks the Anthropic HTTP endpoint with hand-crafted JSON fixtures in [tests/fixtures/responses/](apps/api/tests/fixtures/responses/). Why hand-crafted vs, recorded:

- Recorded fixtures bind tests to a specific real prompt + model behavior. When the model changes (Sonnet 4.6 → 4.7), the recordings need re-running and the diffs are noisy.
- Hand-crafted fixtures encode **exactly the contract we want to test**: "given this tool-use payload, the agent surface should respond *this* way." Model behavior changes don't break the contract test.

For the `/run` orchestrator integration test, three sequential responses are queued, classify → draft → escalate, and the test asserts both the per-stage outputs and the persisted aggregate row.

## 11, e2e in compose, deploy on Modal

The e2e test (`tests/e2e/test_full_stack.py`) runs `docker compose up`, waits for `/health`, and exercises live endpoints. CI does not run e2e by default (skipped via `pytest -m e2e`); it's a `make test-e2e` target. Modal deployment is verified separately by `make smoke-modal`. Reason: docker-compose and Modal are different runtime targets, pretending one tests the other would be misleading.

## 12. Structured logging from day 1

[structlog](https://www.structlog.org/) with `JSONRenderer` in non-development environments. Every LLM call emits one structured log line with `operation`, `model`, `trace_id`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `repair_attempts`. Modal/Cloud Run/CloudWatch parse JSON natively; you can `jq '.cost_usd'` on prod logs to bill a customer for their inference, or filter on `repair_attempts > 0` to find prompts that need tightening.

In dev, structlog renders pretty colored output instead, same call sites, different sink.

## 13. Pydantic v2 for both wire schemas and tool schemas, kept separate

`apps/api/src/inbox_agent/api/schemas.py` defines the public HTTP contract.
`apps/api/src/inbox_agent/llm/tool_schemas.py` defines the LLM JSON contract.

They overlap (both have `category`, `confidence`, etc.) but are deliberately separate models. Reason: the public API can evolve (add a field for A/B test tracking) without forcing a re-train of the prompts; the prompts can change without breaking API consumers. The orchestrator translates between them.

## 14. Async everywhere, single connection pool

FastAPI + SQLAlchemy 2.0 async + `psycopg3`. One async engine per process (cached via `lru_cache`), `pool_size=5, max_overflow=5`, sized for Modal's per-container concurrency limits.

The Anthropic SDK is async-native; the Voyage SDK is sync, so [apps/api/src/inbox_agent/faq/embed.py](apps/api/src/inbox_agent/faq/embed.py) wraps it in `asyncio.to_thread` to avoid blocking the loop during ingestion.

## 15. Why no LangChain

LangChain optimizes for breadth (any model, any vector store, any chain pattern). This project optimizes for depth on one stack (Anthropic + Voyage + pgvector). Adding LangChain would (a) duplicate the wrapper invariant, there'd be two ways to call Anthropic, and (b) make the type system fight the test harness (LangChain's runtime type checks vs, mypy strict). The cost was: write ~150 lines of `LLMClient` instead of importing it. The win: every call site is mypy-checked end-to-end, and the dependency surface is small enough to audit in an afternoon.
