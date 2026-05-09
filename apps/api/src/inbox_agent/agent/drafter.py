"""Drafter stage: ticket + classification + optional FAQ context → reply."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inbox_agent.config import get_settings
from inbox_agent.llm.tool_schemas import DRAFT_TOOL, DraftOutput

if TYPE_CHECKING:
    from inbox_agent.agent.prompts import PromptLoader
    from inbox_agent.faq.retrieve import FAQContextItem
    from inbox_agent.llm.client import LLMClient, LLMResult


def format_faq_context(items: list[FAQContextItem]) -> str:
    if not items:
        return (
            "No FAQ context was retrieved. If the answer is not derivable from the "
            "ticket alone, defer to a human."
        )
    blocks = [f"FAQ chunk id={it.chunk_id} (similarity={it.score:.2f}):\n{it.text}" for it in items]
    return "FAQ context (cite by chunk id when used):\n\n" + "\n\n".join(blocks)


class Drafter:
    def __init__(self, llm: LLMClient, prompts: PromptLoader) -> None:
        self._llm = llm
        self._prompts = prompts

    async def draft(
        self,
        *,
        ticket: str,
        classification: str,
        confidence: float,
        faq_context: list[FAQContextItem],
    ) -> LLMResult[DraftOutput]:
        prompt = self._prompts.load("draft")
        system, user = prompt.render(
            ticket=ticket,
            classification=classification,
            confidence=confidence,
            faq_context_block=format_faq_context(faq_context),
        )
        return await self._llm.call_with_tool(
            model=get_settings().anthropic_model_primary,
            system=system,
            user=user,
            tool=DRAFT_TOOL,
            output_model=DraftOutput,
            operation="draft",
            metadata={
                "prompt_version": prompt.version,
                "classification": classification,
                "faq_chunks_used": [it.chunk_id for it in faq_context],
            },
            max_tokens=1024,
        )
