"""Integration test 3/4: escalation endpoint, both branches."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient, Response

from inbox_agent.main import create_app
from tests.conftest import load_fixture

if TYPE_CHECKING:
    import respx

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_escalate_no_for_routine_ticket(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/v1/messages").mock(
        return_value=Response(200, json=load_fixture("escalate_no_high_conf"))
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/escalate-decision",
            json={
                "ticket": "Where can I get my invoice?",
                "classification": "billing",
                "confidence": 0.96,
                "drafted_response": "You can download invoices from Account > Billing.",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["escalate"] is False
    assert body["suggested_team"] == "none"


@pytest.mark.asyncio
async def test_escalate_yes_for_legal_signal(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/v1/messages").mock(
        return_value=Response(200, json=load_fixture("escalate_yes_legal"))
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/escalate-decision",
            json={
                "ticket": "I am about to file a GDPR complaint with my regulator.",
                "classification": "account",
                "confidence": 0.85,
                "drafted_response": "",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["escalate"] is True
    assert body["suggested_team"] == "trust_safety"
    assert "gdpr" in body["reasoning"].lower() or "regulator" in body["reasoning"].lower()
