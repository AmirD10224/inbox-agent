"""Scorecard computation + diff comparison for the regression gate."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean

from evals.types import RunRecord, Scorecard


def build_scorecard(records: list[RunRecord], git_sha: str | None = None) -> Scorecard:
    if not records:
        msg = "Cannot build scorecard from zero records"
        raise ValueError(msg)

    n = len(records)
    class_correct = sum(1 for r in records if r.expected_class == r.actual_class)
    esc_correct = sum(1 for r in records if r.expected_escalate == r.actual_escalate)
    team_correct = sum(1 for r in records if r.expected_team == r.actual_team)

    by_class: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        by_class[r.expected_class].append(r.expected_class == r.actual_class)

    latencies = sorted(r.latency_ms for r in records)
    p50 = latencies[int(0.50 * (len(latencies) - 1))]
    p95 = latencies[int(0.95 * (len(latencies) - 1))]

    failures = [
        r.id
        for r in records
        if r.judge_label == "incorrect" or r.expected_class != r.actual_class
    ]

    return Scorecard(
        n=n,
        classification_accuracy=class_correct / n,
        escalation_accuracy=esc_correct / n,
        team_accuracy=team_correct / n,
        judge_mean_score=mean(r.judge_score for r in records),
        hallucination_rate=sum(1 for r in records if r.judge_label == "incorrect") / n,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        avg_cost_usd=mean(r.cost_usd for r in records),
        total_cost_usd=sum(r.cost_usd for r in records),
        per_class_accuracy={
            cls: sum(hits) / len(hits) for cls, hits in by_class.items()
        },
        failures=failures,
        git_sha=git_sha,
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
    )


# ─── Regression gate ───────────────────────────────────────────────────────


# Metrics where higher is better.
_HIGHER_IS_BETTER = (
    "classification_accuracy",
    "escalation_accuracy",
    "team_accuracy",
    "judge_mean_score",
)
# Metrics where lower is better.
_LOWER_IS_BETTER = (
    "hallucination_rate",
    "p95_latency_ms",
    "avg_cost_usd",
)
REGRESSION_THRESHOLD = 0.05  # 5%, used on full runs (n≥50).
# Sample-size floor below which a single label flip exceeds 5% on a rate
# metric (1/20 = 5%). Below this, the gate is statistically incoherent and
# should not fire; users can still see the diff in the PR comment.
MIN_N_FOR_GATE = 20


def diff(prev: Scorecard, curr: Scorecard) -> dict[str, dict[str, float]]:
    """Return per-metric {prev, curr, delta}. Positive delta = curr larger."""
    out: dict[str, dict[str, float]] = {}
    for name in (*_HIGHER_IS_BETTER, *_LOWER_IS_BETTER):
        p = float(getattr(prev, name))
        c = float(getattr(curr, name))
        out[name] = {"prev": p, "curr": c, "delta": c - p}
    return out


def regressions(prev: Scorecard, curr: Scorecard) -> list[str]:
    """Return human-readable strings naming each metric that regressed >5%.

    Returns an empty list when `curr.n < MIN_N_FOR_GATE`, on small samples a
    single label flip is already > 5%, so the gate would fire on noise. The
    diff is still visible in the PR comment via `format_markdown`.
    """
    if curr.n < MIN_N_FOR_GATE:
        return []
    msgs: list[str] = []
    for name in _HIGHER_IS_BETTER:
        p = float(getattr(prev, name))
        c = float(getattr(curr, name))
        if p > 0 and (p - c) / p > REGRESSION_THRESHOLD:
            msgs.append(f"{name}: {p:.4f} → {c:.4f} (-{(p - c) / p * 100:.1f}%)")
    for name in _LOWER_IS_BETTER:
        p = float(getattr(prev, name))
        c = float(getattr(curr, name))
        if p > 0 and (c - p) / p > REGRESSION_THRESHOLD:
            msgs.append(f"{name}: {p:.4f} → {c:.4f} (+{(c - p) / p * 100:.1f}%)")
    return msgs


def format_markdown(curr: Scorecard, prev: Scorecard | None) -> str:
    """Markdown summary suitable for a PR comment."""
    lines = [
        f"### InboxAgent eval scorecard, n={curr.n}",
        "",
        "| Metric | Value | Δ vs main |",
        "| --- | ---: | ---: |",
    ]
    rows = [
        ("Classification accuracy", "classification_accuracy", "{:.1%}"),
        ("Escalation accuracy", "escalation_accuracy", "{:.1%}"),
        ("Team accuracy", "team_accuracy", "{:.1%}"),
        ("Judge mean score", "judge_mean_score", "{:.3f}"),
        ("Hallucination rate", "hallucination_rate", "{:.1%}"),
        ("p50 latency", "p50_latency_ms", "{:.0f} ms"),
        ("p95 latency", "p95_latency_ms", "{:.0f} ms"),
        ("Avg cost / ticket", "avg_cost_usd", "${:.4f}"),
        ("Total cost", "total_cost_usd", "${:.3f}"),
    ]
    for label, attr, fmt in rows:
        c = float(getattr(curr, attr))
        cell_curr = fmt.format(c)
        if prev is not None:
            p = float(getattr(prev, attr))
            delta = c - p
            cell_delta = fmt.format(delta) if abs(delta) > 0 else "-"
        else:
            cell_delta = "-"
        lines.append(f"| {label} | {cell_curr} | {cell_delta} |")

    if curr.failures:
        lines.append("")
        lines.append(f"**{len(curr.failures)} failure(s):** `{', '.join(curr.failures)}`")
    if prev is not None:
        regs = regressions(prev, curr)
        if regs:
            lines.append("")
            lines.append("**⚠ Regressions (>5%):**")
            for r in regs:
                lines.append(f"- {r}")
        elif curr.n < MIN_N_FOR_GATE:
            lines.append("")
            lines.append(
                f"_Regression gate suppressed: n={curr.n} < {MIN_N_FOR_GATE} "
                f"(label this PR `eval` to run the full set)._"
            )
    return "\n".join(lines)
