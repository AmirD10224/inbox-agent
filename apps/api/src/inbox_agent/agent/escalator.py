"""Escalator stage: ticket + classification + draft → escalate Y/N + team."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inbox_agent.config import get_settings
from inbox_agent.llm.tool_schemas import ESCALATE_TOOL, EscalateOutput

if TYPE_CHECKING:
    from inbox_agent.agent.prompts import PromptLoader
    from inbox_agent.llm.client import LLMClient, LLMResult


class Escalator:
    def __init__(self, llm: LLMClient, prompts: PromptLoader) -> None:
        self._llm = llm
        self._prompts = prompts

    async def decide(
        self,
        *,
        ticket: str,
        classification: str,
        confidence: float,
        drafted_response: str,
    ) -> LLMResult[EscalateOutput]:
        prompt = self._prompts.load("escalate")
        system, user = prompt.render(
            ticket=ticket,
            classification=classification,
            confidence=confidence,
            drafted_response=drafted_response or "(no draft produced)",
        )
        return await self._llm.call_with_tool(
            model=get_settings().anthropic_model_primary,
            system=system,
            user=user,
            tool=ESCALATE_TOOL,
            output_model=EscalateOutput,
            operation="escalate",
            metadata={
                "prompt_version": prompt.version,
                "classification": classification,
                "confidence": confidence,
            },
            max_tokens=512,
        )
