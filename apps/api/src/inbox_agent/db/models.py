"""SQLAlchemy 2.0 models for traces and FAQ chunks.

Tables:
- traces:    one row per orchestrator run; aggregates the 3 LLM calls.
- faq_chunks: ingested FAQ text + voyage-3 embedding for retrieval.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Voyage-3 produces 1024-dim embeddings (default).
EMBED_DIM = 1024


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONB}


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Ticket inputs
    ticket_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Aggregated agent outputs (nullable, partial runs ok).
    classification: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float)
    escalated: Mapped[bool | None] = mapped_column()
    suggested_team: Mapped[str | None] = mapped_column(String(32))
    drafted_response: Mapped[str | None] = mapped_column(Text)

    # Per-call breakdown for the dashboard. Each entry: {trace_id, model, latency_ms, ...}.
    # Postgres uses JSONB (indexable); SQLite (test only) falls back to JSON.
    llm_calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )

    # Aggregates.
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Langfuse deep-link (nullable when Langfuse is unconfigured).
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (Index("ix_traces_created_at_desc", "created_at"),)


class FAQDocument(Base):
    __tablename__ = "faq_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(512))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list[FAQChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class FAQChunk(Base):
    __tablename__ = "faq_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("faq_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Voyage-extracted Q (optional), when chunk represents a Q/A pair.
    question: Mapped[str | None] = mapped_column(Text)

    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM), nullable=False)

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[FAQDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        # hnsw works on empty tables and builds incrementally, see migration
        # 0001 for the operational rationale (vs ivfflat).
        Index(
            "ix_faq_chunks_embedding_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
