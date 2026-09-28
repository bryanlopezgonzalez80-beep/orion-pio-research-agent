from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from database.connection import connect_database
from scripts import backup_sqlite, db_status, migrate_sqlite_to_postgres as migration

pytestmark = pytest.mark.integration


def create_source(path: Path):
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE papers(id TEXT PRIMARY KEY, title TEXT NOT NULL)")
        con.execute("INSERT INTO papers VALUES ('p1', 'Liderazgo ñ')")
        con.commit()
    finally:
        con.close()


def test_backup_uses_sqlite_backup_api_and_is_consistent(tmp_path):
    source = tmp_path / "source.db"
    target = tmp_path / "backups" / "copy.db"
    create_source(source)
    result = backup_sqlite.backup_sqlite(source, target)
    assert result == target.resolve()
    con = sqlite3.connect(target)
    try:
        assert con.execute("SELECT title FROM papers").fetchone()[0] == "Liderazgo ñ"
    finally:
        con.close()
    with pytest.raises(FileExistsError):
        backup_sqlite.backup_sqlite(source, target)


def test_migration_dry_run_without_database_url_never_writes(tmp_path, monkeypatch, capsys):
    source = tmp_path / "source.db"
    create_source(source)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert migration.main(["--sqlite-path", str(source), "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "papers: 1" in output
    assert "No writes performed" in output
    assert source.stat().st_size > 0


def test_source_is_opened_read_only(tmp_path):
    source = tmp_path / "source.db"
    create_source(source)
    con = migration.open_sqlite_read_only(source)
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("INSERT INTO papers VALUES ('p2', 'No')")
    finally:
        con.close()


def test_migration_is_idempotent_and_commits_after_verification(tmp_path, monkeypatch):
    source_path = tmp_path / "source.db"
    create_source(source_path)
    source = migration.open_sqlite_read_only(source_path)
    events = []

    class Cursor:
        rowcount = 1

    class Destination:
        engine = "postgres"

        def execute(self, sql, params=None):
            events.append((sql, params))
            return Cursor()

        def commit(self):
            events.append(("commit", None))

        def rollback(self):
            events.append(("rollback", None))

    destination = Destination()
    monkeypatch.setattr(migration, "ensure_postgres_schema", lambda con: events.append(("schema", None)))
    monkeypatch.setattr(migration, "verify_counts", lambda *a: {"papers": {"source": 1, "destination": 1, "missing": 0, "mismatched": 0}})
    try:
        results = migration.migrate(source, destination)
    finally:
        source.close()
    assert results["papers"].inserted == 1
    assert any("ON CONFLICT DO NOTHING" in sql for sql, _ in events if isinstance(sql, str))
    assert events[-1] == ("commit", None)


def test_migration_rolls_back_completely_on_error(tmp_path, monkeypatch):
    source_path = tmp_path / "source.db"
    create_source(source_path)
    source = migration.open_sqlite_read_only(source_path)
    events = []

    class Destination:
        engine = "postgres"

        def execute(self, sql, params=None):
            if sql.startswith("INSERT"):
                raise RuntimeError("write failed")
            return type("Cursor", (), {"rowcount": 0})()

        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

    monkeypatch.setattr(migration, "ensure_postgres_schema", lambda con: None)
    try:
        with pytest.raises(RuntimeError, match="write failed"):
            migration.migrate(source, Destination())
    finally:
        source.close()
    assert events == ["rollback"]


def test_safe_error_redacts_database_url():
    url = "postgresql://user:secret@host/db"
    message = migration.safe_error_message(RuntimeError(f"could not connect to {url}"), url)
    assert "secret" not in message
    assert "<redacted DATABASE_URL>" in message


def test_verify_detects_conflicting_destination_content(tmp_path):
    source_path = tmp_path / "source.db"
    destination_path = tmp_path / "destination.db"
    create_source(source_path)
    destination_raw = sqlite3.connect(destination_path)
    try:
        destination_raw.execute("CREATE TABLE papers(id TEXT PRIMARY KEY, title TEXT NOT NULL)")
        destination_raw.execute("INSERT INTO papers VALUES ('p1', 'Different title')")
        destination_raw.commit()
    finally:
        destination_raw.close()
    source = migration.open_sqlite_read_only(source_path)
    destination = connect_database(sqlite_path=destination_path, force_sqlite=True)
    try:
        result = migration.verify_counts(source, destination)["papers"]
    finally:
        source.close()
        destination.close()
    assert result == {"source": 1, "destination": 1, "missing": 0, "mismatched": 1}


def test_db_status_reports_sqlite_without_secrets(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    create_source(source)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    status = db_status.collect_status(source)
    assert status["engine"] == "sqlite"
    assert status["row_counts"] == {"papers": 1}
    assert status["migration_ready"] is True
