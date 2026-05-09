"""Modal deployment entrypoint.

Two functions:

    modal run modal_app.py::migrate     # one-shot, run BEFORE deploy
    modal deploy modal_app.py           # publishes the API

We do NOT run migrations on every cold start because Modal can boot multiple
containers concurrently under load, racing migrations either deadlock on the
alembic version row or fail one container outright. Run migrations once
ahead of deploy; the API can then scale freely.

Required Modal secrets:
- inbox-agent-anthropic   (ANTHROPIC_API_KEY)
- inbox-agent-voyage      (VOYAGE_API_KEY)
- inbox-agent-langfuse    (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST)
- inbox-agent-db          (DATABASE_URL. managed Postgres + pgvector)
"""

from __future__ import annotations

import modal

app_name = "inbox-agent"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libpq-dev", "build-essential")
    .pip_install_from_pyproject("pyproject.toml")
    .add_local_dir("src", "/app/src")
    .add_local_dir("prompts", "/app/prompts")
    .add_local_dir("alembic", "/app/alembic")
    .add_local_file("alembic.ini", "/app/alembic.ini")
    .workdir("/app")
    .env({"PYTHONPATH": "/app/src"})
)

modal_app = modal.App(name=app_name, image=image)

secrets = [
    modal.Secret.from_name("inbox-agent-anthropic"),
    modal.Secret.from_name("inbox-agent-voyage"),
    modal.Secret.from_name("inbox-agent-langfuse"),
    modal.Secret.from_name("inbox-agent-db"),
]


@modal_app.function(secrets=secrets, timeout=300)
def migrate() -> None:
    """One-shot migration runner. Invoke before `modal deploy`."""
    import subprocess
    import sys

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, file=sys.stderr)
    if result.returncode:
        msg = f"alembic upgrade failed (exit {result.returncode}): {result.stderr}"
        raise RuntimeError(msg)


@modal_app.function(
    secrets=secrets,
    min_containers=0,
    max_containers=4,
    timeout=120,
)
@modal.asgi_app()
def fastapi_app() -> object:
    # No subprocess work here, migrations are a one-shot deploy step
    # (`modal run modal_app.py::migrate`), not a per-cold-start race.
    from inbox_agent.main import app

    return app
