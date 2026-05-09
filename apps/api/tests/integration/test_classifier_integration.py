"""Integration test 1/4: classify endpoint behavior with respx-mocked LLM."""

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
async def test_classify_high_confidence_billing(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/v1/messages").mock(
        return_value=Response(200, json=load_fixture("classify_billing_high_conf"))
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/classify",
            json={"ticket": "Why was I charged $19 last month? Please send an itemized invoice."},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "billing"
    assert body["confidence"] >= 0.9
    assert len(body["rationale"]) >= 10
    assert body["call"]["model"] == "claude-sonnet-4-6"
    assert body["call"]["input_tokens"] == 412
    assert body["call"]["output_tokens"] == 78
    # Cost = 412 * 3/1M + 78 * 15/1M = 0.001236 + 0.00117 = 0.002406
    assert body["call"]["cost_usd"] == pytest.approx(0.002406, rel=1e-3)


@pytest.mark.asyncio
async def test_classify_repairs_invalid_then_succeeds(respx_mock: respx.MockRouter) -> None:
    """Validation failure on attempt 1 → repair retry → success on attempt 2."""
    invalid = load_fixture("classify_invalid_then_repaired")
    valid = load_fixture("classify_billing_high_conf")
    responses = iter([Response(200, json=invalid), Response(200, json=valid)])
    respx_mock.post("/v1/messages").mock(side_effect=lambda _request: next(responses))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/classify", json={"ticket": "Refund please"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "billing"
    assert body["call"]["repair_attempts"] == 1


@pytest.mark.asyncio
async def test_classify_rejects_empty_ticket() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/classify", json={"ticket": ""})
    assert resp.status_code == 422
