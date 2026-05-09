"""Voyage embedding client wrapper.

Single-purpose wrapper so tests can swap in a deterministic fake client. The
real Voyage SDK is sync; we offload to a thread to keep the request loop free.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, Protocol

import voyageai

from inbox_agent.config import get_settings
from inbox_agent.logging import get_logger

log = get_logger(__name__)


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]: ...


class VoyageEmbeddingClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client: Any = voyageai.Client(api_key=api_key)
        self._model = model

    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        if not texts:
            return []
        # voyageai is sync, push to a thread.
        result = await asyncio.to_thread(
            self._client.embed,
            texts,
            model=self._model,
            input_type=input_type,
        )
        embeddings: list[list[float]] = result.embeddings
        log.debug("voyage_embed", n=len(texts), model=self._model, input_type=input_type)
        return embeddings


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    return VoyageEmbeddingClient(
        api_key=settings.voyage_api_key.get_secret_value(),
        model=settings.voyage_embed_model,
    )
