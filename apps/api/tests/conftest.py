"""Test fixtures.

Strategy: respx mocks the Anthropic HTTP endpoint with payloads recorded in
`tests/fixtures/responses/`. CI runs with no real API keys.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import pytest_asyncio
import respx
from httpx import Response

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

# Make the repo-root `evals/` package importable from the apps/api test tree.
# `evals` lives at <repo>/evals, two parents above this conftest's dir.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Force test config before any inbox_agent imports.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("VOYAGE_API_KEY", "test-key-not-real")
# Use SQLite for unit tests that don't need pgvector. Integration tests that
# touch the DB use a per-test override.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "responses"


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture
def messages_endpoint() -> str:
    return "https://api.anthropic.com/v1/messages"


@pytest.fixture
def respx_mock() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, base_url="https://api.anthropic.com") as router:
        yield router


@pytest.fixture
def mock_classify_ok(respx_mock: respx.MockRouter) -> respx.MockRouter:
    fixture = load_fixture("classify_billing_high_conf")
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=fixture))
    return respx_mock


@pytest.fixture
def mock_draft_ok(respx_mock: respx.MockRouter) -> respx.MockRouter:
    fixture = load_fixture("draft_billing_with_citation")
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=fixture))
    return respx_mock


@pytest.fixture
def mock_escalate_no(respx_mock: respx.MockRouter) -> respx.MockRouter:
    fixture = load_fixture("escalate_no_high_conf")
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=fixture))
    return respx_mock


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[Any]:
    """In-memory sqlite session for tests that need to persist Trace rows.

    We only create the Trace table, pgvector-backed FAQ tables aren't usable
    on sqlite. Tests that exercise retrieval mock at the FAQRetriever layer.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from inbox_agent.db.models import Trace

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Trace.__table__ is a Table at runtime (with .create), but mypy sees
        # the broader FromClause via the declarative attribute. Cast to keep
        # the strict-mode check honest.
        from sqlalchemy import Table

        trace_table = cast(Table, Trace.__table__)
        await conn.run_sync(trace_table.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
