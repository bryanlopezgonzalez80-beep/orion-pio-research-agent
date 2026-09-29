from __future__ import annotations

import sqlite3

import pytest

import data_store

pytestmark = pytest.mark.integration


def test_initialization_creates_all_tables():
    con = data_store.connect()
    try:
        tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        con.close()
    assert {
        "papers", "clients", "projects", "proposals", "generated_assets",
        "radar_runs", "surveys", "survey_questions", "survey_responses",
    } <= tables


def test_empty_upsert_does_not_create_database(tmp_path, monkeypatch):
    path = tmp_path / "unused.db"
    monkeypatch.setattr(data_store, "DB_PATH", path)
    data_store.upsert_papers([])
    assert not path.exists()


def test_paper_crud_deduplicates_and_preserves_richer_values(sample_paper):
    data_store.upsert_papers([sample_paper, dict(sample_paper)])
    assert len(data_store.get_papers()) == 1

    data_store.upsert_papers([{
        "id": sample_paper["id"],
        "title": "Título actualizado",
        "abstract": "Breve",
        "cited_by_count": 2,
        "favorite": 1,
    }])
    stored = data_store.get_paper(sample_paper["id"])
    assert stored["title"] == "Título actualizado"
    assert stored["abstract"] == sample_paper["abstract"]
    assert stored["cited_by_count"] == 7
    assert stored["favorite"] == 1


def test_library_text_search_covers_topics_journal_authors_and_doi(sample_paper):
    data_store.upsert_papers([sample_paper])

    assert data_store.list_papers(query="psychological safety")[0]["id"] == sample_paper["id"]
    assert data_store.list_papers(query="Revista PIO")[0]["id"] == sample_paper["id"]
    assert data_store.list_papers(query="Ana Pérez")[0]["id"] == sample_paper["id"]
    assert data_store.list_papers(query="10.1234/orion")[0]["id"] == sample_paper["id"]


def test_paper_flags_analysis_filters_and_missing_record(sample_paper):
    data_store.upsert_papers([sample_paper])
    data_store.set_favorite(sample_paper["id"], True)
    data_store.set_read_full(sample_paper["id"], True)
    data_store.save_ai_analysis(sample_paper["id"], {
        "summary": "Síntesis útil",
        "why_it_matters": "Importa",
        "applications": "Aplicación",
        "limitations": "Limitación",
        "evidence_level": "Estudio",
        "apa_citation": "Pérez (2025)",
        "read_full": True,
        "practical_score": 8,
        "evidence_score": 7,
    })
    stored = data_store.get_paper(sample_paper["id"])
    assert stored["summary"] == "Síntesis útil"
    assert stored["read_full"] == 1
    assert data_store.get_papers(favorites_only=True)[0]["id"] == sample_paper["id"]
    assert data_store.get_paper("missing") is None
    data_store.set_favorite("missing", True)


def test_unicode_assets_and_radar_history(sample_paper):
    data_store.upsert_papers([sample_paper])
    data_store.add_generated_asset(sample_paper["id"], "taller", "Niñez y ética", "Contenido ñ")
    data_store.log_radar_run(["OpenAlex"], ["liderazgo ético"], 3, 1, ["aviso ñ"])
    assert data_store.get_generated_assets()[0]["content"] == "Contenido ñ"
    assert "liderazgo ético" in data_store.get_radar_runs()[0]["topics"]


def test_clients_projects_and_proposals_round_trip():
    data_store.add_client("José", "Compañía", "jose@example.test", "787", notes="Señal")
    client = data_store.get_clients()[0]
    data_store.add_project(client["id"], "Cambio", "DO", "Activo", "2026-01-01", 1500, "Nota")
    data_store.add_proposal(client["id"], "Propuesta", "Borrador", 2500, "", "", "Nota")
    assert data_store.get_projects()[0]["client_name"] == "José"
    assert data_store.get_proposals()[0]["client_name"] == "José"


def test_surveys_round_trip_and_stats(sample_paper):
    data_store.upsert_papers([{**sample_paper, "favorite": 1, "read_full": 1}])
    survey_id = data_store.create_survey("Clima", "Descripción", ["Pregunta uno", "  ", "Pregunta dos"])
    questions = data_store.get_survey_questions(survey_id)
    assert [q["question_text"] for q in questions] == ["Pregunta uno", "Pregunta dos"]
    data_store.save_survey_response(survey_id, "Participante", {str(questions[0]["id"]): 5})
    assert "5" in data_store.get_survey_responses(survey_id)[0]["answers_json"]
    assert data_store.get_surveys()[0]["title"] == "Clima"
    stats = data_store.db_stats()
    assert stats["papers"] == stats["favorites"] == stats["read_full"] == 1


def test_invalid_numeric_payload_rolls_back_without_partial_insert(sample_paper):
    invalid = {**sample_paper, "id": "bad", "year": "not-a-number"}
    with pytest.raises(ValueError):
        data_store.upsert_papers([sample_paper, invalid])
    assert data_store.get_papers() == []


def test_database_error_rolls_back_and_closes_connection(sample_paper, monkeypatch):
    events = []

    class BrokenConnection:
        engine = "sqlite"

        def execute(self, *args, **kwargs):
            class EmptyCursor:
                def fetchall(self):
                    return []
            return EmptyCursor()

        def executemany(self, *args, **kwargs):
            raise sqlite3.OperationalError("disk unavailable")

        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    monkeypatch.setattr(data_store, "connect", BrokenConnection)
    with pytest.raises(sqlite3.OperationalError, match="disk unavailable"):
        data_store.upsert_papers([sample_paper])
    assert events == ["rollback", "close"]


def test_schema_migration_adds_missing_columns(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE papers (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
        con.commit()
    finally:
        con.close()
    monkeypatch.setattr(data_store, "DB_PATH", path)
    con = data_store.connect()
    try:
        columns = {row[1] for row in con.execute("PRAGMA table_info(papers)")}
    finally:
        con.close()
    assert set(data_store.PAPER_COLUMNS) <= columns


def test_postgres_upsert_uses_greatest_dialect(sample_paper, monkeypatch):
    events = []

    class PostgresConnection:
        engine = "postgres"

        def execute(self, *args, **kwargs):
            class EmptyCursor:
                def fetchall(self):
                    return []
            return EmptyCursor()

        def executemany(self, sql, payloads):
            events.append(sql)

        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    monkeypatch.setattr(data_store, "connect", PostgresConnection)
    data_store.upsert_papers([sample_paper])
    assert "GREATEST(COALESCE(papers.cited_by_count,0)" in events[0]
    assert "ON CONFLICT(id) DO UPDATE" in events[0]
    assert events[-2:] == ["commit", "close"]
