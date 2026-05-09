"""Run the eval suite and write a scorecard to disk.

Usage:
    python -m evals.run_evals --golden evals/golden_set.jsonl --out evals/results/scorecard.json [--smoke|--full]

Smoke mode runs a deterministic auto-stratified sample (2 per expected_class,
seeded), so adding a new category to the golden set automatically extends
smoke coverage without editing this file. Full mode runs all 50.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from inbox_agent.agent.classifier import Classifier
from inbox_agent.agent.drafter import Drafter
from inbox_agent.agent.escalator import Escalator
from inbox_agent.agent.prompts import get_prompt_loader
from inbox_agent.config import get_settings
from inbox_agent.llm.client import LLMClient
from evals.judge import Judge
from evals.scorecard import build_scorecard, diff, format_markdown, regressions
from evals.types import GoldenItem, RunRecord, Scorecard


SMOKE_PER_CLASS = 2  # → 2 × n_classes ≈ 10 items on the current taxonomy.


def load_golden(path: Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(GoldenItem.model_validate_json(line))
    return items


def stratified_smoke(items: list[GoldenItem], per_class: int = SMOKE_PER_CLASS) -> list[GoldenItem]:
    """Pick the first `per_class` items from each `expected_class`, in file order.

    Deterministic so smoke runs across PRs are comparable; auto-stratified so
    new categories are covered without editing this file.
    """
    by_class: dict[str, list[GoldenItem]] = defaultdict(list)
    for item in items:
        by_class[item.expected_class].append(item)
    chosen: list[GoldenItem] = []
    for cls in sorted(by_class):
        chosen.extend(by_class[cls][:per_class])
    return chosen


async def run_one(
    *,
    item: GoldenItem,
    classifier: Classifier,
    drafter: Drafter,
    escalator: Escalator,
    judge: Judge,
) -> RunRecord:
    start = time.perf_counter()
    cls = await classifier.classify(item.ticket)

    # No FAQ context in evals, keeps results deterministic across runs.
    draft = await drafter.draft(
        ticket=item.ticket,
        classification=cls.output.category,
        confidence=cls.output.confidence,
        faq_context=[],
    )
    esc = await escalator.decide(
        ticket=item.ticket,
        classification=cls.output.category,
        confidence=cls.output.confidence,
        drafted_response=draft.output.response,
    )

    # The judge grades the *draft only*. We deliberately do NOT pass the
    # expected category/escalate/team, those have their own dedicated metrics
    # (`classification_accuracy`, `escalation_accuracy`, `team_accuracy`) and
    # leaking them to the judge biases `judge_mean_score` / `hallucination_rate`.
    expected_keywords = " / ".join(item.expected_answer_contains) or "(no specific keywords)"
    judgment = await judge.judge(
        ticket=item.ticket,
        expected=f"Reply should address the ticket and mention: {expected_keywords}",
        faq_context="",
        drafted=draft.output.response,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)
    cost = cls.cost_usd + draft.cost_usd + esc.cost_usd

    return RunRecord(
        id=item.id,
        ticket=item.ticket,
        expected_class=item.expected_class,
        actual_class=cls.output.category,
        expected_escalate=item.expected_action.escalate,
        actual_escalate=esc.output.escalate,
        expected_team=item.expected_action.suggested_team,
        actual_team=esc.output.suggested_team,
        confidence=cls.output.confidence,
        drafted_response=draft.output.response,
        judge_score=judgment.score,
        judge_label=judgment.label,
        judge_reasoning=judgment.reasoning,
        cost_usd=cost,
        latency_ms=latency_ms,
    )


async def run_async(items: list[GoldenItem], concurrency: int) -> list[RunRecord]:
    llm = LLMClient()
    classifier = Classifier(llm=llm, prompts=get_prompt_loader())
    drafter = Drafter(llm=llm, prompts=get_prompt_loader())
    escalator = Escalator(llm=llm, prompts=get_prompt_loader())
    judge = Judge(llm=llm)

    sem = asyncio.Semaphore(concurrency)

    async def _bound(item: GoldenItem) -> RunRecord:
        async with sem:
            return await run_one(
                item=item,
                classifier=classifier,
                drafter=drafter,
                escalator=escalator,
                judge=judge,
            )

    return await asyncio.gather(*(_bound(it) for it in items))


def _git_sha() -> str | None:
    try:
        r = subprocess.run(  # noqa: S603, S607
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--baseline", type=Path, help="Previous scorecard.json for diff/gate.")
    parser.add_argument("--smoke", action="store_true", help="Run 10-item smoke set.")
    parser.add_argument("--full", action="store_true", help="Run full golden set.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--markdown-out", type=Path, help="Write PR-comment markdown.")
    args = parser.parse_args()

    if not args.smoke and not args.full:
        parser.error("Pick --smoke or --full")

    items = load_golden(args.golden)
    if args.smoke:
        items = stratified_smoke(items)
        if not items:
            print("Smoke set yielded zero items, golden_set.jsonl empty?", file=sys.stderr)
            return 2

    if not get_settings().anthropic_api_key.get_secret_value().startswith("sk-ant-"):
        print(
            "ANTHROPIC_API_KEY missing or test placeholder, eval needs a real key.",
            file=sys.stderr,
        )
        return 2

    print(f"Running {len(items)} items at concurrency={args.concurrency}…", file=sys.stderr)
    records = asyncio.run(run_async(items, args.concurrency))

    sha = _git_sha() or os.getenv("GITHUB_SHA")
    scorecard = build_scorecard(records, git_sha=sha)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(scorecard.model_dump_json(indent=2))
    print(f"\nScorecard → {args.out}", file=sys.stderr)
    print(scorecard.model_dump_json(indent=2))

    prev: Scorecard | None = None
    if args.baseline and args.baseline.exists():
        prev = Scorecard.model_validate_json(args.baseline.read_text())

    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(format_markdown(scorecard, prev))

    if args.fail_on_regression and prev is not None:
        regs = regressions(prev, scorecard)
        if regs:
            print("\n--- REGRESSIONS ---", file=sys.stderr)
            for r in regs:
                print(r, file=sys.stderr)
            return 1
        print("\nNo regressions ≥ 5%. ✓", file=sys.stderr)

    if prev is not None:
        d = diff(prev, scorecard)
        print("\n--- DIFF vs baseline ---", file=sys.stderr)
        for k, v in d.items():
            print(f"  {k}: {v['prev']:.4f} → {v['curr']:.4f} (Δ {v['delta']:+.4f})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
