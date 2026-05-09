# 90-second Loom demo script

Open the deployed demo URL in a tab. Have the GitHub repo in another. Have terminal with `cd inbox-agent` ready in a third tab if needed.

---

## 0:00. 0:10 · Hook (10s)

> "Most AI customer support demos are a ChatGPT wrapper around a system prompt. This is what production looks like, same use case, real engineering. Let me show you."

(Screen: home page, browser maximized.)

## 0:10. 0:35 · Live run (25s)

> "I paste a customer ticket, let's pick the trickiest one, a GDPR threat."

Click the **Edge, legal threat** sample chip. Click **Run agent**.

> "Three things happen in two seconds. The agent classifies it as `account` with 85% confidence. It drafts a calm, on-policy reply that doesn't promise anything legally binding. And it correctly decides to escalate to trust & safety, with reasoning."

Point at the three result cards as they fill in.

> "And down here, total tokens, dollar cost, latency, the trace ID. Three calls, half a cent."

## 0:35. 1:00 · Why this matters (25s)

Click on the **Dashboard** tab.

> "Every run lands here in the dashboard. Real cost per ticket, p95 latency, escalation rate, the prompts and outputs."

Hover over a row's external-link icon.

> "Each row deep-links into Langfuse, one click and you see the full per-call breakdown. Local DB is the source of truth, Langfuse is the deep timeline."

## 1:00. 1:25 · The engineering (25s)

Switch to the GitHub repo, scroll to the README badges row.

> "CI runs ruff format, mypy strict, full test suite, docker build, every PR. There's an evals workflow too, fifty hand-crafted golden tickets, judged by Haiku 4.5, scored, diffed against `main`. Any metric that regresses more than 5% fails the PR."

Scroll to the architecture Mermaid diagram.

> "Tool-forced JSON outputs, single LLM client wrapper, pgvector for FAQ retrieval, structured logging, dual-write tracing. ARCHITECTURE.md walks through every choice and why."

## 1:25. 1:30 · Close (5s)

> "Live demo URL is in the README. Repo is public. Happy to walk you through any part of it."

---

## Setup checklist before recording

- [ ] Hard-refresh the demo so a fresh `traces` table doesn't have my testing.
- [ ] Pre-run two sample tickets so the dashboard isn't empty when I click over.
- [ ] Audio level check; close Slack/notifications.
- [ ] If demo is slow, record at the home page with one warm cache call already done.
- [ ] Replace the README placeholder demo URL with the actual deployed one before pushing.
