from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.config import get_database_config
from database.connection import (
    connect_database,
    ensure_postgres_schema,
    first_value,
    list_tables,
    quote_identifier,
    table_row_counts,
)


TABLE_KEYS = {
    "papers": ("id",),
    "clients": ("id",),
    "projects": ("id",),
    "proposals": ("id",),
    "generated_assets": ("id",),
    "radar_runs": ("id",),
    "surveys": ("id",),
    "survey_questions": ("id",),
    "survey_responses": ("id",),
    "orion_search_history": ("id",),
    "orion_search_cache": ("cache_key",),
    "orion_source_health": ("source",),
    "orion_collections": ("id",),
    "orion_collection_items": ("collection_id", "paper_id"),
    "orion_alerts": ("id",),
    "orion_settings": ("key",),
}
MIGRATION_TABLES = tuple(TABLE_KEYS)
# These columns are BIGSERIAL in database/schema_postgres.sql. Do not infer
# sequence ownership from a column name: papers.id is deliberately TEXT.
SEQUENCE_COLUMNS = {
    "clients": "id",
    "projects": "id",
    "proposals": "id",
    "generated_assets": "id",
    "radar_runs": "id",
    "surveys": "id",
    "survey_questions": "id",
    "survey_responses": "id",
    "orion_search_history": "id",
    "orion_collections": "id",
    "orion_alerts": "id",
}


@dataclass
class TableResult:
    source: int = 0
    inserted: int = 0
    skipped: int = 0
    failed: int = 0


def open_sqlite_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {resolved}")
    connection = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def sqlite_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def source_counts(connection: sqlite3.Connection) -> dict[str, int]:
    existing = sqlite_tables(connection)
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()[0])
        for table in MIGRATION_TABLES
        if table in existing
    }


def read_source_rows(connection: sqlite3.Connection, table: str) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(f"SELECT * FROM {quote_identifier(table)}").fetchall()
    ]


def destination_rows_by_key(
    connection, table: str, keys: tuple[str, ...], columns: list[str]
) -> dict[tuple, dict]:
    names = ",".join(quote_identifier(column) for column in columns)
    rows = connection.execute(
        f"SELECT {names} FROM {quote_identifier(table)}"
    ).fetchall()
    normalized = [
        row if isinstance(row, dict) else dict(zip(columns, row, strict=True))
        for row in rows
    ]
    return {
        tuple(row[key] for key in keys): row
        for row in normalized
    }


def verify_counts(source: sqlite3.Connection, destination) -> dict[str, dict[str, int]]:
    destination_tables = set(list_tables(destination))
    results: dict[str, dict[str, int]] = {}
    for table in MIGRATION_TABLES:
        if table not in sqlite_tables(source):
            continue
        rows = read_source_rows(source, table)
        if table not in destination_tables:
            results[table] = {
                "source": len(rows), "destination": 0,
                "missing": len(rows), "mismatched": 0,
            }
            continue
        columns = list(rows[0]) if rows else list(TABLE_KEYS[table])
        destination_rows = destination_rows_by_key(
            destination, table, TABLE_KEYS[table], columns
        )
        source_by_key = {
            tuple(row[key] for key in TABLE_KEYS[table]): row
            for row in rows
        }
        missing = set(source_by_key) - set(destination_rows)
        mismatched = sum(
            1
            for key, row in source_by_key.items()
            if key in destination_rows
            and any(destination_rows[key].get(column) != row.get(column) for column in columns)
        )
        destination_count = int(first_value(destination.execute(
            f"SELECT COUNT(*) AS count FROM {quote_identifier(table)}"
        ).fetchone()))
        results[table] = {
            "source": len(rows),
            "destination": destination_count,
            "missing": len(missing),
            "mismatched": mismatched,
        }
    return results


def synchronize_sequences(destination) -> list[tuple[str, str]]:
    """Reset confirmed PostgreSQL sequences after preserving explicit IDs."""
    synchronized: list[tuple[str, str]] = []
    for table, column in SEQUENCE_COLUMNS.items():
        metadata = destination.execute(
            "SELECT pg_get_serial_sequence(?, ?) AS sequence_name",
            (table, column),
        ).fetchone()
        sequence_name = first_value(metadata)
        if not sequence_name:
            continue

        aggregate = destination.execute(
            f"SELECT COALESCE(MAX({quote_identifier(column)}), 1) AS max_value, "
            f"COUNT(*) > 0 AS has_rows FROM {quote_identifier(table)}"
        ).fetchone()
        if isinstance(aggregate, dict):
            max_value = aggregate["max_value"]
            has_rows = aggregate["has_rows"]
        else:
            max_value, has_rows = aggregate
        destination.execute(
            "SELECT setval(?::regclass, ?, ?)",
            (sequence_name, int(max_value), bool(has_rows)),
        )
        synchronized.append((table, column))
    return synchronized


def migrate(source: sqlite3.Connection, destination) -> dict[str, TableResult]:
    results: dict[str, TableResult] = {}
    try:
        ensure_postgres_schema(destination)
        for table in MIGRATION_TABLES:
            if table not in sqlite_tables(source):
                continue
            rows = read_source_rows(source, table)
            result = TableResult(source=len(rows))
            results[table] = result
            for row in rows:
                columns = list(row)
                names = ",".join(quote_identifier(column) for column in columns)
                placeholders = ",".join("?" for _ in columns)
                sql = (
                    f"INSERT INTO {quote_identifier(table)} ({names}) "
                    f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                )
                cursor = destination.execute(sql, [row[column] for column in columns])
                if cursor.rowcount == 1:
                    result.inserted += 1
                else:
                    result.skipped += 1

        synchronize_sequences(destination)

        verification = verify_counts(source, destination)
        invalid = {
            table: {"missing": values["missing"], "mismatched": values["mismatched"]}
            for table, values in verification.items()
            if values["missing"] or values["mismatched"]
        }
        if invalid:
            raise RuntimeError(f"Migration verification found invalid rows: {invalid}")
        destination.commit()
        return results
    except Exception:
        destination.rollback()
        for result in results.values():
            result.failed = result.inserted
            result.inserted = 0
        raise


def safe_error_message(error: Exception, database_url: str | None) -> str:
    message = str(error)
    if database_url:
        message = message.replace(database_url, "<redacted DATABASE_URL>")
    return f"{type(error).__name__}: {message}"


def print_counts(label: str, counts: dict[str, int]):
    print(label)
    for table, count in counts.items():
        print(f"  {table}: {count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely migrate Orion SQLite data to PostgreSQL")
    parser.add_argument("--sqlite-path", type=Path, default=Path("pio_dashboard.db"))
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Inspect source and destination without writes")
    modes.add_argument("--verify", action="store_true", help="Compare source and destination without writes")
    modes.add_argument("--apply", action="store_true", help="Run the transactional idempotent migration")
    args = parser.parse_args(argv)

    source = open_sqlite_read_only(args.sqlite_path)
    destination = None
    try:
        counts = source_counts(source)
        print_counts("SQLite source rows:", counts)
        config = get_database_config()
        if config.engine != "postgres":
            print("PostgreSQL is not configured; DATABASE_URL was not supplied. No writes performed.")
            return 0 if args.dry_run else 2

        destination = connect_database(config)
        if args.dry_run:
            tables = set(list_tables(destination))
            existing_counts = table_row_counts(destination, [t for t in MIGRATION_TABLES if t in tables])
            print_counts("Existing PostgreSQL rows:", existing_counts)
            print("Dry-run complete. No schema or data was written.")
            return 0
        if args.verify:
            verification = verify_counts(source, destination)
            for table, values in verification.items():
                print(
                    f"{table}: source={values['source']} destination={values['destination']} "
                    f"missing={values['missing']} mismatched={values['mismatched']}"
                )
            return 0 if all(
                not values["missing"] and not values["mismatched"]
                for values in verification.values()
            ) else 1

        results = migrate(source, destination)
        for table, result in results.items():
            print(
                f"{table}: source={result.source} inserted={result.inserted} "
                f"skipped={result.skipped} failed={result.failed}"
            )
        print("Migration committed successfully. SQLite was not modified or deleted.")
        return 0
    except Exception as error:
        database_url = None
        try:
            config = get_database_config()
            database_url = config.database_url
        except Exception:
            pass
        print(f"Migration failed safely: {safe_error_message(error, database_url)}")
        return 1
    finally:
        if destination is not None:
            destination.close()
        source.close()


if __name__ == "__main__":
    raise SystemExit(main())
