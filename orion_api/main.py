from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.config import DatabaseConfigurationError
from database.connection import DatabaseConnectionError

from .config import APISettings, get_settings, validate_settings
from .errors import ExternalRateLimit, ExternalSearchError, ExternalSearchTimeout
from .rate_limit import InMemoryRateLimiter, RateLimitCategory
from .routes import health, library, papers, radar, search, sources


def create_app(
    settings: APISettings | None = None,
    *,
    rate_limit_clock: Callable[[], float] | None = None,
) -> FastAPI:
    settings = validate_settings(settings) if settings is not None else get_settings()
    application = FastAPI(
        title="Orion PIO Intelligence API",
        version="v1",
        description="Secure API over Orion's research and persistence services.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    application.state.settings = settings
    rate_limits = {
        RateLimitCategory.READ: settings.rate_limit_read_per_minute,
        RateLimitCategory.WRITE: settings.rate_limit_write_per_minute,
        RateLimitCategory.SEARCH: settings.rate_limit_search_per_minute,
    }
    limiter_options = (
        {"clock": rate_limit_clock} if rate_limit_clock is not None else {}
    )
    application.state.rate_limiter = InMemoryRateLimiter(
        rate_limits, **limiter_options
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type", "X-Orion-API-Key"],
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @application.exception_handler(DatabaseConnectionError)
    @application.exception_handler(DatabaseConfigurationError)
    async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database unavailable"},
        )

    @application.exception_handler(ExternalSearchTimeout)
    async def timeout_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "External search timed out"},
        )

    @application.exception_handler(ExternalRateLimit)
    async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "External source rate limit reached"},
        )

    @application.exception_handler(ExternalSearchError)
    async def external_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "External search unavailable"},
        )

    @application.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal service failure"},
        )

    application.include_router(health.router)
    versioned = APIRouter()
    versioned.include_router(health.router)
    protected = APIRouter()
    protected.include_router(papers.router)
    protected.include_router(radar.router)
    protected.include_router(search.router)
    protected.include_router(sources.router)
    protected.include_router(library.router)
    versioned.include_router(protected)
    application.include_router(versioned, prefix="/api/v1")
    return application


app = create_app()
