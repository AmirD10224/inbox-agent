"""FastAPI app entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from inbox_agent import __version__
from inbox_agent.api import router
from inbox_agent.config import get_settings
from inbox_agent.db.session import get_engine
from inbox_agent.logging import configure_logging, get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger(__name__)
    settings = get_settings()
    log.info(
        "app_startup",
        env=settings.app_env,
        langfuse_enabled=settings.langfuse_enabled,
        primary_model=settings.anthropic_model_primary,
    )
    yield
    engine = get_engine()
    await engine.dispose()
    log.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="InboxAgent",
        version=__version__,
        description=(
            "AI customer support agent with classify / draft / escalate-decision endpoints, "
            "FAQ retrieval, full LLM tracing, cost accounting, and an evals harness."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
