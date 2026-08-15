"""
FastAPI app factory.

create_app(db_path) exists as a factory (not a bare module-level `app`)
specifically so tests can spin up an isolated in-memory database per test
via create_app(":memory:") — no shared state leaking between tests, no
dependency-override gymnastics needed.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.storage.db import Database
from app.storage.repository import LogRepository

logger = logging.getLogger("swasthiq")


def _build_llm_client():
    """Returns an AnthropicLLMClient if ANTHROPIC_API_KEY is set, else
    None. None is a fully supported state — the narrative endpoint falls
    back to the deterministic template and reports
    grounding_status='fallback_no_llm_configured', it never errors."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — narrative endpoint will use the deterministic fallback template only.")
        return None
    from app.narrative.llm_client import AnthropicLLMClient
    return AnthropicLLMClient(api_key=api_key)


def create_app(db_path: str = "swasthiq.db") -> FastAPI:
    db = Database(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        db.close()

    app = FastAPI(title="SwasthiQ EOD Billing & Analytics Agent", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev-friendly; tighten before any real deployment
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.db = db
    app.state.repository = LogRepository(db)
    app.state.llm_client = _build_llm_client()

    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Safety net for truly unexpected errors (e.g. a DB failure).
        # Distinct from malformed-row handling, which never reaches here —
        # bad billing DATA is a normal response (422/201+errors), not an
        # exception. This handler is for genuine bugs/infra failures, and
        # deliberately does NOT leak the stack trace to the client.
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected error occurred and has been logged.",
            },
        )

    return app


# Default app instance for `uvicorn app.main:app`
app = create_app()