"""FAQ retrieval over pgvector cosine similarity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from inbox_agent.db.models import FAQChunk
from inbox_agent.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from inbox_agent.faq.embed import EmbeddingClient

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FAQContextItem:
    """A retrieved FAQ chunk consumable by the Drafter."""

    chunk_id: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    """Retrieval thresholds.

    `similarity_floor` is **raw cosine similarity** in [-1, 1]. With L2-normalized
    embeddings (Voyage-3 default), unrelated text typically scores < 0.30, loosely
    related 0.30-0.45, on-topic 0.45+. The default 0.40 was tuned against the
    golden set, bumping to 0.50+ trades recall for precision.
    """

    similarity_floor: float = 0.40


class FAQRetriever:
    def __init__(
        self,
        *,
        embedder: EmbeddingClient,
        config: RetrievalConfig | None = None,
    ) -> None:
        self._embedder = embedder
        self._config = config or RetrievalConfig()

    async def search(
        self,
        *,
        query: str,
        top_k: int,
        session: AsyncSession,
    ) -> list[FAQContextItem]:
        if not query.strip():
            return []

        [embedding] = await self._embedder.embed([query], input_type="query")

        # pgvector's cosine_distance = 1 - cosine_similarity, so similarity = 1 - distance.
        # Range: [-1, 1] for arbitrary vectors; [0, 2] only when both are unit-norm and
        # always non-negative. Voyage-3 returns L2-normalized vectors, so distance in
        # [0, 2] and similarity in [-1, 1].
        distance = FAQChunk.embedding.cosine_distance(embedding)
        stmt = select(FAQChunk, distance.label("distance")).order_by(distance).limit(top_k)
        result = await session.execute(stmt)
        rows = result.all()

        items: list[FAQContextItem] = []
        for chunk, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity < self._config.similarity_floor:
                continue
            items.append(FAQContextItem(chunk_id=chunk.id, text=chunk.text, score=similarity))

        log.debug(
            "faq_retrieved",
            query_len=len(query),
            candidates=len(rows),
            kept=len(items),
            top_k=top_k,
        )
        return items
