from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.config import DatabaseConfigurationError
from database.connection import DatabaseConnectionError

from .config import APISettings, get_settings
from .errors import ExternalRateLimit, ExternalSearchError, ExternalSearchTimeout
from .routes import health, library, papers, search, sources


def create_app(settings: APISettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(
        title="Orion PIO Intelligence API",
        version="v1",
        description="Secure API over Orion's research and persistence services.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type", "X-API-Key"],
    )

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
    versioned.include_router(papers.router)
    versioned.include_router(search.router)
    versioned.include_router(sources.router)
    versioned.include_router(library.router)
    application.include_router(versioned, prefix="/api/v1")
    return application


app = create_app()
