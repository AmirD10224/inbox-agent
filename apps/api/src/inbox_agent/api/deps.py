"""FastAPI dependency providers.

A single LLMClient and embedding client live for the lifetime of the app and
are dependency-injected per request. Tests override these with respx-stubbed
or fake implementations.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends

from inbox_agent.agent import Classifier, Drafter, Escalator, Orchestrator, get_prompt_loader
from inbox_agent.db.session import get_session_factory
from inbox_agent.faq import FAQIngestor, FAQRetriever, get_embedding_client
from inbox_agent.llm.client import LLMClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from inbox_agent.faq.embed import EmbeddingClient


@lru_cache(maxsize=1)
def _llm_singleton() -> LLMClient:
    return LLMClient()


def get_llm_client() -> LLMClient:
    return _llm_singleton()


def get_embedder() -> EmbeddingClient:
    return get_embedding_client()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_classifier(llm: LLMClient = Depends(get_llm_client)) -> Classifier:
    return Classifier(llm=llm, prompts=get_prompt_loader())


def get_drafter(llm: LLMClient = Depends(get_llm_client)) -> Drafter:
    return Drafter(llm=llm, prompts=get_prompt_loader())


def get_escalator(llm: LLMClient = Depends(get_llm_client)) -> Escalator:
    return Escalator(llm=llm, prompts=get_prompt_loader())


def get_retriever(embedder: EmbeddingClient = Depends(get_embedder)) -> FAQRetriever:
    return FAQRetriever(embedder=embedder)


def get_ingestor(embedder: EmbeddingClient = Depends(get_embedder)) -> FAQIngestor:
    return FAQIngestor(embedder=embedder)


def get_orchestrator(
    classifier: Classifier = Depends(get_classifier),
    drafter: Drafter = Depends(get_drafter),
    escalator: Escalator = Depends(get_escalator),
    retriever: FAQRetriever = Depends(get_retriever),
) -> Orchestrator:
    return Orchestrator(
        classifier=classifier,
        drafter=drafter,
        escalator=escalator,
        retriever=retriever,
    )
