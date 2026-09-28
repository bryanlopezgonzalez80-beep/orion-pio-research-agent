from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:8501",
)
MIN_PRODUCTION_API_KEY_LENGTH = 32


class APIConfigurationError(ValueError):
    """Sanitized API configuration failure safe for startup output."""


@dataclass(frozen=True)
class APISettings:
    allowed_origins: tuple[str, ...]
    api_key: str | None
    environment: str = "development"


def _validate_origins(origins: tuple[str, ...], *, production: bool) -> None:
    if any("*" in origin for origin in origins):
        raise APIConfigurationError(
            "ORION_ALLOWED_ORIGINS must list explicit origins"
        )
    for origin in origins:
        parsed = urlsplit(origin)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
        if not valid:
            raise APIConfigurationError("ORION_ALLOWED_ORIGINS contains an invalid origin")
        hostname = (parsed.hostname or "").casefold()
        local = hostname == "localhost" or hostname.endswith(".localhost") or hostname in {
            "127.0.0.1",
            "::1",
        }
        if production and (local or parsed.scheme != "https"):
            raise APIConfigurationError(
                "Production origins must use HTTPS and cannot use localhost"
            )


def validate_settings(settings: APISettings) -> APISettings:
    if settings.environment not in {"development", "production"}:
        raise APIConfigurationError("ORION_ENV must be development or production")
    production = settings.environment == "production"
    if production and settings.api_key is None:
        raise APIConfigurationError("ORION_API_KEY is required in production")
    if production and len(settings.api_key or "") < MIN_PRODUCTION_API_KEY_LENGTH:
        raise APIConfigurationError(
            "ORION_API_KEY must be at least 32 characters in production"
        )
    if production and not settings.allowed_origins:
        raise APIConfigurationError(
            "ORION_ALLOWED_ORIGINS is required in production"
        )
    _validate_origins(settings.allowed_origins, production=production)
    return settings


def get_settings(environ: dict[str, str] | None = None) -> APISettings:
    env = os.environ if environ is None else environ
    environment = (env.get("ORION_ENV") or "development").strip().casefold()
    if environment not in {"development", "production"}:
        raise APIConfigurationError(
            "ORION_ENV must be development or production"
        )
    production = environment == "production"
    raw_origins = (env.get("ORION_ALLOWED_ORIGINS") or "").strip()
    api_key = (env.get("ORION_API_KEY") or "").strip() or None
    if production and api_key is None:
        raise APIConfigurationError(
            "ORION_API_KEY is required in production"
        )
    if production and len(api_key or "") < MIN_PRODUCTION_API_KEY_LENGTH:
        raise APIConfigurationError(
            "ORION_API_KEY must be at least 32 characters in production"
        )
    if production and not raw_origins:
        raise APIConfigurationError(
            "ORION_ALLOWED_ORIGINS is required in production"
        )
    origins = (
        tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        if raw_origins
        else DEFAULT_ALLOWED_ORIGINS
    )
    return validate_settings(
        APISettings(
            allowed_origins=origins,
            api_key=api_key,
            environment=environment,
        )
    )
