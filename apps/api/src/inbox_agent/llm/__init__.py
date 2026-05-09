"""Single entry-point for all LLM calls.

Every Anthropic call in the codebase goes through `LLMClient`. This invariant
is enforced by ruff/mypy and a unit test that greps the source tree.
"""

from inbox_agent.llm.client import LLMClient, LLMResult
from inbox_agent.llm.cost import ModelPricing, compute_cost_usd, get_pricing

__all__ = ["LLMClient", "LLMResult", "ModelPricing", "compute_cost_usd", "get_pricing"]
