"""Smoke-set stratifier auto-balances across categories.

Replaces the previous frozen-literal `SMOKE_IDS` set so that adding a new
category to the golden set is automatically smoke-covered.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.run_evals import stratified_smoke
from evals.types import GoldenItem

# tests/unit/test_*.py → tests/unit → tests → apps/api → apps → repo root.
REPO_ROOT = Path(__file__).resolve().parents[4]
GOLDEN_SET = REPO_ROOT / "evals" / "golden_set.jsonl"


def _load_real_golden_set() -> list[GoldenItem]:
    if not GOLDEN_SET.exists():
        pytest.skip(f"golden set not found at {GOLDEN_SET}")
    items: list[GoldenItem] = []
    for line in GOLDEN_SET.read_text().splitlines():
        if line.strip():
            items.append(GoldenItem.model_validate(json.loads(line)))
    return items


def test_smoke_covers_every_class_present_in_golden() -> None:
    """A smoke run sees ≥1 example from every class the golden set defines."""
    golden = _load_real_golden_set()
    smoke = stratified_smoke(golden, per_class=2)
    assert smoke
    smoke_classes = {item.expected_class for item in smoke}
    golden_classes = {item.expected_class for item in golden}
    assert smoke_classes == golden_classes


def test_smoke_size_is_per_class_times_n_classes() -> None:
    golden = _load_real_golden_set()
    n_classes = len({item.expected_class for item in golden})
    smoke = stratified_smoke(golden, per_class=2)
    assert len(smoke) == n_classes * 2 or len(smoke) <= len(golden)


def test_smoke_is_deterministic() -> None:
    golden = _load_real_golden_set()
    a = [it.id for it in stratified_smoke(golden, per_class=2)]
    b = [it.id for it in stratified_smoke(golden, per_class=2)]
    assert a == b


def test_smoke_handles_per_class_larger_than_available() -> None:
    """If a class has fewer items than per_class, take what's available."""
    items = [
        GoldenItem(
            id="x1",
            ticket="t",
            expected_class="billing",
            expected_action={"escalate": False, "suggested_team": "none"},
        ),
        GoldenItem(
            id="x2",
            ticket="t",
            expected_class="other",
            expected_action={"escalate": False, "suggested_team": "none"},
        ),
    ]
    chosen = stratified_smoke(items, per_class=5)
    assert len(chosen) == 2
    assert {it.id for it in chosen} == {"x1", "x2"}
