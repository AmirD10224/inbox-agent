"""Pydantic v2 request/response schemas for the public API.

Kept separate from the internal `tool_schemas` (LLM JSON shapes) so the wire
contract can evolve independently of prompt schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ─── Shared ────────────────────────────────────────────────────────────────


class CallSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["classify", "draft", "escalate"]
    trace_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    repair_attempts: int
    langfuse_url: str | None = None


# ─── /classify ─────────────────────────────────────────────────────────────


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str = Field(min_length=1, max_length=10_000)


class ClassifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["billing", "technical", "account", "refund", "other"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    call: CallSummary


# ─── /draft ────────────────────────────────────────────────────────────────


class DraftCitationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    faq_id: str
    quote: str


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: str = Field(min_length=1, max_length=10_000)
    classification: Literal["billing", "technical", "account", "refund", "other"]
    confidence: float = Field(ge=0.0, le=1.0)
    use_faq: bool = True
    faq_top_k: int = Field(default=3, ge=1, le=10)


class DraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    citations: list[DraftCitationOut]
    tone: Literal["empathetic", "neutral", "apologetic", "informative"]
    faq_chunks_used: list[str]
    call: CallSummary


# ─── /escalate-decision ────────────────────────────────────────────────────


class EscalateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: str = Field(min_length=1, max_length=10_000)
    classification: Literal["billing", "technical", "account", "refund", "other"]
    confidence: float = Field(ge=0.0, le=1.0)
    drafted_response: str = Field(default="", max_length=5000)


class EscalateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    escalate: bool
    reasoning: str
    suggested_team: Literal["billing", "engineering", "trust_safety", "general", "none"]
    call: CallSummary


# ─── /run (orchestrated end-to-end) ────────────────────────────────────────


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: str = Field(min_length=1, max_length=10_000)
    use_faq: bool = True
    faq_top_k: int = Field(default=3, ge=1, le=10)


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    classification: ClassifyResponse
    draft: DraftResponse
    escalation: EscalateResponse
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int


# ─── /traces ───────────────────────────────────────────────────────────────


class TraceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    operation: str
    ticket_text: str
    classification: str | None
    confidence: float | None
    escalated: bool | None
    suggested_team: str | None
    drafted_response: str | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    llm_calls: list[CallSummary]
    langfuse_trace_id: str | None
    created_at: datetime


class TracesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    traces: list[TraceOut]
    count: int


# ─── /ingest-faq ───────────────────────────────────────────────────────────


class IngestFAQRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl


class IngestFAQResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_url: str
    title: str | None
    chunks_inserted: int


# ─── /health ───────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    version: str
    db: Literal["ok", "error"]
    langfuse_enabled: bool
