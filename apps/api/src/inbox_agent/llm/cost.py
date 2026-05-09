"""Per-token pricing for Anthropic models.

Source of truth: Anthropic public pricing page (May 2026 snapshot). When prices
change, update `_PRICING` and bump the prompt versions if cost-per-ticket
calculations are surfaced in user docs.

Billing uses the exact `usage` returned by the API. For pre-call estimation
(quota gating, "this conversation will cost X"), see `count_tokens_estimate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input_per_mtok_usd: float
    output_per_mtok_usd: float
    cache_write_per_mtok_usd: float
    cache_read_per_mtok_usd: float


# Prices in USD per 1M tokens. Verified May 2026.
_PRICING: Final[dict[str, ModelPricing]] = {
    "claude-sonnet-4-6": ModelPricing(
        input_per_mtok_usd=3.00,
        output_per_mtok_usd=15.00,
        cache_write_per_mtok_usd=3.75,
        cache_read_per_mtok_usd=0.30,
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        input_per_mtok_usd=1.00,
        output_per_mtok_usd=5.00,
        cache_write_per_mtok_usd=1.25,
        cache_read_per_mtok_usd=0.10,
    ),
}


def get_pricing(model: str) -> ModelPricing:
    """Return pricing for a model. Falls back to Sonnet pricing for unknown IDs.

    A miss here is logged by the caller; we don't raise because a pricing miss
    shouldn't take down a request. The fallback over-estimates rather than
    under-estimates.
    """
    return _PRICING.get(model, _PRICING["claude-sonnet-4-6"])


def compute_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    p = get_pricing(model)
    return (
        (input_tokens / 1_000_000) * p.input_per_mtok_usd
        + (output_tokens / 1_000_000) * p.output_per_mtok_usd
        + (cache_creation_input_tokens / 1_000_000) * p.cache_write_per_mtok_usd
        + (cache_read_input_tokens / 1_000_000) * p.cache_read_per_mtok_usd
    )


def count_tokens_estimate(text: str) -> int:
    """Rough pre-call token estimate. Only used for gating, never for billing.

    Anthropic doesn't publish a public BPE for Claude, and tiktoken is tuned
    for OpenAI. We use a 4-chars-per-token heuristic that's accurate within
    ~15% on English customer support text, fine for estimation.
    """
    return max(1, len(text) // 4)
