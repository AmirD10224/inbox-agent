"""Unit tests for cost accounting."""

from __future__ import annotations

import pytest

from inbox_agent.llm.cost import compute_cost_usd, count_tokens_estimate, get_pricing


def test_pricing_known_models() -> None:
    sonnet = get_pricing("claude-sonnet-4-6")
    assert sonnet.input_per_mtok_usd == pytest.approx(3.0)
    assert sonnet.output_per_mtok_usd == pytest.approx(15.0)

    haiku = get_pricing("claude-haiku-4-5-20251001")
    assert haiku.input_per_mtok_usd == pytest.approx(1.0)
    assert haiku.output_per_mtok_usd == pytest.approx(5.0)


def test_pricing_unknown_model_falls_back_to_sonnet() -> None:
    fallback = get_pricing("nonsense-model-id")
    assert fallback == get_pricing("claude-sonnet-4-6")


def test_cost_basic_input_output() -> None:
    cost = compute_cost_usd(
        model="claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=500_000
    )
    # 1M @ $3 + 0.5M @ $15 = $3 + $7.50 = $10.50
    assert cost == pytest.approx(10.5)


def test_cost_with_cache() -> None:
    cost = compute_cost_usd(
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=500,
        cache_creation_input_tokens=2000,
        cache_read_input_tokens=10_000,
    )
    # 1000 * 3/1M + 500 * 15/1M + 2000 * 3.75/1M + 10000 * 0.30/1M
    expected = 0.003 + 0.0075 + 0.0075 + 0.003
    assert cost == pytest.approx(expected, rel=1e-6)


def test_cost_zero_tokens_is_zero() -> None:
    assert compute_cost_usd(model="claude-sonnet-4-6", input_tokens=0, output_tokens=0) == 0.0


def test_count_tokens_estimate_monotonic() -> None:
    short = count_tokens_estimate("hi")
    long = count_tokens_estimate("hi" * 1000)
    assert long > short
    assert short >= 1


def test_count_tokens_estimate_empty() -> None:
    assert count_tokens_estimate("") == 1
