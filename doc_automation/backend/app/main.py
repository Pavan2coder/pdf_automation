"""
app/main.py
───────────
FastAPI application entry point.

Start with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.api.routes import upload, process, download

log = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Application factory
# ──────────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title       = settings.APP_NAME,
        version     = settings.APP_VERSION,
        description = (
            "Production-ready AI Document Automation Platform. "
            "Upload project documents + PDF templates → AI extracts content "
            "→ templates are edited in-place → download generated PDFs."
        ),
        docs_url    = "/docs",
        redoc_url   = "/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins     = settings.CORS_ORIGINS,
        allow_credentials = True,
        allow_methods     = ["*"],
        allow_headers     = ["*"],
    )

    # ── Request timing middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def _add_timing(request: Request, call_next):
        t0  = time.perf_counter()
        res = await call_next(request)
        ms  = (time.perf_counter() - t0) * 1000
        res.headers["X-Process-Time-Ms"] = f"{ms:.1f}"
        log.debug("%s %s → %d (%.1f ms)", request.method, request.url.path, res.status_code, ms)
        return res

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {exc}"},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    prefix = "/api"
    app.include_router(upload.router,   prefix=prefix)
    app.include_router(process.router,  prefix=prefix)
    app.include_router(download.router, prefix=prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health():
        return {
            "status":  "ok",
            "version": settings.APP_VERSION,
            "ai":      settings.AI_PROVIDER,
        }

    log.info("✅  %s v%s started | AI=%s | DEBUG=%s",
             settings.APP_NAME, settings.APP_VERSION,
             settings.AI_PROVIDER, settings.DEBUG)
    return app


app = create_app()
