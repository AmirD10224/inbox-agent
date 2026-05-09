"""Calibrated LLM-as-judge using Claude Haiku 4.5.

The judge reads the agent's drafted response and the golden expected answer,
then scores faithfulness + correctness via a forced-JSON tool call.
"""

from __future__ import annotations

from inbox_agent.agent.prompts import get_prompt_loader
from inbox_agent.config import get_settings
from inbox_agent.llm.client import LLMClient
from inbox_agent.llm.tool_schemas import JUDGE_TOOL, JudgeOutput


class Judge:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm or LLMClient()
        self._prompts = get_prompt_loader()

    async def judge(
        self,
        *,
        ticket: str,
        expected: str,
        faq_context: str,
        drafted: str,
    ) -> JudgeOutput:
        prompt = self._prompts.load("judge")
        system, user = prompt.render(
            ticket=ticket,
            expected=expected,
            faq_context=faq_context or "(none)",
            drafted=drafted,
        )
        result = await self._llm.call_with_tool(
            model=get_settings().anthropic_model_judge,
            system=system,
            user=user,
            tool=JUDGE_TOOL,
            output_model=JudgeOutput,
            operation="judge",
            metadata={"prompt_version": prompt.version},
            temperature=0.0,
            max_tokens=512,
        )
        return result.output
