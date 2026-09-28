from __future__ import annotations

import os
import hmac
from dataclasses import dataclass
from urllib.parse import urlsplit


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:8501",
)
MIN_PRODUCTION_API_KEY_LENGTH = 32
DEFAULT_RATE_LIMIT_SEARCH_PER_MINUTE = 20
DEFAULT_RATE_LIMIT_WRITE_PER_MINUTE = 60
DEFAULT_RATE_LIMIT_READ_PER_MINUTE = 120
MAX_RATE_LIMIT_PER_MINUTE = 10_000


class APIConfigurationError(ValueError):
    """Sanitized API configuration failure safe for startup output."""


@dataclass(frozen=True)
class APISettings:
    allowed_origins: tuple[str, ...]
    api_key: str | None
    environment: str = "development"
    api_key_secondary: str | None = None
    rate_limit_search_per_minute: int = DEFAULT_RATE_LIMIT_SEARCH_PER_MINUTE
    rate_limit_write_per_minute: int = DEFAULT_RATE_LIMIT_WRITE_PER_MINUTE
    rate_limit_read_per_minute: int = DEFAULT_RATE_LIMIT_READ_PER_MINUTE


def _parse_rate_limit(env: dict[str, str], name: str, default: int) -> int:
    raw_value = (env.get(name) or "").strip()
    if not raw_value:
        return default
    if not raw_value.isdecimal():
        raise APIConfigurationError(f"{name} must be a positive integer")
    value = int(raw_value)
    if not 1 <= value <= MAX_RATE_LIMIT_PER_MINUTE:
        raise APIConfigurationError(
            f"{name} must be between 1 and {MAX_RATE_LIMIT_PER_MINUTE}"
        )
    return value


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
    if settings.api_key_secondary is not None:
        if settings.api_key is None:
            raise APIConfigurationError(
                "ORION_API_KEY is required when ORION_API_KEY_SECONDARY is configured"
            )
        if len(settings.api_key_secondary) < MIN_PRODUCTION_API_KEY_LENGTH:
            raise APIConfigurationError(
                "ORION_API_KEY_SECONDARY must be at least 32 characters"
            )
        if hmac.compare_digest(
            settings.api_key_secondary.encode("utf-8"),
            settings.api_key.encode("utf-8"),
        ):
            raise APIConfigurationError(
                "ORION_API_KEY_SECONDARY must differ from ORION_API_KEY"
            )
    for name, value in (
        ("ORION_RATE_LIMIT_SEARCH_PER_MINUTE", settings.rate_limit_search_per_minute),
        ("ORION_RATE_LIMIT_WRITE_PER_MINUTE", settings.rate_limit_write_per_minute),
        ("ORION_RATE_LIMIT_READ_PER_MINUTE", settings.rate_limit_read_per_minute),
    ):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 1 <= value <= MAX_RATE_LIMIT_PER_MINUTE
        ):
            raise APIConfigurationError(
                f"{name} must be between 1 and {MAX_RATE_LIMIT_PER_MINUTE}"
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
    api_key_secondary = (env.get("ORION_API_KEY_SECONDARY") or "").strip() or None
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
            api_key_secondary=api_key_secondary,
            rate_limit_search_per_minute=_parse_rate_limit(
                env,
                "ORION_RATE_LIMIT_SEARCH_PER_MINUTE",
                DEFAULT_RATE_LIMIT_SEARCH_PER_MINUTE,
            ),
            rate_limit_write_per_minute=_parse_rate_limit(
                env,
                "ORION_RATE_LIMIT_WRITE_PER_MINUTE",
                DEFAULT_RATE_LIMIT_WRITE_PER_MINUTE,
            ),
            rate_limit_read_per_minute=_parse_rate_limit(
                env,
                "ORION_RATE_LIMIT_READ_PER_MINUTE",
                DEFAULT_RATE_LIMIT_READ_PER_MINUTE,
            ),
        )
    )
