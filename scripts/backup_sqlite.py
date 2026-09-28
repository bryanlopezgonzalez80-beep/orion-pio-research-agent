from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup_sqlite(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")

    source_uri = f"{source.as_uri()}?mode=ro"
    source_connection = sqlite3.connect(source_uri, uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        result = destination_connection.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("SQLite backup failed its integrity check")
    except Exception:
        destination_connection.close()
        source_connection.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        destination_connection.close()
        source_connection.close()
    return destination


def default_destination(directory: Path = Path("backups")) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"pio_dashboard_{stamp}.db"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite backup")
    parser.add_argument("--source", type=Path, default=Path("pio_dashboard.db"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = backup_sqlite(args.source, args.output or default_destination())
    print(f"Backup created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
