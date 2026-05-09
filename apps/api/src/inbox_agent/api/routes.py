"""FastAPI route handlers."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from inbox_agent import __version__
from inbox_agent.agent import Classifier, Drafter, Escalator, Orchestrator
from inbox_agent.api.deps import (
    get_classifier,
    get_db_session,
    get_drafter,
    get_escalator,
    get_ingestor,
    get_orchestrator,
    get_retriever,
)
from inbox_agent.api.schemas import (
    CallSummary,
    ClassifyRequest,
    ClassifyResponse,
    DraftCitationOut,
    DraftRequest,
    DraftResponse,
    EscalateRequest,
    EscalateResponse,
    HealthResponse,
    IngestFAQRequest,
    IngestFAQResponse,
    RunRequest,
    RunResponse,
    TraceOut,
    TracesListResponse,
)
from inbox_agent.config import get_settings
from inbox_agent.db.models import Trace
from inbox_agent.faq import FAQIngestor, FAQRetriever
from inbox_agent.llm.client import LLMOutputError, LLMResult
from inbox_agent.logging import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    db_status: Literal["ok", "error"] = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        log.warning("health_db_check_failed", error=str(e))
        db_status = "error"
    return HealthResponse(
        version=__version__,
        db=db_status,
        langfuse_enabled=get_settings().langfuse_enabled,
    )


@router.post("/classify", response_model=ClassifyResponse)
async def classify(
    payload: ClassifyRequest,
    classifier: Classifier = Depends(get_classifier),
) -> ClassifyResponse:
    try:
        result = await classifier.classify(payload.ticket)
    except LLMOutputError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return ClassifyResponse(
        category=result.output.category,
        confidence=result.output.confidence,
        rationale=result.output.rationale,
        call=_summarize("classify", result),
    )


@router.post("/draft", response_model=DraftResponse)
async def draft(
    payload: DraftRequest,
    drafter: Drafter = Depends(get_drafter),
    retriever: FAQRetriever = Depends(get_retriever),
    session: AsyncSession = Depends(get_db_session),
) -> DraftResponse:
    faq_items = []
    if payload.use_faq:
        try:
            faq_items = await retriever.search(
                query=payload.ticket, top_k=payload.faq_top_k, session=session
            )
        except Exception as e:
            log.warning("faq_retrieve_failed_in_draft", error=str(e))

    try:
        result = await drafter.draft(
            ticket=payload.ticket,
            classification=payload.classification,
            confidence=payload.confidence,
            faq_context=faq_items,
        )
    except LLMOutputError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    return DraftResponse(
        response=result.output.response,
        citations=[
            DraftCitationOut(faq_id=c.faq_id, quote=c.quote) for c in result.output.citations
        ],
        tone=result.output.tone,
        faq_chunks_used=[it.chunk_id for it in faq_items],
        call=_summarize("draft", result),
    )


@router.post("/escalate-decision", response_model=EscalateResponse)
async def escalate_decision(
    payload: EscalateRequest,
    escalator: Escalator = Depends(get_escalator),
) -> EscalateResponse:
    try:
        result = await escalator.decide(
            ticket=payload.ticket,
            classification=payload.classification,
            confidence=payload.confidence,
            drafted_response=payload.drafted_response,
        )
    except LLMOutputError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    return EscalateResponse(
        escalate=result.output.escalate,
        reasoning=result.output.reasoning,
        suggested_team=result.output.suggested_team,
        call=_summarize("escalate", result),
    )


@router.post("/run", response_model=RunResponse)
async def run_full(
    payload: RunRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    try:
        run = await orchestrator.run(
            ticket=payload.ticket,
            session=session,
            use_faq=payload.use_faq,
        )
    except LLMOutputError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    cls_call = _call_from_dict(run.llm_calls[0])
    draft_call = _call_from_dict(run.llm_calls[1])
    esc_call = _call_from_dict(run.llm_calls[2])

    return RunResponse(
        trace_id=run.trace_id,
        classification=ClassifyResponse(
            category=run.classification.category,
            confidence=run.classification.confidence,
            rationale=run.classification.rationale,
            call=cls_call,
        ),
        draft=DraftResponse(
            response=run.draft.response,
            citations=[
                DraftCitationOut(faq_id=c.faq_id, quote=c.quote) for c in run.draft.citations
            ],
            tone=run.draft.tone,
            faq_chunks_used=[it.chunk_id for it in run.faq_chunks_used],
            call=draft_call,
        ),
        escalation=EscalateResponse(
            escalate=run.escalation.escalate,
            reasoning=run.escalation.reasoning,
            suggested_team=run.escalation.suggested_team,
            call=esc_call,
        ),
        total_input_tokens=run.total_input_tokens,
        total_output_tokens=run.total_output_tokens,
        total_cost_usd=run.total_cost_usd,
        total_latency_ms=run.total_latency_ms,
    )


@router.get("/traces", response_model=TracesListResponse)
async def list_traces(
    session: AsyncSession = Depends(get_db_session),
    limit: int = 50,
) -> TracesListResponse:
    limit = max(1, min(limit, 200))
    stmt = select(Trace).order_by(Trace.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    out: list[TraceOut] = []
    for row in rows:
        out.append(
            TraceOut(
                id=row.id,
                operation=row.operation,
                ticket_text=row.ticket_text,
                classification=row.classification,
                confidence=row.confidence,
                escalated=row.escalated,
                suggested_team=row.suggested_team,
                drafted_response=row.drafted_response,
                total_input_tokens=row.total_input_tokens,
                total_output_tokens=row.total_output_tokens,
                total_cost_usd=row.total_cost_usd,
                total_latency_ms=row.total_latency_ms,
                # Partial failures append a non-call marker (`{"stage": "error", ...}`);
                # filter those out, only real per-call summaries belong on the wire.
                llm_calls=[
                    _call_from_dict(c)
                    for c in row.llm_calls
                    if c.get("stage") in {"classify", "draft", "escalate"}
                ],
                langfuse_trace_id=row.langfuse_trace_id,
                created_at=row.created_at,
            )
        )
    return TracesListResponse(traces=out, count=len(out))


@router.post("/ingest-faq", response_model=IngestFAQResponse, status_code=status.HTTP_201_CREATED)
async def ingest_faq(
    payload: IngestFAQRequest,
    ingestor: FAQIngestor = Depends(get_ingestor),
    session: AsyncSession = Depends(get_db_session),
) -> IngestFAQResponse:
    try:
        result = await ingestor.ingest(url=str(payload.url), session=session)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        log.exception("ingest_faq_failed", url=str(payload.url))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    return IngestFAQResponse(
        document_id=result.document_id,
        source_url=result.source_url,
        title=result.title,
        chunks_inserted=result.chunks_inserted,
    )


# ─── helpers ───────────────────────────────────────────────────────────────


def _summarize(
    stage: Literal["classify", "draft", "escalate"],
    result: LLMResult[Any],
) -> CallSummary:
    return CallSummary(
        stage=stage,
        trace_id=result.trace_id,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        repair_attempts=result.repair_attempts,
        langfuse_url=result.langfuse_url,
    )


def _call_from_dict(d: dict[str, Any]) -> CallSummary:
    return CallSummary(
        stage=d["stage"],
        trace_id=str(d["trace_id"]),
        model=str(d["model"]),
        input_tokens=int(d["input_tokens"]),
        output_tokens=int(d["output_tokens"]),
        cost_usd=float(d["cost_usd"]),
        latency_ms=int(d["latency_ms"]),
        repair_attempts=int(d["repair_attempts"]),
        langfuse_url=d.get("langfuse_url"),
    )
