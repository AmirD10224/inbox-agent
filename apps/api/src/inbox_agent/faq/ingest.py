"""FAQ ingestion pipeline: URL → text → chunks → embeddings → DB."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import trafilatura

from inbox_agent.db.models import FAQChunk, FAQDocument
from inbox_agent.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from inbox_agent.faq.embed import EmbeddingClient

log = get_logger(__name__)

CHUNK_TARGET_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 50
# 4 chars/token heuristic, see llm.cost.count_tokens_estimate.
_CHARS_PER_TOKEN = 4
_MAX_FETCH_BYTES = 5 * 1024 * 1024  # 5MB safety cap.
_FETCH_TIMEOUT_S = 15.0


@dataclass(frozen=True, slots=True)
class IngestResult:
    document_id: str
    source_url: str
    title: str | None
    chunks_inserted: int


class FAQIngestor:
    def __init__(self, *, embedder: EmbeddingClient, http: httpx.AsyncClient | None = None) -> None:
        self._embedder = embedder
        self._http = http or httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT_S,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=4),
            headers={"User-Agent": "InboxAgent/0.1 (+https://github.com/amirdhibi/inbox-agent)"},
        )

    async def ingest(self, *, url: str, session: AsyncSession) -> IngestResult:
        html = await self._fetch(url)
        title, text = _extract(html, url)
        if not text:
            msg = f"Could not extract text from {url}"
            raise ValueError(msg)

        chunks = _chunk(
            text, target_tokens=CHUNK_TARGET_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS
        )
        if not chunks:
            msg = f"No usable chunks produced from {url}"
            raise ValueError(msg)

        embeddings = await self._embedder.embed(chunks, input_type="document")

        doc_id = str(uuid.uuid4())
        document = FAQDocument(id=doc_id, source_url=url, title=title)
        session.add(document)
        await session.flush()

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            session.add(
                FAQChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    chunk_index=idx,
                    text=chunk_text,
                    question=None,
                    embedding=embedding,
                    metadata_={"source_url": url},
                )
            )
        await session.flush()

        log.info("faq_ingested", url=url, chunks=len(chunks), document_id=doc_id)
        return IngestResult(
            document_id=doc_id,
            source_url=url,
            title=title,
            chunks_inserted=len(chunks),
        )

    async def _fetch(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            msg = "Only http(s) URLs are supported"
            raise ValueError(msg)
        resp = await self._http.get(url)
        resp.raise_for_status()
        body = resp.content
        if len(body) > _MAX_FETCH_BYTES:
            msg = f"Response too large: {len(body)} bytes"
            raise ValueError(msg)
        return body.decode(resp.encoding or "utf-8", errors="replace")


def _extract(html: str, url: str) -> tuple[str | None, str]:
    """Best-effort title + main text extraction."""
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    if not extracted:
        return None, ""

    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else None
    if title is not None:
        title = re.sub(r"\s+", " ", title)[:512]

    return title, extracted.strip()


_MIN_CHUNK_CHARS = 50


def _chunk(text: str, *, target_tokens: int, overlap_tokens: int) -> list[str]:
    """Paragraph-aware chunker.

    - Joins paragraphs until ~target_tokens, then opens a new chunk preserving
      an overlap window so context isn't sliced mid-sentence.
    - When a single paragraph already exceeds the target, hard-splits it on
      target_chars boundaries (no infinite-mega-chunk failure mode).
    - Drops scraps shorter than `_MIN_CHUNK_CHARS` ONLY when there are 2+
      chunks; a tiny single-chunk doc still ingests rather than silently
      vanishing.
    """
    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    # Pre-pass: hard-split any paragraph that's already larger than target_chars
    # so the joining loop never sees an oversize unit.
    expanded: list[str] = []
    for para in paragraphs:
        if len(para) <= target_chars:
            expanded.append(para)
            continue
        for start in range(0, len(para), target_chars - overlap_chars):
            piece = para[start : start + target_chars]
            if piece:
                expanded.append(piece)

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in expanded:
        if current_len + len(para) > target_chars and current:
            chunks.append("\n\n".join(current))
            tail = "\n\n".join(current)[-overlap_chars:]
            current = [tail, para] if tail else [para]
            current_len = sum(len(c) for c in current)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    if len(chunks) <= 1:
        # Tiny single-chunk docs are valid input; don't silently drop them.
        return chunks
    return [c for c in chunks if len(c) >= _MIN_CHUNK_CHARS]
