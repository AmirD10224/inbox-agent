"""The single Anthropic client wrapper.

Every LLM call in the system goes through `LLMClient.call_with_tool`. This is
the single place that owns: retries, cost accounting, structured outputs via
tool-use, Langfuse tracing, structured logging, timeout policy.

Test surface: unit tests stub Anthropic at the `httpx`/`respx` level so the
client's retry+repair logic is exercised against realistic Anthropic payloads.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, cast

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AsyncAnthropic,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from inbox_agent.config import get_settings
from inbox_agent.llm.cost import compute_cost_usd
from inbox_agent.llm.tool_schemas import AnthropicTool, repair_with_pydantic
from inbox_agent.llm.tracing import trace_generation
from inbox_agent.logging import get_logger

log = get_logger(__name__)


class LLMOutputError(RuntimeError):
    """The model produced output we could not validate after retries."""


@dataclass(slots=True)
class LLMResult[T: BaseModel]:
    """Outcome of a single tool-forced call."""

    output: T
    trace_id: str
    langfuse_url: str | None
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    repair_attempts: int = 0
    raw_tool_input: dict[str, Any] = field(default_factory=dict)


# Errors safe to retry. We deliberately exclude 4xx (auth, permission, bad
# request, not found, unprocessable), those are configuration mistakes that
# retrying will not fix and only delay the visible failure.
_TRANSIENT = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


class LLMClient:
    """Thin wrapper around `AsyncAnthropic` that enforces tool-use + tracing.

    A single instance is created at app startup (DI in FastAPI) so the
    underlying httpx pool is reused.
    """

    def __init__(self, anthropic: AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        self._client = anthropic or AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.anthropic_timeout_s,
            max_retries=0,  # we own retries to keep visibility + tenacity-free.
        )
        self._max_retries = settings.anthropic_max_retries

    async def call_with_tool[T: BaseModel](
        self,
        *,
        model: str,
        system: str,
        user: str,
        tool: AnthropicTool,
        output_model: type[T],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResult[T]:
        """Run a tool-forced call and return a validated, traced result.

        Retry policy: up to `anthropic_max_retries` total attempts, exponential
        backoff (0.5s base, doubled per attempt, capped at 4s) on transient
        SDK errors. Pydantic validation failures trigger a single repair
        attempt with a tightened reminder appended to the user message.
        """
        meta = {**(metadata or {}), "operation": operation}
        repair_attempts = 0
        last_validation_err: ValidationError | None = None
        effective_user = user

        with trace_generation(
            name=operation,
            model=model,
            input_payload={"system": system, "user": user},
            metadata=meta,
        ) as trace:
            start = time.perf_counter()

            for attempt in range(1, self._max_retries + 1):
                try:
                    # The Anthropic SDK has heavily-overloaded TypedDicts for
                    # tools/messages; runtime accepts plain dicts. Cast through
                    # Any to avoid pinning to a specific SDK type alias.
                    response = await self._client.messages.create(
                        model=model,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        tools=cast("Any", [tool]),
                        tool_choice=cast("Any", {"type": "tool", "name": tool["name"]}),
                        messages=cast("Any", [{"role": "user", "content": effective_user}]),
                    )
                except _TRANSIENT as e:
                    if attempt == self._max_retries:
                        log.error(
                            "llm_call_transient_giveup",
                            operation=operation,
                            attempts=attempt,
                            error=str(e),
                        )
                        raise
                    delay = min(0.5 * 2 ** (attempt - 1), 4.0)
                    log.warning(
                        "llm_call_transient_retry",
                        operation=operation,
                        attempt=attempt,
                        delay_s=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    continue

                tool_input = _extract_tool_input(response, tool["name"])
                try:
                    validated = repair_with_pydantic(output_model, tool_input)
                    break
                except ValidationError as e:
                    last_validation_err = e
                    repair_attempts += 1
                    if repair_attempts >= 2:
                        log.error(
                            "llm_call_validation_giveup",
                            operation=operation,
                            errors=e.errors(),
                            payload=tool_input,
                        )
                        msg = (
                            f"LLM output failed validation after {repair_attempts} attempts: "
                            f"{e.errors()}"
                        )
                        raise LLMOutputError(msg) from e
                    log.warning(
                        "llm_call_validation_repair",
                        operation=operation,
                        errors=e.errors(),
                    )
                    effective_user = (
                        f"{user}\n\n"
                        f"Your previous output failed validation: {e.errors()}. "
                        f"Re-emit a tool call that strictly conforms to the schema."
                    )
            else:
                # Reached when the loop exhausts without `break`. With the
                # default `_max_retries=3` this is rare (the validation
                # give-up at attempt 2 raises first), but with `_max_retries=1`
                # a single ValidationError exits the loop normally and we
                # need to surface it here.
                if last_validation_err is not None:
                    msg = f"LLM output failed validation: {last_validation_err.errors()}"
                    raise LLMOutputError(msg) from last_validation_err
                msg = "LLM call exhausted retries with no response"
                raise LLMOutputError(msg)

            latency_ms = int((time.perf_counter() - start) * 1000)

            usage = response.usage
            cost_usd = compute_cost_usd(
                model=model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            )

            trace.input_tokens = usage.input_tokens
            trace.output_tokens = usage.output_tokens
            trace.cost_usd = cost_usd
            trace.output = tool_input
            trace.extra_metadata["repair_attempts"] = repair_attempts
            trace.extra_metadata["latency_ms"] = latency_ms

            log.info(
                "llm_call_complete",
                operation=operation,
                model=model,
                trace_id=trace.trace_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=round(cost_usd, 6),
                latency_ms=latency_ms,
                repair_attempts=repair_attempts,
            )

            return LLMResult(
                output=validated,
                trace_id=trace.trace_id,
                langfuse_url=trace.langfuse_url,
                model=model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                repair_attempts=repair_attempts,
                raw_tool_input=tool_input,
            )


def _extract_tool_input(response: Any, tool_name: str) -> dict[str, Any]:
    """Pull the `tool_use` block matching `tool_name` from a Messages response."""
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
            return dict(block.input)
    msg = f"No tool_use block named {tool_name!r} in response"
    raise LLMOutputError(msg)


__all__ = ["LLMClient", "LLMOutputError", "LLMResult"]
