"""Classifier stage: ticket text → category + confidence + rationale."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inbox_agent.config import get_settings
from inbox_agent.llm.tool_schemas import CLASSIFY_TOOL, ClassifyOutput

if TYPE_CHECKING:
    from inbox_agent.agent.prompts import PromptLoader
    from inbox_agent.llm.client import LLMClient, LLMResult


class Classifier:
    def __init__(self, llm: LLMClient, prompts: PromptLoader) -> None:
        self._llm = llm
        self._prompts = prompts

    async def classify(self, ticket: str) -> LLMResult[ClassifyOutput]:
        prompt = self._prompts.load("classify")
        system, user = prompt.render(ticket=ticket)
        return await self._llm.call_with_tool(
            model=get_settings().anthropic_model_primary,
            system=system,
            user=user,
            tool=CLASSIFY_TOOL,
            output_model=ClassifyOutput,
            operation="classify",
            metadata={"prompt_version": prompt.version},
            max_tokens=512,
        )
