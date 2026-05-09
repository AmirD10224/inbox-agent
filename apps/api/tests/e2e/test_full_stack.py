"""End-to-end stack test.

Boots the full compose stack (Postgres-with-pgvector + the API container) and
exercises the live HTTP surface, including a real `POST /run` against the
container, with the Anthropic SDK redirected to a local mock server bound on
the host. No real API credits burned, no real keys needed in CI.

Slow (~30s cold). Marked `e2e` so it's only run via `make test-e2e`.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "compose.yml"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "responses"
HEALTH_URL = "http://localhost:8000/health"
RUN_URL = "http://localhost:8000/run"
TRACES_URL = "http://localhost:8000/traces"


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _wait_for(url: str, timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as e:  # pragma: no cover
            last_err = e
        time.sleep(1.0)
    msg = f"Timed out waiting for {url}: {last_err}"
    raise TimeoutError(msg)


def _free_port() -> int:
    # Intentionally bind to all interfaces, the docker-compose container
    # connects to this server via host.docker.internal, which on Linux maps
    # to the host gateway, not 127.0.0.1.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))  # noqa: S104
        return int(s.getsockname()[1])


def _load_fixture(name: str) -> dict[str, object]:
    data: object = json.loads((FIXTURES_DIR / f"{name}.json").read_text())
    if not isinstance(data, dict):
        raise TypeError(f"fixture {name!r} did not parse as dict, got {type(data).__name__}")
    return data


class _AnthropicMockHandler(BaseHTTPRequestHandler):
    """Replays our recorded Anthropic responses in classify/draft/escalate order.

    The SDK sends `tool_choice.name` in the request body, we use it to pick
    the right fixture so order-of-arrival doesn't matter.
    """

    fixture_map: ClassVar[dict[str, str]] = {
        "record_classification": "classify_billing_high_conf",
        "record_draft": "draft_billing_with_citation",
        "record_escalation_decision": "escalate_no_high_conf",
    }

    def log_message(self, format: str, *args: object) -> None:
        # Quiet the default stdout spam.
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        tool_name = payload.get("tool_choice", {}).get("name", "")
        fixture_name = self.fixture_map.get(tool_name, "classify_billing_high_conf")
        try:
            response = _load_fixture(fixture_name)
        except FileNotFoundError:
            self.send_response(500)
            self.end_headers()
            return
        body_bytes = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


@pytest.fixture(scope="module")
def mock_anthropic_server() -> Iterator[int]:
    """Spin up a local mock Anthropic server on a free port for the lifetime of the module."""
    port = _free_port()
    server = HTTPServer(("0.0.0.0", port), _AnthropicMockHandler)  # noqa: S104
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def compose_stack(mock_anthropic_server: int) -> Iterator[None]:
    if not _docker_available():
        pytest.skip("docker not available, skipping e2e")
    if not COMPOSE_FILE.exists():
        pytest.skip(f"compose file not found at {COMPOSE_FILE}")

    # Point the in-container Anthropic SDK at our host-side mock.
    # `host.docker.internal` is added via compose.yml `extra_hosts` so it
    # resolves on Linux CI as well as Docker Desktop.
    env = {
        **os.environ,
        "APP_ENV": "test",
        "LOG_LEVEL": "WARNING",
        "ANTHROPIC_BASE_URL": f"http://host.docker.internal:{mock_anthropic_server}",
        "ANTHROPIC_API_KEY": "sk-ant-e2e-mock-not-real",
    }
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build"],
        check=True,
        env=env,
    )
    try:
        _wait_for(HEALTH_URL)
        yield
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            check=False,
        )


def test_health_endpoint_reports_db_ok(compose_stack: None) -> None:
    r = httpx.get(HEALTH_URL, timeout=5.0)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["version"]


def test_run_endpoint_executes_full_agent_flow_against_live_stack(
    compose_stack: None,
) -> None:
    """POST /run end-to-end through the compose stack with mocked Anthropic.

    Verifies the entire byte-path: HTTP → FastAPI → Orchestrator → LLMClient →
    httpx → mock server → response → DB persistence → /traces readback.
    """
    payload = {
        "ticket": "Why was I charged $19? Please send the invoice.",
        "use_faq": False,
        "faq_top_k": 3,
    }
    r = httpx.post(RUN_URL, json=payload, timeout=30.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classification"]["category"] == "billing"
    assert body["draft"]["response"]
    assert body["escalation"]["escalate"] is False
    assert body["total_cost_usd"] > 0

    # Trace was persisted; /traces returns it.
    traces = httpx.get(TRACES_URL, timeout=5.0).json()
    assert traces["count"] >= 1
    row = next(t for t in traces["traces"] if t["id"] == body["trace_id"])
    assert row["classification"] == "billing"
    assert len(row["llm_calls"]) == 3
