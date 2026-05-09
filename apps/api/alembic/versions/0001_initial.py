"""initial schema: traces, faq_documents, faq_chunks (+ pgvector extension)

Revision ID: 0001
Revises:
Create Date: 2026-05-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("ticket_text", sa.Text, nullable=False),
        sa.Column("classification", sa.String(32)),
        sa.Column("confidence", sa.Float),
        sa.Column("escalated", sa.Boolean),
        sa.Column("suggested_team", sa.String(32)),
        sa.Column("drafted_response", sa.Text),
        sa.Column("llm_calls", sa.dialects.postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("total_input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("langfuse_trace_id", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_traces_operation", "traces", ["operation"])
    op.create_index("ix_traces_created_at_desc", "traces", ["created_at"])

    op.create_table(
        "faq_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_url", sa.String(2048), nullable=False, unique=True),
        sa.Column("title", sa.String(512)),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "faq_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("faq_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("question", sa.Text),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_faq_chunks_document_id", "faq_chunks", ["document_id"])
    # hnsw (pgvector ≥ 0.5) builds incrementally and works on empty tables.
    # ivfflat would require a REINDEX after the first batch of rows lands or
    # its centroids are computed on zero data, we skip that operational
    # footgun by using hnsw from day one.
    op.execute(
        "CREATE INDEX ix_faq_chunks_embedding_cosine ON faq_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_faq_chunks_embedding_cosine", table_name="faq_chunks")
    op.drop_index("ix_faq_chunks_document_id", table_name="faq_chunks")
    op.drop_table("faq_chunks")
    op.drop_table("faq_documents")
    op.drop_index("ix_traces_created_at_desc", table_name="traces")
    op.drop_index("ix_traces_operation", table_name="traces")
    op.drop_table("traces")
    op.execute("DROP EXTENSION IF EXISTS vector")
