from __future__ import annotations

import sqlite3
import time
from collections.abc import Mapping
from pathlib import Path
from threading import Lock
from typing import Iterable

from .config import DatabaseConfig, get_database_config


class DatabaseConnectionError(RuntimeError):
    """A connection failure whose message never includes credentials."""


_POSTGRES_SCHEMA_LOCK = Lock()
_POSTGRES_SCHEMA_READY = False


def convert_placeholders(sql: str, engine: str) -> str:
    """Convert qmark parameters to psycopg parameters outside SQL strings."""
    if engine != "postgres":
        return sql
    out: list[str] = []
    in_single_quote = False
    i = 0
    while i < len(sql):
        char = sql[i]
        if char == "'":
            out.append(char)
            if in_single_quote and i + 1 < len(sql) and sql[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            in_single_quote = not in_single_quote
        elif char == "?" and not in_single_quote:
            out.append("%s")
        elif (
            char == ":"
            and not in_single_quote
            and (i == 0 or sql[i - 1] != ":")
            and i + 1 < len(sql)
            and (sql[i + 1].isalpha() or sql[i + 1] == "_")
        ):
            end = i + 2
            while end < len(sql) and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            out.append(f"%({sql[i + 1:end]})s")
            i = end
            continue
        else:
            out.append(char)
        i += 1
    return "".join(out)


class CursorProxy:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class ConnectionProxy:
    def __init__(self, raw, engine: str):
        self.raw = raw
        self.engine = engine

    def execute(self, sql: str, params: Iterable | None = None) -> CursorProxy:
        statement = convert_placeholders(sql, self.engine)
        if params is None:
            cursor = self.raw.execute(statement)
        else:
            values = params if isinstance(params, Mapping) else tuple(params)
            cursor = self.raw.execute(statement, values)
        return CursorProxy(cursor)

    def executemany(self, sql: str, params) -> CursorProxy:
        statement = convert_placeholders(sql, self.engine)
        if self.engine == "postgres":
            cursor = self.raw.cursor()
            cursor.executemany(statement, params)
        else:
            cursor = self.raw.executemany(statement, params)
        return CursorProxy(cursor)

    def executescript(self, script: str):
        if self.engine == "sqlite":
            return self.raw.executescript(script)
        cursor = None
        for statement in split_sql_statements(script):
            cursor = self.execute(statement)
        return cursor

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def split_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    for char in script:
        if char == "'":
            in_single_quote = not in_single_quote
        if char == ";" and not in_single_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)
    return statements


def connect_database(
    config: DatabaseConfig | None = None,
    *,
    sqlite_path: str | Path | None = None,
    force_sqlite: bool = False,
    sqlite_foreign_keys: bool = False,
) -> ConnectionProxy:
    config = config or get_database_config(sqlite_path, force_sqlite=force_sqlite)
    if config.engine == "postgres":
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - dependency error is environment-specific
            raise RuntimeError(
                "PostgreSQL support requires psycopg[binary]"
            ) from exc
        try:
            raw = psycopg.connect(config.database_url, row_factory=dict_row)
        except Exception:
            raise DatabaseConnectionError(
                "Unable to connect to the configured PostgreSQL database"
            ) from None
        return ConnectionProxy(raw, "postgres")

    path = Path(config.sqlite_path or "pio_dashboard.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path, timeout=30)
    raw.row_factory = sqlite3.Row
    if sqlite_foreign_keys:
        raw.execute("PRAGMA foreign_keys=ON")
    return ConnectionProxy(raw, "sqlite")


def ensure_postgres_schema(connection: ConnectionProxy):
    global _POSTGRES_SCHEMA_READY
    if connection.engine != "postgres":
        return
    if _POSTGRES_SCHEMA_READY:
        return
    with _POSTGRES_SCHEMA_LOCK:
        if _POSTGRES_SCHEMA_READY:
            return
        schema_path = Path(__file__).with_name("schema_postgres.sql")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        connection.commit()
        _POSTGRES_SCHEMA_READY = True


def first_value(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def insert_returning_id(connection: ConnectionProxy, sql: str, params) -> int:
    if connection.engine == "postgres":
        row = connection.execute(f"{sql.rstrip().rstrip(';')} RETURNING id", params).fetchone()
        return int(row["id"])
    return int(connection.execute(sql, params).lastrowid)


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def list_tables(connection: ConnectionProxy) -> list[str]:
    if connection.engine == "postgres":
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"
        ).fetchall()
        return [row["table_name"] for row in rows]
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def table_row_counts(connection: ConnectionProxy, tables: Iterable[str] | None = None) -> dict[str, int]:
    selected = list(tables) if tables is not None else list_tables(connection)
    counts: dict[str, int] = {}
    existing = set(list_tables(connection))
    for table in selected:
        if table not in existing:
            continue
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {quote_identifier(table)}").fetchone()
        counts[table] = int(row["count"] if isinstance(row, dict) else row[0])
    return counts


def check_database_health(*, sqlite_path: str | Path | None = None) -> dict:
    started = time.perf_counter()
    config = get_database_config(sqlite_path)
    result = {
        "engine": config.engine,
        "reachable": False,
        "basic_query": "fail",
        "latency_ms": None,
    }
    connection = None
    try:
        connection = connect_database(config)
        row = connection.execute("SELECT 1 AS ok").fetchone()
        value = row["ok"] if isinstance(row, dict) else row[0]
        result["reachable"] = value == 1
        result["basic_query"] = "pass" if value == 1 else "fail"
    except Exception:
        result["reachable"] = False
        result["basic_query"] = "fail"
    finally:
        if connection is not None:
            connection.close()
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result
