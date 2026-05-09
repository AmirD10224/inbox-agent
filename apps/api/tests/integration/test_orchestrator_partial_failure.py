"""Orchestrator must persist a partial Trace when a stage fails.

The dashboard sells "one canonical record per ticket", that promise breaks
if failed runs are invisible. This tests covers:

- classify succeeds → draft fails → partial Trace recorded with classification
  set, draft/escalate empty, operation="full_run_failed".
- classify fails on the first call → partial Trace with everything null,
  operation="full_run_failed".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inbox_agent.api.deps import get_db_session, get_retriever
from inbox_agent.db.models import Trace
from inbox_agent.faq.retrieve import FAQContextItem, FAQRetriever
from inbox_agent.main import create_app
from tests.conftest import load_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration


class _StubRetriever(FAQRetriever):
    def __init__(self) -> None:
        pass

    async def search(
        self,
        *,
        query: str,
        top_k: int,
        session: object,
    ) -> list[FAQContextItem]:
        return []


@pytest.mark.asyncio
async def test_partial_trace_persists_when_draft_fails(
    respx_mock: respx.MockRouter, db_session: AsyncSession
) -> None:
    """classify ok → draft returns invalid payload twice → 502 + partial Trace."""
    classify_fx = load_fixture("classify_billing_high_conf")
    invalid = load_fixture("classify_invalid_then_repaired")  # invalid for any schema
    responses = iter(
        [
            Response(200, json=classify_fx),
            Response(200, json=invalid),  # 1st draft attempt, validation fails
            Response(200, json=invalid),  # 2nd draft attempt, validation fails again → giveup
        ]
    )
    respx_mock.post("/v1/messages").mock(side_effect=lambda _r: next(responses))

    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield db_session
        await db_session.commit()

    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_resp = await client.post(
            "/run",
            json={"ticket": "Need invoice please", "use_faq": False, "faq_top_k": 3},
        )
        assert run_resp.status_code == 502, run_resp.text

        traces_resp = await client.get("/traces")
        assert traces_resp.status_code == 200
        traces = traces_resp.json()
        assert traces["count"] == 1
        row = traces["traces"][0]
        assert row["operation"] == "full_run_failed"
        # Classification stage completed; downstream did not.
        assert row["classification"] == "billing"
        assert row["confidence"] is not None
        assert row["drafted_response"] is None
        assert row["escalated"] is None
        assert row["suggested_team"] is None
        # Wire response only includes real per-call summaries (the error
        # marker is filtered out by /traces). Classify completed → present.
        stages = [c["stage"] for c in row["llm_calls"]]
        assert stages == ["classify"]

    # Direct DB read confirms the error marker was persisted (auditable).
    result = await db_session.execute(select(Trace))
    rows = result.scalars().all()
    assert len(rows) == 1
    persisted_stages = [c.get("stage") for c in rows[0].llm_calls]
    assert "error" in persisted_stages


@pytest.mark.asyncio
async def test_partial_trace_when_classify_itself_fails(
    respx_mock: respx.MockRouter, db_session: AsyncSession
) -> None:
    """classify validation fails twice on the first stage → partial Trace with all-null."""
    invalid = load_fixture("classify_invalid_then_repaired")
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=invalid))

    app = create_app()
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield db_session
        await db_session.commit()

    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_resp = await client.post(
            "/run",
            json={"ticket": "x", "use_faq": False, "faq_top_k": 3},
        )
        assert run_resp.status_code == 502

        # Direct DB query, the trace row exists with everything null.
        result = await db_session.execute(select(Trace))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].operation == "full_run_failed"
        assert rows[0].classification is None
        assert rows[0].drafted_response is None
