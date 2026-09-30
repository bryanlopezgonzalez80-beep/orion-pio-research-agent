from __future__ import annotations

from pathlib import Path

import pytest

from database import connection
from database.config import DatabaseConfigurationError, get_database_config, safe_database_description

pytestmark = pytest.mark.unit


def test_database_config_defaults_to_sqlite(tmp_path):
    path = tmp_path / "orion.db"
    config = get_database_config(path, environ={})
    assert config.engine == "sqlite"
    assert config.sqlite_path == path
    assert "SQLite" in safe_database_description(config)


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_database_config_selects_postgres_without_exposing_password(scheme):
    url = f"{scheme}://user:very-secret@db.example.test/orion"
    config = get_database_config(environ={"DATABASE_URL": url})
    assert config.engine == "postgres"
    assert config.database_url == url
    assert "very-secret" not in safe_database_description(config)


@pytest.mark.parametrize(
    "url",
    ["mysql://host/db", "sqlite:///tmp/test.db", "postgresql:///missing-host", "postgresql://host"],
)
def test_invalid_database_urls_fail_closed(url):
    with pytest.raises(DatabaseConfigurationError):
        get_database_config(environ={"DATABASE_URL": url})


def test_force_sqlite_ignores_database_url(tmp_path):
    config = get_database_config(
        tmp_path / "test.db",
        environ={"DATABASE_URL": "postgresql://user:secret@host/db"},
        force_sqlite=True,
    )
    assert config.engine == "sqlite"


def test_placeholder_conversion_ignores_question_marks_in_literals():
    sql = "SELECT '?' AS literal, value FROM sample WHERE id=? AND note='it''s ?'"
    converted = connection.convert_placeholders(sql, "postgres")
    assert converted == "SELECT '?' AS literal, value FROM sample WHERE id=%s AND note='it''s ?'"
    assert connection.convert_placeholders(sql, "sqlite") == sql


def test_named_placeholder_conversion_preserves_casts_and_literals():
    sql = "INSERT INTO papers(id,title) VALUES (:id,:title) RETURNING CURRENT_TIMESTAMP::text, ':literal'"
    converted = connection.convert_placeholders(sql, "postgres")
    assert converted == "INSERT INTO papers(id,title) VALUES (%(id)s,%(title)s) RETURNING CURRENT_TIMESTAMP::text, ':literal'"


def test_sqlite_connection_health_tables_and_counts(tmp_path, monkeypatch):
    path = tmp_path / "health.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    con = connection.connect_database(sqlite_path=path, force_sqlite=True)
    try:
        con.execute("CREATE TABLE example(id INTEGER PRIMARY KEY, name TEXT)")
        con.execute("INSERT INTO example(name) VALUES (?)", ("Orión",))
        con.commit()
        assert connection.list_tables(con) == ["example"]
        assert connection.table_row_counts(con) == {"example": 1}
    finally:
        con.close()
    health = connection.check_database_health(sqlite_path=path)
    assert health["engine"] == "sqlite"
    assert health["reachable"] is True
    assert health["basic_query"] == "pass"
    assert "database_url" not in health


def test_health_failure_is_non_sensitive(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@host/orion")
    monkeypatch.setattr(connection, "connect_database", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    health = connection.check_database_health()
    assert health["engine"] == "postgres"
    assert health["reachable"] is False
    assert "secret" not in str(health)


def test_postgres_schema_contains_every_active_table():
    schema = Path("database/schema_postgres.sql").read_text(encoding="utf-8")
    expected = {
        "papers", "clients", "projects", "proposals", "generated_assets", "radar_runs",
        "surveys", "survey_questions", "survey_responses", "orion_search_history",
        "orion_search_cache", "orion_source_health", "orion_collections",
        "orion_collection_items", "orion_alerts", "orion_settings",
    }
    for table in expected:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert "AUTOINCREMENT" not in schema
    assert "BIGSERIAL" in schema
    assert "DOUBLE PRECISION" in schema


def test_postgres_connection_errors_do_not_fallback_to_sqlite(monkeypatch):
    config = get_database_config(environ={"DATABASE_URL": "postgresql://user:secret@host/db"})

    class FakePsycopg:
        @staticmethod
        def connect(*args, **kwargs):
            raise OSError("unreachable")

    monkeypatch.setitem(__import__("sys").modules, "psycopg", FakePsycopg)
    monkeypatch.setitem(__import__("sys").modules, "psycopg.rows", type("Rows", (), {"dict_row": object()})())
    with pytest.raises(connection.DatabaseConnectionError) as error:
        connection.connect_database(config)
    assert "secret" not in str(error.value)
    assert "host" not in str(error.value)


def test_connection_proxy_delegates_transactions_and_scripts():
    events = []

    class FakeCursor:
        rowcount = 2
        lastrowid = 7

        def fetchone(self):
            return (1,)

        def fetchall(self):
            return [(1,), (2,)]

        def __iter__(self):
            return iter([(1,)])

    class FakeRaw:
        def execute(self, sql, params=None):
            events.append(("execute", sql, params))
            return FakeCursor()

        def cursor(self):
            class BatchCursor(FakeCursor):
                def executemany(self, sql, params):
                    events.append(("executemany", sql, params))
            return BatchCursor()

        def commit(self):
            events.append(("commit",))

        def rollback(self):
            events.append(("rollback",))

        def close(self):
            events.append(("close",))

    proxy = connection.ConnectionProxy(FakeRaw(), "postgres")
    cursor = proxy.execute("SELECT * FROM t WHERE id=?", (1,))
    assert cursor.fetchone() == (1,)
    assert cursor.fetchall() == [(1,), (2,)]
    assert list(cursor) == [(1,)]
    assert cursor.rowcount == 2
    assert cursor.lastrowid == 7
    proxy.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])
    proxy.executescript("CREATE TABLE a(id int); CREATE TABLE b(id int);")
    proxy.commit(); proxy.rollback(); proxy.close()
    assert any(event[0] == "executemany" and "%s" in event[1] for event in events)
    assert ("commit",) in events and ("rollback",) in events and ("close",) in events


def test_first_value_and_returning_id_helpers():
    assert connection.first_value({"count": 3}) == 3
    assert connection.first_value((4,)) == 4
    assert connection.first_value(None) is None

    class Cursor:
        lastrowid = 9

        def fetchone(self):
            return {"id": 11}

    class Con:
        def __init__(self, engine):
            self.engine = engine
            self.sql = ""

        def execute(self, sql, params):
            self.sql = sql
            return Cursor()

    sqlite = Con("sqlite")
    postgres = Con("postgres")
    assert connection.insert_returning_id(sqlite, "INSERT INTO x(a) VALUES (?)", (1,)) == 9
    assert connection.insert_returning_id(postgres, "INSERT INTO x(a) VALUES (?)", (1,)) == 11
    assert postgres.sql.endswith("RETURNING id")


def test_ensure_postgres_schema_executes_schema(monkeypatch):
    calls = []
    monkeypatch.setattr(connection, "_POSTGRES_SCHEMA_READY", False)

    class Con:
        engine = "postgres"

        def executescript(self, script):
            calls.append(script)

        def commit(self):
            calls.append("commit")

    connection.ensure_postgres_schema(Con())
    assert "CREATE TABLE IF NOT EXISTS papers" in calls[0]
    connection.ensure_postgres_schema(Con())
    assert len([item for item in calls if isinstance(item, str) and item.startswith("CREATE")]) == 1

    class SQLiteCon:
        engine = "sqlite"

    assert connection.ensure_postgres_schema(SQLiteCon()) is None
