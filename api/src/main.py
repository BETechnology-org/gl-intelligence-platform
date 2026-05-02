"""FastAPI entrypoint for the BL/GL Intelligence platform."""

from __future__ import annotations

import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routes import cortex, dise, health, sessions, tax

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 70)
    log.info("BL/GL Intelligence API starting (env=%s, version=%s)",
             settings.environment, settings.app_version)
    log.info("CORS: %s", settings.cors_origins)
    log.info("Rate limit: %d/min", settings.rate_limit_per_minute)
    log.info("BQ data project: %s.%s", settings.bq_data_project, settings.bq_dataset)
    log.info("Supabase URL: %s", settings.supabase_url)
    log.info("Claude model: %s (Bedrock=%s)", settings.claude_model, settings.use_bedrock)
    log.info("=" * 70)

    yield

    log.info("BL/GL Intelligence API shutting down")
    # Graceful session shutdown (when SessionService lands)
    try:
        from .services.session_service import session_service
        await session_service.shutdown_all()
    except ImportError:
        pass


app = FastAPI(
    title="BL/GL Intelligence API",
    version=settings.app_version,
    description="FASB ASU compliance platform — DISE (ASU 2024-03) + Income Tax (ASU 2023-09)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)


# ── Request lifecycle: request-id + structured logging ────────────────
@app.middleware("http")
async def request_lifecycle(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    request.state.request_id = request_id
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = int((time.monotonic() - start) * 1000)
        log.exception("unhandled rid=%s path=%s elapsed=%dms", request_id, request.url.path, elapsed)
        raise

    elapsed = int((time.monotonic() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    log.info(
        "req rid=%s %s %s -> %d in %dms",
        request_id, request.method, request.url.path, response.status_code, elapsed,
    )
    return response


# ── Error handlers ─────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    log.warning("validation rid=%s path=%s errors=%s",
                getattr(request.state, "request_id", "-"), request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "details": exc.errors(),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("unhandled rid=%s path=%s",
                  getattr(request.state, "request_id", "-"), request.url.path)
    msg = "Internal server error" if settings.is_prod else f"{type(exc).__name__}: {exc}"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": msg,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ── Routers ────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["health"])
app.include_router(cortex.router, prefix="/api/cortex", tags=["cortex"])
app.include_router(dise.router, prefix="/api/dise", tags=["dise"])
app.include_router(tax.router, prefix="/api/tax", tags=["tax"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])


@app.get("/")
async def root() -> dict:
    return {
        "service": "BL/GL Intelligence API",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
    }


if __name__ == "__main__":
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, log_level=settings.log_level.lower())
