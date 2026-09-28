from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.config import get_database_config
from database.connection import check_database_health, connect_database, list_tables, table_row_counts


def collect_status(sqlite_path: Path | None = None) -> dict:
    config = get_database_config(sqlite_path)
    health = check_database_health(sqlite_path=sqlite_path)
    status = {**health, "tables": [], "row_counts": {}, "migration_ready": False}
    if not health["reachable"]:
        return status
    connection = connect_database(config)
    try:
        status["tables"] = list_tables(connection)
        status["row_counts"] = table_row_counts(connection, status["tables"])
        status["migration_ready"] = bool(status["tables"])
    finally:
        connection.close()
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show non-sensitive Orion database status")
    parser.add_argument("--sqlite-path", type=Path)
    args = parser.parse_args(argv)
    status = collect_status(args.sqlite_path)
    print(f"Database engine: {status['engine']}")
    print(f"Connection status: {'reachable' if status['reachable'] else 'unreachable'}")
    print(f"Basic query: {status['basic_query']}")
    print(f"Latency: {status['latency_ms']} ms")
    print(f"Tables found: {', '.join(status['tables']) or 'none'}")
    for table, count in status["row_counts"].items():
        print(f"  {table}: {count}")
    print(f"Migration readiness: {'ready' if status['migration_ready'] else 'not ready'}")
    return 0 if status["reachable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
