from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class DatabaseConfigurationError(ValueError):
    """Raised for unsafe or unsupported database configuration."""


@dataclass(frozen=True)
class DatabaseConfig:
    engine: str
    sqlite_path: Path | None = None
    database_url: str | None = None


def get_database_config(
    sqlite_path: str | Path | None = None,
    *,
    environ: dict[str, str] | None = None,
    force_sqlite: bool = False,
) -> DatabaseConfig:
    env = os.environ if environ is None else environ
    database_url = (env.get("DATABASE_URL") or "").strip()
    if database_url and not force_sqlite:
        parsed = urlsplit(database_url)
        if parsed.scheme not in {"postgresql", "postgres"}:
            raise DatabaseConfigurationError(
                "DATABASE_URL must use the postgresql:// or postgres:// scheme"
            )
        if not parsed.hostname or not parsed.path.strip("/"):
            raise DatabaseConfigurationError(
                "DATABASE_URL must include a host and database name"
            )
        return DatabaseConfig(engine="postgres", database_url=database_url)

    fallback = sqlite_path or env.get("PIO_DB_PATH") or env.get("ORION_DB_PATH") or "pio_dashboard.db"
    return DatabaseConfig(engine="sqlite", sqlite_path=Path(fallback))


def safe_database_description(config: DatabaseConfig) -> str:
    """Return a non-sensitive description suitable for status output."""
    if config.engine == "postgres":
        return "PostgreSQL configured through DATABASE_URL"
    return f"SQLite at {config.sqlite_path}"
