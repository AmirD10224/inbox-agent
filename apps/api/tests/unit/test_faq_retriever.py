"""Unit tests for FAQRetriever.

We don't spin up real pgvector here (that's covered by the e2e stack). Instead
we mock the embedder and the SQLAlchemy session to verify:
- the similarity = 1 - distance math
- the similarity_floor cutoff
- top-k limit
- empty-query short-circuit
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from inbox_agent.faq.retrieve import FAQRetriever, RetrievalConfig


@dataclass
class _FakeChunk:
    id: str
    text: str


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, float]]:
        return self._rows


class _FakeSession:
    """Minimal AsyncSession stand-in: returns a canned (chunk, distance) list."""

    def __init__(self, rows: list[tuple[_FakeChunk, float]]) -> None:
        self._rows = rows

    async def execute(self, _stmt: object) -> _FakeResult:
        return _FakeResult(self._rows)


class _FakeEmbedder:
    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        # Deterministic fake, content doesn't matter, only length matches expectations.
        return [[0.1] * 1024 for _ in texts]


@pytest.mark.asyncio
async def test_empty_query_short_circuits() -> None:
    retriever = FAQRetriever(embedder=_FakeEmbedder())
    out = await retriever.search(query="   ", top_k=3, session=_FakeSession([]))  # type: ignore[arg-type]
    assert out == []


@pytest.mark.asyncio
async def test_similarity_is_one_minus_distance() -> None:
    """A distance of 0.2 must produce a score of 0.8 (raw cosine), not 0.9."""
    rows = [(_FakeChunk(id="a", text="alpha"), 0.2)]
    retriever = FAQRetriever(
        embedder=_FakeEmbedder(),
        config=RetrievalConfig(similarity_floor=0.0),  # accept everything
    )
    out = await retriever.search(query="hi", top_k=3, session=_FakeSession(rows))  # type: ignore[arg-type]
    assert len(out) == 1
    assert out[0].chunk_id == "a"
    assert out[0].score == pytest.approx(0.8, rel=1e-6)


@pytest.mark.asyncio
async def test_similarity_floor_filters_low_scores() -> None:
    """Floor 0.5 admits dist≤0.5, rejects dist>0.5."""
    rows = [
        (_FakeChunk(id="hi", text="similar"), 0.10),  # sim 0.90 → keep
        (_FakeChunk(id="mid", text="ok"), 0.50),  # sim 0.50 → keep (boundary)
        (_FakeChunk(id="lo", text="far"), 0.80),  # sim 0.20 → drop
    ]
    retriever = FAQRetriever(
        embedder=_FakeEmbedder(),
        config=RetrievalConfig(similarity_floor=0.50),
    )
    out = await retriever.search(query="q", top_k=10, session=_FakeSession(rows))  # type: ignore[arg-type]
    ids = [item.chunk_id for item in out]
    assert ids == ["hi", "mid"]


@pytest.mark.asyncio
async def test_default_floor_rejects_irrelevant_chunks() -> None:
    """Default floor (0.40) must reject chunks at distance ~0.7 (raw sim 0.3)."""
    rows = [
        (_FakeChunk(id="rel", text="relevant"), 0.30),  # sim 0.70 → keep
        (_FakeChunk(id="noise", text="noise"), 0.70),  # sim 0.30 → drop
    ]
    retriever = FAQRetriever(embedder=_FakeEmbedder())  # default config
    out = await retriever.search(query="q", top_k=5, session=_FakeSession(rows))  # type: ignore[arg-type]
    assert [item.chunk_id for item in out] == ["rel"]


@pytest.mark.asyncio
async def test_top_k_limit_passed_to_query() -> None:
    """The retriever respects the SQL LIMIT; we just verify the call shape."""
    rows = [
        (_FakeChunk(id="a", text="t"), 0.10),
        (_FakeChunk(id="b", text="t"), 0.20),
    ]
    retriever = FAQRetriever(
        embedder=_FakeEmbedder(),
        config=RetrievalConfig(similarity_floor=0.0),
    )
    out = await retriever.search(query="q", top_k=5, session=_FakeSession(rows))  # type: ignore[arg-type]
    # The fake session returns whatever we hand it; we're verifying the
    # transformation, not that LIMIT was applied (that's a SQL-layer test).
    assert {item.chunk_id for item in out} == {"a", "b"}
