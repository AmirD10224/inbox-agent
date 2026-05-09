"""Langfuse tracing wrapper.

Designed so the rest of the code doesn't care whether Langfuse is configured.
When keys are missing, the tracer is a no-op and `trace_id` is a local UUID
that still appears in logs and the `traces` table. Langfuse outages or
unconfigured environments do not block the demo.
"""

from __future__ import annotations

import contextlib
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from inbox_agent.config import get_settings
from inbox_agent.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

log = get_logger(__name__)

Langfuse: Any = None
with contextlib.suppress(ImportError):
    from langfuse import Langfuse  # type: ignore[no-redef,unused-ignore]


_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.langfuse_enabled or Langfuse is None:
        return None
    assert settings.langfuse_public_key is not None
    assert settings.langfuse_secret_key is not None
    _client = Langfuse(
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    return _client


@contextmanager
def trace_generation(
    *,
    name: str,
    model: str,
    input_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Iterator[TraceHandle]:
    """Context manager around an LLM call.

    Yields a `TraceHandle` the caller updates with output, usage, cost. On
    exit, flushes the span to Langfuse if configured. The trace ID is always
    available, even without Langfuse.
    """
    trace_id = str(uuid.uuid4())
    handle = TraceHandle(trace_id=trace_id, name=name, model=model)
    client = _get_client()
    span: Any = None
    if client is not None:
        try:
            span = client.generation(
                name=name,
                model=model,
                input=input_payload,
                metadata=metadata or {},
            )
            handle._set_remote_id(span.id)
        except Exception as e:  # pragma: no cover. Langfuse outage tolerated.
            log.warning("langfuse_span_create_failed", error=str(e))
            span = None
    try:
        yield handle
    finally:
        if span is not None:
            try:
                span.end(
                    output=handle.output,
                    usage_details={
                        "input": handle.input_tokens,
                        "output": handle.output_tokens,
                        "total": handle.input_tokens + handle.output_tokens,
                    },
                    cost_details={"total": handle.cost_usd},
                    metadata={**(metadata or {}), "trace_id": trace_id, **handle.extra_metadata},
                )
                client.flush()
            except Exception as e:  # pragma: no cover
                log.warning("langfuse_span_end_failed", error=str(e))


class TraceHandle:
    """Mutable record updated by the LLM client during a call."""

    __slots__ = (
        "_remote_id",
        "cost_usd",
        "extra_metadata",
        "input_tokens",
        "model",
        "name",
        "output",
        "output_tokens",
        "trace_id",
    )

    def __init__(self, *, trace_id: str, name: str, model: str) -> None:
        self.trace_id = trace_id
        self.name = name
        self.model = model
        self.output: dict[str, Any] | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cost_usd: float = 0.0
        self.extra_metadata: dict[str, Any] = {}
        self._remote_id: str | None = None

    def _set_remote_id(self, remote_id: str) -> None:
        self._remote_id = remote_id

    @property
    def langfuse_url(self) -> str | None:
        if self._remote_id is None:
            return None
        settings = get_settings()
        return f"{settings.langfuse_host}/trace/{self._remote_id}"
