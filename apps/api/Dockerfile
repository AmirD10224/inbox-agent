# syntax=docker/dockerfile:1.7
# Multi-stage build: install deps in a builder, then copy site-packages into a
# clean runtime image, psycopg ships a binary wheel so the runtime image needs
# neither libpq-dev nor build-essential.

FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# Manifest first so the dependency layer caches across code edits.
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

# Now copy the source, code edits invalidate this layer only.
COPY src ./src
RUN uv pip install --system --no-cache --no-deps .


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Carry installed site-packages and console scripts from the builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY alembic.ini ./
COPY alembic ./alembic
COPY prompts ./prompts
COPY src ./src

# Drop privileges.
RUN useradd --create-home --shell /bin/bash --uid 1001 app \
 && chown -R app:app /app
USER app

EXPOSE 8000

# Use exec form so uvicorn becomes PID 1 and receives SIGTERM cleanly. We
# deliberately do NOT run alembic at every container start, migrations are
# a one-shot deploy step (see modal_app.py / Makefile target `migrate`).
CMD ["uvicorn", "inbox_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
