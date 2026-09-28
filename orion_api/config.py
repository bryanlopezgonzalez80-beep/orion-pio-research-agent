from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:8501",
)


@dataclass(frozen=True)
class APISettings:
    allowed_origins: tuple[str, ...]
    api_key: str | None


def get_settings(environ: dict[str, str] | None = None) -> APISettings:
    env = os.environ if environ is None else environ
    raw_origins = (env.get("ORION_ALLOWED_ORIGINS") or "").strip()
    origins = (
        tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        if raw_origins
        else DEFAULT_ALLOWED_ORIGINS
    )
    if "*" in origins:
        raise ValueError("ORION_ALLOWED_ORIGINS must list explicit origins")
    api_key = (env.get("ORION_API_KEY") or "").strip() or None
    return APISettings(allowed_origins=origins, api_key=api_key)
