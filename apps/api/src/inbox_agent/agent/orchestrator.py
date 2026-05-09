"""End-to-end orchestrator: classify → retrieve → draft → escalate.

Persists exactly one `Trace` row per ticket, successful runs and partial
failures alike, so the dashboard tells the truth about real behaviour
instead of only the happy path.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from inbox_agent.db.models import Trace
from inbox_agent.llm.client import LLMOutputError
from inbox_agent.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from inbox_agent.agent.classifier import Classifier
    from inbox_agent.agent.drafter import Drafter
    from inbox_agent.agent.escalator import Escalator
    from inbox_agent.faq.retrieve import FAQContextItem, FAQRetriever
    from inbox_agent.llm.tool_schemas import ClassifyOutput, DraftOutput, EscalateOutput

log = get_logger(__name__)


@dataclass(slots=True)
class AgentRun:
    trace_id: str
    classification: ClassifyOutput
    draft: DraftOutput
    escalation: EscalateOutput
    faq_chunks_used: list[FAQContextItem]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    llm_calls: list[dict[str, Any]] = field(default_factory=list)


class Orchestrator:
    """Composes the three agent stages and persists the outcome."""

    def __init__(
        self,
        *,
        classifier: Classifier,
        drafter: Drafter,
        escalator: Escalator,
        retriever: FAQRetriever | None = None,
        faq_top_k: int = 3,
    ) -> None:
        self._classifier = classifier
        self._drafter = drafter
        self._escalator = escalator
        self._retriever = retriever
        self._faq_top_k = faq_top_k

    async def run(
        self,
        *,
        ticket: str,
        session: AsyncSession,
        use_faq: bool = True,
    ) -> AgentRun:
        trace_id = str(uuid.uuid4())
        # Track per-stage state so we can persist a partial Trace on failure.
        cls_result = None
        draft_result = None
        esc_result = None
        faq_items: list[FAQContextItem] = []
        llm_calls: list[dict[str, Any]] = []

        try:
            # 1. Classify.
            cls_result = await self._classifier.classify(ticket)
            llm_calls.append(_call_summary("classify", cls_result))

            # 2. Retrieve FAQ context (caller may opt out).
            if use_faq and self._retriever is not None:
                try:
                    faq_items = await self._retriever.search(
                        query=ticket, top_k=self._faq_top_k, session=session
                    )
                except Exception as e:
                    log.warning("faq_retrieve_failed", trace_id=trace_id, error=str(e))

            # 3. Draft.
            draft_result = await self._drafter.draft(
                ticket=ticket,
                classification=cls_result.output.category,
                confidence=cls_result.output.confidence,
                faq_context=faq_items,
            )
            llm_calls.append(_call_summary("draft", draft_result))

            # 4. Escalate decision.
            esc_result = await self._escalator.decide(
                ticket=ticket,
                classification=cls_result.output.category,
                confidence=cls_result.output.confidence,
                drafted_response=draft_result.output.response,
            )
            llm_calls.append(_call_summary("escalate", esc_result))

        except LLMOutputError as e:
            # Persist the partial Trace so the dashboard reflects this run,
            # then re-raise so the route returns 502.
            await _persist_partial(
                session=session,
                trace_id=trace_id,
                ticket=ticket,
                cls_result=cls_result,
                draft_result=draft_result,
                esc_result=esc_result,
                llm_calls=llm_calls,
                error=str(e),
            )
            raise

        total_in = cls_result.input_tokens + draft_result.input_tokens + esc_result.input_tokens
        total_out = cls_result.output_tokens + draft_result.output_tokens + esc_result.output_tokens
        total_cost = cls_result.cost_usd + draft_result.cost_usd + esc_result.cost_usd
        total_latency = cls_result.latency_ms + draft_result.latency_ms + esc_result.latency_ms

        # Persist successful trace.
        trace_row = Trace(
            id=trace_id,
            operation="full_run",
            ticket_text=ticket,
            classification=cls_result.output.category,
            confidence=cls_result.output.confidence,
            escalated=esc_result.output.escalate,
            suggested_team=esc_result.output.suggested_team,
            drafted_response=draft_result.output.response,
            llm_calls=llm_calls,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            langfuse_trace_id=cls_result.trace_id,
        )
        session.add(trace_row)
        await session.flush()

        return AgentRun(
            trace_id=trace_id,
            classification=cls_result.output,
            draft=draft_result.output,
            escalation=esc_result.output,
            faq_chunks_used=faq_items,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            llm_calls=llm_calls,
        )


async def _persist_partial(
    *,
    session: AsyncSession,
    trace_id: str,
    ticket: str,
    cls_result: Any,
    draft_result: Any,
    esc_result: Any,
    llm_calls: list[dict[str, Any]],
    error: str,
) -> None:
    """Record whatever stages did complete before the failure."""
    classification = cls_result.output.category if cls_result is not None else None
    confidence = cls_result.output.confidence if cls_result is not None else None
    drafted_response = draft_result.output.response if draft_result is not None else None
    escalated = esc_result.output.escalate if esc_result is not None else None
    team = esc_result.output.suggested_team if esc_result is not None else None

    total_in = sum(c.get("input_tokens", 0) for c in llm_calls)
    total_out = sum(c.get("output_tokens", 0) for c in llm_calls)
    total_cost = sum(c.get("cost_usd", 0.0) for c in llm_calls)
    total_latency = sum(c.get("latency_ms", 0) for c in llm_calls)
    langfuse_trace_id = cls_result.trace_id if cls_result is not None else None

    enriched_calls = [*llm_calls, {"stage": "error", "error": error}]

    trace_row = Trace(
        id=trace_id,
        operation="full_run_failed",
        ticket_text=ticket,
        classification=classification,
        confidence=confidence,
        escalated=escalated,
        suggested_team=team,
        drafted_response=drafted_response,
        llm_calls=enriched_calls,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        langfuse_trace_id=langfuse_trace_id,
    )
    session.add(trace_row)
    try:
        await session.flush()
    except Exception as flush_err:  # pragma: no cover, defensive
        log.error("partial_trace_flush_failed", trace_id=trace_id, error=str(flush_err))


def _call_summary(stage: str, result: Any) -> dict[str, Any]:
    return {
        "stage": stage,
        "trace_id": result.trace_id,
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": round(result.cost_usd, 6),
        "latency_ms": result.latency_ms,
        "repair_attempts": result.repair_attempts,
        "langfuse_url": result.langfuse_url,
    }
