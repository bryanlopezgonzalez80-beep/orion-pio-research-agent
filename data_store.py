from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import os
DB_PATH = Path(os.getenv("PIO_DB_PATH") or Path(__file__).with_name("pio_dashboard.db"))

PAPER_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "title": "TEXT NOT NULL",
    "authors": "TEXT",
    "year": "INTEGER",
    "published_date": "TEXT",
    "source": "TEXT",
    "journal": "TEXT",
    "work_type": "TEXT",
    "doi": "TEXT",
    "url": "TEXT",
    "oa_url": "TEXT",
    "pdf_url": "TEXT",
    "abstract": "TEXT",
    "topics": "TEXT",
    "discovered_via": "TEXT",
    "cited_by_count": "INTEGER DEFAULT 0",
    "relevance_score": "REAL DEFAULT 0",
    "practical_score": "REAL DEFAULT 0",
    "evidence_score": "REAL DEFAULT 0",
    "recency_score": "REAL DEFAULT 0",
    "summary": "TEXT",
    "why_it_matters": "TEXT",
    "applications": "TEXT",
    "limitations": "TEXT",
    "evidence_level": "TEXT",
    "apa_citation": "TEXT",
    "read_full": "INTEGER DEFAULT 0",
    "favorite": "INTEGER DEFAULT 0",
    "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
}


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _init_schema(con)
    return con


def _init_schema(con: sqlite3.Connection):
    cols = ",\n        ".join(f"{name} {spec}" for name, spec in PAPER_COLUMNS.items())
    con.execute(f"CREATE TABLE IF NOT EXISTS papers (\n        {cols}\n    )")

    # Safe migrations from v1: add any new columns that are absent.
    existing = {r[1] for r in con.execute("PRAGMA table_info(papers)").fetchall()}
    for name, spec in PAPER_COLUMNS.items():
        if name not in existing:
            # SQLite ALTER TABLE does not allow adding PK/NOT NULL without a default;
            # all v2-only columns are nullable/defaulted, so strip constraints defensively.
            add_spec = spec.replace(" PRIMARY KEY", "").replace(" NOT NULL", "")
            # SQLite cannot ALTER ADD COLUMN with non-constant defaults such as CURRENT_TIMESTAMP.
            if "CURRENT_TIMESTAMP" in add_spec:
                add_spec = "TEXT"
            con.execute(f"ALTER TABLE papers ADD COLUMN {name} {add_spec}")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            organization TEXT,
            email TEXT,
            phone TEXT,
            status TEXT DEFAULT 'Prospecto',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            name TEXT NOT NULL,
            category TEXT,
            status TEXT DEFAULT 'Idea',
            due_date TEXT,
            value REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'Borrador',
            amount REAL DEFAULT 0,
            sent_date TEXT,
            followup_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT,
            asset_type TEXT NOT NULL,
            title TEXT,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS radar_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sources TEXT,
            topics TEXT,
            found INTEGER DEFAULT 0,
            unique_saved INTEGER DEFAULT 0,
            errors TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS survey_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            scale_min INTEGER DEFAULT 1,
            scale_max INTEGER DEFAULT 5,
            FOREIGN KEY(survey_id) REFERENCES surveys(id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            respondent_label TEXT,
            answers_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(survey_id) REFERENCES surveys(id)
        )
        """
    )
    con.commit()


def _paper_payload(p: dict) -> dict:
    payload = {k: p.get(k) for k in PAPER_COLUMNS.keys() if k not in {"created_at", "updated_at"}}
    payload["title"] = payload.get("title") or "Sin título"
    for key in ("source", "journal", "work_type", "doi", "url", "oa_url", "pdf_url", "abstract", "topics", "discovered_via", "summary", "why_it_matters", "applications", "limitations", "evidence_level", "apa_citation", "authors", "published_date"):
        payload[key] = payload.get(key) or ""
    for key in ("year", "cited_by_count", "read_full", "favorite"):
        payload[key] = int(payload.get(key) or 0)
    for key in ("relevance_score", "practical_score", "evidence_score", "recency_score"):
        payload[key] = float(payload.get(key) or 0)
    return payload


def upsert_papers(papers: Iterable[dict]):
    papers = list(papers)
    if not papers:
        return
    payloads = [_paper_payload(p) for p in papers]
    columns = [k for k in PAPER_COLUMNS.keys() if k not in {"created_at", "updated_at"}]
    col_sql = ",".join(columns)
    val_sql = ",".join(f":{c}" for c in columns)
    update_sql = ",\n".join(
        [
            "title=excluded.title",
            "authors=CASE WHEN excluded.authors<>'' THEN excluded.authors ELSE papers.authors END",
            "year=CASE WHEN excluded.year<>0 THEN excluded.year ELSE papers.year END",
            "published_date=CASE WHEN excluded.published_date<>'' THEN excluded.published_date ELSE papers.published_date END",
            "source=CASE WHEN excluded.source<>'' THEN excluded.source ELSE papers.source END",
            "journal=CASE WHEN excluded.journal<>'' THEN excluded.journal ELSE papers.journal END",
            "work_type=CASE WHEN excluded.work_type<>'' THEN excluded.work_type ELSE papers.work_type END",
            "doi=CASE WHEN excluded.doi<>'' THEN excluded.doi ELSE papers.doi END",
            "url=CASE WHEN excluded.url<>'' THEN excluded.url ELSE papers.url END",
            "oa_url=CASE WHEN excluded.oa_url<>'' THEN excluded.oa_url ELSE papers.oa_url END",
            "pdf_url=CASE WHEN excluded.pdf_url<>'' THEN excluded.pdf_url ELSE papers.pdf_url END",
            "abstract=CASE WHEN length(excluded.abstract)>length(COALESCE(papers.abstract,'')) THEN excluded.abstract ELSE papers.abstract END",
            "topics=CASE WHEN excluded.topics<>'' THEN excluded.topics ELSE papers.topics END",
            "discovered_via=CASE WHEN excluded.discovered_via<>'' THEN excluded.discovered_via ELSE papers.discovered_via END",
            "cited_by_count=MAX(COALESCE(papers.cited_by_count,0), excluded.cited_by_count)",
            "relevance_score=MAX(COALESCE(papers.relevance_score,0), excluded.relevance_score)",
            "practical_score=MAX(COALESCE(papers.practical_score,0), excluded.practical_score)",
            "evidence_score=MAX(COALESCE(papers.evidence_score,0), excluded.evidence_score)",
            "recency_score=MAX(COALESCE(papers.recency_score,0), excluded.recency_score)",
            "summary=CASE WHEN excluded.summary<>'' THEN excluded.summary ELSE papers.summary END",
            "why_it_matters=CASE WHEN excluded.why_it_matters<>'' THEN excluded.why_it_matters ELSE papers.why_it_matters END",
            "applications=CASE WHEN excluded.applications<>'' THEN excluded.applications ELSE papers.applications END",
            "limitations=CASE WHEN excluded.limitations<>'' THEN excluded.limitations ELSE papers.limitations END",
            "evidence_level=CASE WHEN excluded.evidence_level<>'' THEN excluded.evidence_level ELSE papers.evidence_level END",
            "apa_citation=CASE WHEN excluded.apa_citation<>'' THEN excluded.apa_citation ELSE papers.apa_citation END",
            "read_full=MAX(COALESCE(papers.read_full,0), excluded.read_full)",
            "favorite=MAX(COALESCE(papers.favorite,0), excluded.favorite)",
            "updated_at=CURRENT_TIMESTAMP",
        ]
    )
    sql = f"""
        INSERT INTO papers ({col_sql}) VALUES ({val_sql})
        ON CONFLICT(id) DO UPDATE SET
        {update_sql}
    """
    con = connect()
    try:
        con.executemany(sql, payloads)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def get_papers(limit: int = 500, favorites_only: bool = False):
    con = connect()
    where = "WHERE favorite=1" if favorites_only else ""
    rows = con.execute(
        f"SELECT * FROM papers {where} ORDER BY relevance_score DESC, published_date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_paper(paper_id: str):
    con = connect()
    row = con.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def set_favorite(paper_id: str, favorite: bool):
    con = connect()
    con.execute("UPDATE papers SET favorite=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (1 if favorite else 0, paper_id))
    con.commit(); con.close()


def set_read_full(paper_id: str, read_full: bool):
    con = connect()
    con.execute("UPDATE papers SET read_full=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (1 if read_full else 0, paper_id))
    con.commit(); con.close()


def save_ai_analysis(paper_id: str, data: dict):
    con = connect()
    con.execute(
        """
        UPDATE papers SET summary=?, why_it_matters=?, applications=?, limitations=?, evidence_level=?,
            apa_citation=?, read_full=?, practical_score=?, evidence_score=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            data.get("summary", ""), data.get("why_it_matters", ""), data.get("applications", ""),
            data.get("limitations", ""), data.get("evidence_level", ""), data.get("apa_citation", ""),
            1 if data.get("read_full") else 0, float(data.get("practical_score", 0) or 0),
            float(data.get("evidence_score", 0) or 0), paper_id,
        ),
    )
    con.commit(); con.close()


def add_generated_asset(paper_id: str, asset_type: str, title: str, content: str):
    con = connect()
    con.execute(
        "INSERT INTO generated_assets (paper_id,asset_type,title,content) VALUES (?,?,?,?)",
        (paper_id, asset_type, title, content),
    )
    con.commit(); con.close()


def get_generated_assets(limit: int = 100):
    con = connect()
    rows = con.execute("SELECT * FROM generated_assets ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def log_radar_run(sources, topics, found: int, unique_saved: int, errors):
    con = connect()
    con.execute(
        "INSERT INTO radar_runs (sources,topics,found,unique_saved,errors) VALUES (?,?,?,?,?)",
        (json.dumps(sources, ensure_ascii=False), json.dumps(topics, ensure_ascii=False), found, unique_saved, json.dumps(errors, ensure_ascii=False)),
    )
    con.commit(); con.close()


def get_radar_runs(limit: int = 30):
    con = connect()
    rows = con.execute("SELECT * FROM radar_runs ORDER BY run_at DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_client(name: str, organization: str = "", email: str = "", phone: str = "", status: str = "Prospecto", notes: str = ""):
    con = connect()
    con.execute("INSERT INTO clients(name,organization,email,phone,status,notes) VALUES (?,?,?,?,?,?)", (name,organization,email,phone,status,notes))
    con.commit(); con.close()


def get_clients():
    con = connect(); rows = con.execute("SELECT * FROM clients ORDER BY created_at DESC").fetchall(); con.close()
    return [dict(r) for r in rows]


def add_project(client_id: Optional[int], name: str, category: str, status: str, due_date: str, value: float, notes: str):
    con = connect()
    con.execute("INSERT INTO projects(client_id,name,category,status,due_date,value,notes) VALUES (?,?,?,?,?,?,?)", (client_id,name,category,status,due_date,value,notes))
    con.commit(); con.close()


def get_projects():
    con = connect()
    rows = con.execute(
        """SELECT p.*, c.name AS client_name FROM projects p LEFT JOIN clients c ON c.id=p.client_id ORDER BY p.created_at DESC"""
    ).fetchall(); con.close()
    return [dict(r) for r in rows]


def add_proposal(client_id: Optional[int], title: str, status: str, amount: float, sent_date: str, followup_date: str, notes: str):
    con = connect()
    con.execute("INSERT INTO proposals(client_id,title,status,amount,sent_date,followup_date,notes) VALUES (?,?,?,?,?,?,?)", (client_id,title,status,amount,sent_date,followup_date,notes))
    con.commit(); con.close()


def get_proposals():
    con = connect()
    rows = con.execute(
        """SELECT p.*, c.name AS client_name FROM proposals p LEFT JOIN clients c ON c.id=p.client_id ORDER BY p.created_at DESC"""
    ).fetchall(); con.close()
    return [dict(r) for r in rows]


def create_survey(title: str, description: str, questions: list[str], scale_min: int = 1, scale_max: int = 5):
    con = connect()
    cur = con.execute("INSERT INTO surveys(title,description) VALUES (?,?)", (title, description))
    survey_id = cur.lastrowid
    con.executemany(
        "INSERT INTO survey_questions(survey_id,question_text,scale_min,scale_max) VALUES (?,?,?,?)",
        [(survey_id, q, scale_min, scale_max) for q in questions if q.strip()],
    )
    con.commit(); con.close()
    return survey_id


def get_surveys():
    con = connect(); rows = con.execute("SELECT * FROM surveys ORDER BY created_at DESC").fetchall(); con.close()
    return [dict(r) for r in rows]


def get_survey_questions(survey_id: int):
    con = connect(); rows = con.execute("SELECT * FROM survey_questions WHERE survey_id=? ORDER BY id", (survey_id,)).fetchall(); con.close()
    return [dict(r) for r in rows]


def save_survey_response(survey_id: int, respondent_label: str, answers: dict):
    con = connect()
    con.execute("INSERT INTO survey_responses(survey_id,respondent_label,answers_json) VALUES (?,?,?)", (survey_id, respondent_label, json.dumps(answers, ensure_ascii=False)))
    con.commit(); con.close()


def get_survey_responses(survey_id: int):
    con = connect(); rows = con.execute("SELECT * FROM survey_responses WHERE survey_id=? ORDER BY created_at DESC", (survey_id,)).fetchall(); con.close()
    return [dict(r) for r in rows]


def db_stats():
    con = connect()
    stats = {}
    for table in ("papers", "clients", "projects", "proposals", "generated_assets", "radar_runs", "surveys", "survey_responses"):
        stats[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    stats["favorites"] = con.execute("SELECT COUNT(*) FROM papers WHERE favorite=1").fetchone()[0]
    stats["read_full"] = con.execute("SELECT COUNT(*) FROM papers WHERE read_full=1").fetchone()[0]
    con.close()
    return stats
