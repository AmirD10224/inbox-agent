"""Integration test 4/4: full /run end-to-end with persisted Trace.

This is the headline test, exercises classifier → drafter → escalator,
persists a Trace row, then reads it back via /traces and checks aggregates.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from inbox_agent.api.deps import get_db_session, get_retriever
from inbox_agent.faq.retrieve import FAQContextItem, FAQRetriever
from inbox_agent.main import create_app
from tests.conftest import load_fixture

if TYPE_CHECKING:
    import respx

pytestmark = pytest.mark.integration


class _StubRetriever(FAQRetriever):
    def __init__(self) -> None:
        pass

    async def search(self, *, query: str, top_k: int, session: object) -> list[FAQContextItem]:
        return [
            FAQContextItem(
                chunk_id="chunk-billing-invoices-1",
                text="Customers can download itemized invoices from Account → Billing → Invoices.",
                score=0.91,
            )
        ]


@pytest.mark.asyncio
async def test_full_run_persists_trace_and_aggregates(
    respx_mock: respx.MockRouter, db_session: AsyncSession
) -> None:
    # Three sequential calls in the orchestrator: classify, draft, escalate.
    classify_fx = load_fixture("classify_billing_high_conf")
    draft_fx = load_fixture("draft_billing_with_citation")
    escalate_fx = load_fixture("escalate_no_high_conf")
    responses = iter(
        [
            Response(200, json=classify_fx),
            Response(200, json=draft_fx),
            Response(200, json=escalate_fx),
        ]
    )
    respx_mock.post("/v1/messages").mock(side_effect=lambda _request: next(responses))

    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()

    # Share one session across the request so /traces sees the persisted row.
    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield db_session
        await db_session.commit()

    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_resp = await client.post(
            "/run",
            json={
                "ticket": "Why was I charged $19 last month? Send me an invoice.",
                "use_faq": True,
                "faq_top_k": 3,
            },
        )
        assert run_resp.status_code == 200, run_resp.text
        run = run_resp.json()

        # Aggregates match the sum of fixture usages.
        expected_in = (
            classify_fx["usage"]["input_tokens"]
            + draft_fx["usage"]["input_tokens"]
            + escalate_fx["usage"]["input_tokens"]
        )
        expected_out = (
            classify_fx["usage"]["output_tokens"]
            + draft_fx["usage"]["output_tokens"]
            + escalate_fx["usage"]["output_tokens"]
        )
        assert run["total_input_tokens"] == expected_in
        assert run["total_output_tokens"] == expected_out
        assert run["total_cost_usd"] > 0
        assert run["classification"]["category"] == "billing"
        assert run["draft"]["citations"][0]["faq_id"] == "chunk-billing-invoices-1"
        assert run["escalation"]["escalate"] is False

        # /traces sees the persisted row.
        traces_resp = await client.get("/traces")
        assert traces_resp.status_code == 200
        traces = traces_resp.json()
        assert traces["count"] == 1
        row = traces["traces"][0]
        assert row["classification"] == "billing"
        assert row["escalated"] is False
        assert len(row["llm_calls"]) == 3
        assert {c["stage"] for c in row["llm_calls"]} == {"classify", "draft", "escalate"}
