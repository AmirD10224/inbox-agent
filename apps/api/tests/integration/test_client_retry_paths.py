"""Coverage for the LLMClient retry, repair, and give-up paths.

These directly exercise `LLMClient.call_with_tool` rather than going through a
FastAPI route, because the branches under test (transient retry, validation
give-up) are LLM-client-internal.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from anthropic import AsyncAnthropic
from httpx import Response

from inbox_agent.config import get_settings
from inbox_agent.llm.client import LLMClient, LLMOutputError
from inbox_agent.llm.tool_schemas import CLASSIFY_TOOL, ClassifyOutput
from tests.conftest import load_fixture

pytestmark = pytest.mark.integration


def _make_client() -> LLMClient:
    """Build a real LLMClient pointed at the respx-mocked endpoint."""
    settings = get_settings()
    inner = AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=5.0,
        max_retries=0,
    )
    return LLMClient(anthropic=inner)


@pytest.mark.asyncio
async def test_retries_on_transient_503_then_succeeds(respx_mock: respx.MockRouter) -> None:
    """First call returns 503 (transient), second call returns valid payload."""
    valid = load_fixture("classify_billing_high_conf")
    responses: list[Response] = [
        Response(503, json={"type": "error", "error": {"type": "overloaded_error"}}),
        Response(200, json=valid),
    ]
    iterator = iter(responses)
    respx_mock.post("/v1/messages").mock(side_effect=lambda _request: next(iterator))

    client = _make_client()
    result = await client.call_with_tool(
        model="claude-sonnet-4-6",
        system="s",
        user="u",
        tool=CLASSIFY_TOOL,
        output_model=ClassifyOutput,
        operation="classify",
    )
    assert result.output.category == "billing"
    # No repair attempts (validation passed first try); the retry was at the transport layer.
    assert result.repair_attempts == 0


@pytest.mark.asyncio
async def test_gives_up_after_max_transient_retries(respx_mock: respx.MockRouter) -> None:
    """All attempts return 503 → final attempt re-raises the SDK error."""
    respx_mock.post("/v1/messages").mock(
        return_value=Response(503, json={"type": "error", "error": {"type": "overloaded_error"}})
    )

    client = _make_client()
    with pytest.raises(Exception) as exc:
        await client.call_with_tool(
            model="claude-sonnet-4-6",
            system="s",
            user="u",
            tool=CLASSIFY_TOOL,
            output_model=ClassifyOutput,
            operation="classify",
        )
    # anthropic SDK raises APIStatusError / OverloadedError; both are in _TRANSIENT.
    assert "503" in str(exc.value) or "overloaded" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_rate_limit_429_is_retried(respx_mock: respx.MockRouter) -> None:
    """429 RateLimitError counts as transient and is retried."""
    valid = load_fixture("classify_billing_high_conf")
    responses: list[Response] = [
        Response(429, json={"type": "error", "error": {"type": "rate_limit_error"}}),
        Response(200, json=valid),
    ]
    iterator = iter(responses)
    respx_mock.post("/v1/messages").mock(side_effect=lambda _request: next(iterator))

    client = _make_client()
    result = await client.call_with_tool(
        model="claude-sonnet-4-6",
        system="s",
        user="u",
        tool=CLASSIFY_TOOL,
        output_model=ClassifyOutput,
        operation="classify",
    )
    assert result.output.category == "billing"


@pytest.mark.asyncio
async def test_gives_up_after_two_validation_failures(respx_mock: respx.MockRouter) -> None:
    """Two consecutive invalid payloads → LLMOutputError after one repair attempt."""
    invalid = load_fixture("classify_invalid_then_repaired")
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=invalid))

    client = _make_client()
    with pytest.raises(LLMOutputError) as exc:
        await client.call_with_tool(
            model="claude-sonnet-4-6",
            system="s",
            user="u",
            tool=CLASSIFY_TOOL,
            output_model=ClassifyOutput,
            operation="classify",
        )
    assert "validation" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_extract_raises_when_response_has_no_tool_use(
    respx_mock: respx.MockRouter,
) -> None:
    """Model returns a text-only response (stop_reason='end_turn') → LLMOutputError."""
    text_only: dict[str, Any] = {
        "id": "msg_text_only",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-6",
        "content": [{"type": "text", "text": "I will not use the tool."}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=text_only))

    client = _make_client()
    with pytest.raises(LLMOutputError) as exc:
        await client.call_with_tool(
            model="claude-sonnet-4-6",
            system="s",
            user="u",
            tool=CLASSIFY_TOOL,
            output_model=ClassifyOutput,
            operation="classify",
        )
    assert "tool_use" in str(exc.value)


@pytest.mark.asyncio
async def test_max_retries_one_validation_error_raises_via_else_branch(
    respx_mock: respx.MockRouter,
) -> None:
    """With max_retries=1 and a single validation error, the for/else fires.

    This was previously dead-coded with a `pragma: no cover` comment; that
    pragma was wrong because max_retries=1 is a valid configuration.
    """
    invalid = load_fixture("classify_invalid_then_repaired")
    respx_mock.post("/v1/messages").mock(return_value=Response(200, json=invalid))

    client = _make_client()
    # Drop the retry budget to 1.
    client._max_retries = 1

    with pytest.raises(LLMOutputError) as exc:
        await client.call_with_tool(
            model="claude-sonnet-4-6",
            system="s",
            user="u",
            tool=CLASSIFY_TOOL,
            output_model=ClassifyOutput,
            operation="classify",
        )
    assert "validation" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_401_is_not_retried(respx_mock: respx.MockRouter) -> None:
    """Auth errors are config bugs, retrying them just delays the failure."""
    call_count = {"n": 0}

    def _side(_request: httpx.Request) -> Response:
        call_count["n"] += 1
        return Response(401, json={"type": "error", "error": {"type": "authentication_error"}})

    respx_mock.post("/v1/messages").mock(side_effect=_side)

    client = _make_client()
    with pytest.raises(Exception) as exc:
        await client.call_with_tool(
            model="claude-sonnet-4-6",
            system="s",
            user="u",
            tool=CLASSIFY_TOOL,
            output_model=ClassifyOutput,
            operation="classify",
        )
    assert "401" in str(exc.value) or "auth" in str(exc.value).lower()
    # Exactly ONE call, no retries on 401.
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_connection_error_is_retried(respx_mock: respx.MockRouter) -> None:
    """httpx connection error is a transient, retried, then succeeds."""
    valid = load_fixture("classify_billing_high_conf")
    seq: list[httpx.ConnectError | Response] = [
        httpx.ConnectError("boom"),
        Response(200, json=valid),
    ]
    it = iter(seq)

    def _side(request: httpx.Request) -> Response:
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item

    respx_mock.post("/v1/messages").mock(side_effect=_side)

    client = _make_client()
    result = await client.call_with_tool(
        model="claude-sonnet-4-6",
        system="s",
        user="u",
        tool=CLASSIFY_TOOL,
        output_model=ClassifyOutput,
        operation="classify",
    )
    assert result.output.category == "billing"
