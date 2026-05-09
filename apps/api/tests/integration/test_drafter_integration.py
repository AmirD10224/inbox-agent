"""Integration test 2/4: draft endpoint with FAQ retrieval mocked."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient, Response

from inbox_agent.api.deps import get_retriever
from inbox_agent.faq.retrieve import FAQContextItem, FAQRetriever
from inbox_agent.main import create_app
from tests.conftest import load_fixture

if TYPE_CHECKING:
    import respx

pytestmark = pytest.mark.integration


class _StubRetriever(FAQRetriever):
    def __init__(self, items: list[FAQContextItem]) -> None:
        self._items = items

    async def search(self, *, query: str, top_k: int, session: object) -> list[FAQContextItem]:
        return self._items[:top_k]


@pytest.mark.asyncio
async def test_draft_with_faq_context_includes_citations(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/v1/messages").mock(
        return_value=Response(200, json=load_fixture("draft_billing_with_citation"))
    )
    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever(
        [
            FAQContextItem(
                chunk_id="chunk-billing-invoices-1",
                text="Customers can download itemized invoices from Account → Billing → Invoices.",
                score=0.91,
            )
        ]
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/draft",
            json={
                "ticket": "Where can I get my invoice?",
                "classification": "billing",
                "confidence": 0.96,
                "use_faq": True,
                "faq_top_k": 3,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "invoice" in body["response"].lower()
    assert body["faq_chunks_used"] == ["chunk-billing-invoices-1"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["faq_id"] == "chunk-billing-invoices-1"
    assert body["tone"] == "informative"


@pytest.mark.asyncio
async def test_draft_without_faq_context_has_empty_citations(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/v1/messages").mock(
        return_value=Response(200, json=load_fixture("draft_no_faq"))
    )
    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever([])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/draft",
            json={
                "ticket": "I think the app crashed but I'm not sure",
                "classification": "technical",
                "confidence": 0.6,
                "use_faq": False,
                "faq_top_k": 3,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"] == []
    assert body["faq_chunks_used"] == []
