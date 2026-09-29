from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import os
from database.connection import connect_database, ensure_postgres_schema, insert_returning_id

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
    "evidence_type": "TEXT",
    "peer_review_status": "TEXT DEFAULT 'UNKNOWN'",
    "publication_type": "TEXT",
    "retraction_status": "TEXT DEFAULT 'UNKNOWN'",
    "correction_status": "TEXT DEFAULT 'UNKNOWN'",
    "doi_verified": "INTEGER DEFAULT 0",
    "metadata_sources_count": "INTEGER DEFAULT 1",
    "metadata_provenance": "TEXT DEFAULT '{}'",
    "evidence_flags": "TEXT DEFAULT '[]'",
    "abstract_available": "INTEGER DEFAULT 0",
    "apa_citation": "TEXT",
    "geography_primary": "TEXT",
    "geography_tags": "TEXT",
    "geography_confidence": "REAL DEFAULT 0",
    "geography_basis": "TEXT",
    "study_location": "TEXT",
    "author_affiliation_location": "TEXT",
    "affiliation_locations": "TEXT",
    "publication_location": "TEXT",
    "geographic_mentions": "TEXT",
    "geo_pr": "INTEGER DEFAULT 0",
    "geo_us": "INTEGER DEFAULT 0",
    "geo_latam_caribbean": "INTEGER DEFAULT 0",
    "access_status": "TEXT DEFAULT 'UNKNOWN'",
    "best_access_url": "TEXT",
    "access_provider": "TEXT",
    "access_type": "TEXT",
    "requires_login": "INTEGER DEFAULT 0",
    "institutional_access_possible": "INTEGER DEFAULT 0",
    "open_access": "INTEGER DEFAULT 0",
    "pdf_available": "INTEGER DEFAULT 0",
    "html_available": "INTEGER DEFAULT 0",
    "doi_url": "TEXT",
    "alternative_access_options": "TEXT DEFAULT '[]'",
    "fulltext_available": "INTEGER DEFAULT 0",
    "read_full": "INTEGER DEFAULT 0",
    "favorite": "INTEGER DEFAULT 0",
    "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
}


def connect():
    con = connect_database(sqlite_path=DB_PATH)
    if con.engine == "postgres":
        ensure_postgres_schema(con)
        con.commit()
    else:
        _init_schema(con)
    return con


def verify_database_backend() -> str:
    """Fail fast if the configured database cannot be opened."""
    con = connect()
    try:
        return con.engine
    finally:
        con.close()


def _init_schema(con):
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
        """CREATE TABLE IF NOT EXISTS paper_external_ids (
            paper_id TEXT NOT NULL,
            id_type TEXT NOT NULL,
            external_id TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(id_type, external_id),
            FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
        )"""
    )

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
    from evidence_pipeline import enrich_record

    p = enrich_record(p)
    payload = {k: p.get(k) for k in PAPER_COLUMNS.keys() if k not in {"created_at", "updated_at"}}
    payload["title"] = payload.get("title") or "Sin título"
    for key in ("source", "journal", "work_type", "doi", "url", "oa_url", "pdf_url", "abstract", "topics", "discovered_via", "summary", "why_it_matters", "applications", "limitations", "evidence_level", "evidence_type", "apa_citation", "authors", "published_date", "geography_primary", "study_location", "author_affiliation_location", "publication_location", "peer_review_status", "publication_type", "retraction_status", "correction_status", "access_status", "best_access_url", "access_provider", "access_type", "doi_url"):
        payload[key] = payload.get(key) or ""
    for key in ("geography_tags", "affiliation_locations", "geographic_mentions", "evidence_flags", "alternative_access_options"):
        payload[key] = json.dumps(payload.get(key) or [], ensure_ascii=False)
    for key in ("geography_basis", "metadata_provenance"):
        payload[key] = json.dumps(payload.get(key) or {}, ensure_ascii=False)
    for key in ("year", "cited_by_count", "read_full", "favorite", "geo_pr", "geo_us", "geo_latam_caribbean", "doi_verified", "metadata_sources_count", "abstract_available", "requires_login", "institutional_access_possible", "open_access", "pdf_available", "html_available", "fulltext_available"):
        payload[key] = int(payload.get(key) or 0)
    for key in ("relevance_score", "practical_score", "evidence_score", "recency_score", "geography_confidence"):
        payload[key] = float(payload.get(key) or 0)
    return payload


def _json_value(value, fallback):
    if isinstance(value, type(fallback)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _merge_provenance_payloads(con, payloads: list[dict]) -> None:
    """Union additive provenance in one batched read before portable UPSERT."""
    by_id = {str(payload.get("id") or ""): payload for payload in payloads}
    ids = [paper_id for paper_id in by_id if paper_id]
    fields = (
        "id,geography_tags,geography_basis,affiliation_locations,"
        "geographic_mentions,metadata_provenance,evidence_flags,"
        "alternative_access_options,geo_pr,geo_us,geo_latam_caribbean,metadata_sources_count"
    )
    existing_rows = []
    for start in range(0, len(ids), 500):
        batch = ids[start:start + 500]
        placeholders = ",".join("?" for _ in batch)
        existing_rows.extend(
            con.execute(f"SELECT {fields} FROM papers WHERE id IN ({placeholders})", batch).fetchall()
        )
    for raw in existing_rows:
        existing = dict(raw)
        payload = by_id[str(existing["id"])]
        for field in ("geography_tags", "affiliation_locations", "geographic_mentions", "evidence_flags"):
            combined = sorted(set(_json_value(existing.get(field), [])) | set(_json_value(payload.get(field), [])))
            payload[field] = json.dumps(combined, ensure_ascii=False)
        old_options = _json_value(existing.get("alternative_access_options"), [])
        new_options = _json_value(payload.get("alternative_access_options"), [])
        options = {
            json.dumps(option, ensure_ascii=False, sort_keys=True): option
            for option in old_options + new_options if isinstance(option, dict)
        }
        payload["alternative_access_options"] = json.dumps(
            [options[key] for key in sorted(options)], ensure_ascii=False
        )
        for field in ("geography_basis", "metadata_provenance"):
            old_map = _json_value(existing.get(field), {})
            new_map = _json_value(payload.get(field), {})
            merged = {}
            for key in sorted(set(old_map) | set(new_map)):
                old_values = old_map.get(key, [])
                new_values = new_map.get(key, [])
                if not isinstance(old_values, list):
                    old_values = [old_values]
                if not isinstance(new_values, list):
                    new_values = [new_values]
                merged[key] = sorted({str(value) for value in old_values + new_values if value})
            payload[field] = json.dumps(merged, ensure_ascii=False)
        tags = set(_json_value(payload.get("geography_tags"), []))
        payload["geo_pr"] = max(int(existing.get("geo_pr") or 0), int(payload.get("geo_pr") or 0), int("Puerto Rico" in tags))
        payload["geo_us"] = max(int(existing.get("geo_us") or 0), int(payload.get("geo_us") or 0), int("United States" in tags))
        payload["geo_latam_caribbean"] = max(int(existing.get("geo_latam_caribbean") or 0), int(payload.get("geo_latam_caribbean") or 0), int("Latin America / Caribbean" in tags))
        payload["metadata_sources_count"] = max(int(existing.get("metadata_sources_count") or 1), int(payload.get("metadata_sources_count") or 1))


def upsert_papers(papers: Iterable[dict]):
    papers = list(papers)
    if not papers:
        return
    payloads = [_paper_payload(p) for p in papers]
    con = connect()
    _merge_provenance_payloads(con, payloads)
    greatest = "GREATEST" if con.engine == "postgres" else "MAX"
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
            f"cited_by_count={greatest}(COALESCE(papers.cited_by_count,0), excluded.cited_by_count)",
            f"relevance_score={greatest}(COALESCE(papers.relevance_score,0), excluded.relevance_score)",
            f"practical_score={greatest}(COALESCE(papers.practical_score,0), excluded.practical_score)",
            f"evidence_score={greatest}(COALESCE(papers.evidence_score,0), excluded.evidence_score)",
            f"recency_score={greatest}(COALESCE(papers.recency_score,0), excluded.recency_score)",
            "summary=CASE WHEN excluded.summary<>'' THEN excluded.summary ELSE papers.summary END",
            "why_it_matters=CASE WHEN excluded.why_it_matters<>'' THEN excluded.why_it_matters ELSE papers.why_it_matters END",
            "applications=CASE WHEN excluded.applications<>'' THEN excluded.applications ELSE papers.applications END",
            "limitations=CASE WHEN excluded.limitations<>'' THEN excluded.limitations ELSE papers.limitations END",
            "evidence_level=CASE WHEN excluded.evidence_level<>'' THEN excluded.evidence_level ELSE papers.evidence_level END",
            "evidence_type=CASE WHEN excluded.evidence_type<>'' AND excluded.evidence_type<>'unknown' THEN excluded.evidence_type ELSE papers.evidence_type END",
            "peer_review_status=CASE WHEN excluded.peer_review_status NOT IN ('','UNKNOWN') THEN excluded.peer_review_status ELSE papers.peer_review_status END",
            "publication_type=CASE WHEN excluded.publication_type<>'' THEN excluded.publication_type ELSE papers.publication_type END",
            "retraction_status=CASE WHEN excluded.retraction_status NOT IN ('','UNKNOWN') THEN excluded.retraction_status ELSE papers.retraction_status END",
            "correction_status=CASE WHEN excluded.correction_status NOT IN ('','UNKNOWN') THEN excluded.correction_status ELSE papers.correction_status END",
            f"doi_verified={greatest}(COALESCE(papers.doi_verified,0), excluded.doi_verified)",
            f"metadata_sources_count={greatest}(COALESCE(papers.metadata_sources_count,1), excluded.metadata_sources_count)",
            "metadata_provenance=CASE WHEN excluded.metadata_provenance<>'{}' THEN excluded.metadata_provenance ELSE papers.metadata_provenance END",
            "evidence_flags=CASE WHEN excluded.evidence_flags<>'[]' THEN excluded.evidence_flags ELSE papers.evidence_flags END",
            f"abstract_available={greatest}(COALESCE(papers.abstract_available,0), excluded.abstract_available)",
            "apa_citation=CASE WHEN excluded.apa_citation<>'' THEN excluded.apa_citation ELSE papers.apa_citation END",
            "geography_primary=CASE WHEN excluded.geography_confidence>=COALESCE(papers.geography_confidence,0) AND excluded.geography_primary<>'' THEN excluded.geography_primary ELSE papers.geography_primary END",
            "geography_tags=CASE WHEN excluded.geography_tags<>'[]' THEN excluded.geography_tags ELSE papers.geography_tags END",
            f"geography_confidence={greatest}(COALESCE(papers.geography_confidence,0), excluded.geography_confidence)",
            "geography_basis=CASE WHEN excluded.geography_basis<>'{}' THEN excluded.geography_basis ELSE papers.geography_basis END",
            "study_location=CASE WHEN excluded.study_location<>'' THEN excluded.study_location ELSE papers.study_location END",
            "author_affiliation_location=CASE WHEN excluded.author_affiliation_location<>'' THEN excluded.author_affiliation_location ELSE papers.author_affiliation_location END",
            "affiliation_locations=CASE WHEN excluded.affiliation_locations<>'[]' THEN excluded.affiliation_locations ELSE papers.affiliation_locations END",
            "publication_location=CASE WHEN excluded.publication_location<>'' THEN excluded.publication_location ELSE papers.publication_location END",
            "geographic_mentions=CASE WHEN excluded.geographic_mentions<>'[]' THEN excluded.geographic_mentions ELSE papers.geographic_mentions END",
            f"geo_pr={greatest}(COALESCE(papers.geo_pr,0), excluded.geo_pr)",
            f"geo_us={greatest}(COALESCE(papers.geo_us,0), excluded.geo_us)",
            f"geo_latam_caribbean={greatest}(COALESCE(papers.geo_latam_caribbean,0), excluded.geo_latam_caribbean)",
            "access_status=CASE WHEN excluded.access_status NOT IN ('','UNKNOWN') THEN excluded.access_status ELSE papers.access_status END",
            "best_access_url=CASE WHEN excluded.best_access_url<>'' THEN excluded.best_access_url ELSE papers.best_access_url END",
            "access_provider=CASE WHEN excluded.access_provider<>'' THEN excluded.access_provider ELSE papers.access_provider END",
            "access_type=CASE WHEN excluded.access_type<>'' THEN excluded.access_type ELSE papers.access_type END",
            f"requires_login={greatest}(COALESCE(papers.requires_login,0), excluded.requires_login)",
            f"institutional_access_possible={greatest}(COALESCE(papers.institutional_access_possible,0), excluded.institutional_access_possible)",
            f"open_access={greatest}(COALESCE(papers.open_access,0), excluded.open_access)",
            f"pdf_available={greatest}(COALESCE(papers.pdf_available,0), excluded.pdf_available)",
            f"html_available={greatest}(COALESCE(papers.html_available,0), excluded.html_available)",
            "doi_url=CASE WHEN excluded.doi_url<>'' THEN excluded.doi_url ELSE papers.doi_url END",
            "alternative_access_options=CASE WHEN excluded.alternative_access_options<>'[]' THEN excluded.alternative_access_options ELSE papers.alternative_access_options END",
            f"fulltext_available={greatest}(COALESCE(papers.fulltext_available,0), excluded.fulltext_available)",
            f"read_full={greatest}(COALESCE(papers.read_full,0), excluded.read_full)",
            f"favorite={greatest}(COALESCE(papers.favorite,0), excluded.favorite)",
            "updated_at=CURRENT_TIMESTAMP",
        ]
    )
    sql = f"""
        INSERT INTO papers ({col_sql}) VALUES ({val_sql})
        ON CONFLICT(id) DO UPDATE SET
        {update_sql}
    """
    try:
        con.executemany(sql, payloads)
        from evidence_pipeline import external_ids
        external_rows = []
        for paper, payload in zip(papers, payloads):
            for id_type, external_id in external_ids(paper).items():
                external_rows.append(
                    {
                        "paper_id": payload["id"], "id_type": id_type,
                        "external_id": external_id,
                        "source": str(paper.get("source") or ""),
                    }
                )
        if external_rows:
            con.executemany(
                """INSERT INTO paper_external_ids(paper_id,id_type,external_id,source)
                   VALUES(:paper_id,:id_type,:external_id,:source)
                   ON CONFLICT(id_type,external_id) DO UPDATE SET
                   paper_id=excluded.paper_id,
                   source=CASE WHEN excluded.source<>'' THEN excluded.source ELSE paper_external_ids.source END""",
                external_rows,
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    try:
        from platform_store import enqueue_enrichment
        enqueue_enrichment(payload["id"] for payload in payloads)
    except Exception:
        # Evidence is safely persisted; queue availability must not discard it.
        pass


def get_papers(limit: int = 500, favorites_only: bool = False):
    con = connect()
    where = "WHERE favorite=1" if favorites_only else ""
    rows = con.execute(
        f"SELECT * FROM papers {where} ORDER BY relevance_score DESC, published_date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_papers(
    *,
    limit: int = 50,
    offset: int = 0,
    query: str | None = None,
    source: str | None = None,
    year: int | None = None,
    geography: str | None = None,
    peer_reviewed: bool | None = None,
    open_access: bool | None = None,
    full_text: bool | None = None,
    evidence_type: str | None = None,
    retracted: bool | None = None,
    peer_review_status: str | None = None,
    access_status: str | None = None,
    retraction_status: str | None = None,
    favorites_only: bool = False,
):
    """Return a filtered page of papers using portable parameterized SQL."""
    conditions = []
    params: list[object] = []
    if favorites_only:
        conditions.append("favorite=1")
    if query:
        conditions.append(
            "("
            "LOWER(title) LIKE LOWER(?) OR "
            "LOWER(COALESCE(abstract,'')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(topics,'')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(journal,'')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(authors,'')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(doi,'')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(source,'')) LIKE LOWER(?)"
            ")"
        )
        pattern = f"%{query.strip()}%"
        params.extend((pattern,) * 7)
    if source:
        conditions.append("LOWER(source)=LOWER(?)")
        params.append(source.strip())
    if year is not None:
        conditions.append("year=?")
        params.append(int(year))
    geography_columns = {
        "puerto_rico": "geo_pr",
        "united_states": "geo_us",
        "latam_caribbean": "geo_latam_caribbean",
    }
    if geography is not None:
        if geography == "global":
            conditions.append("COALESCE(geo_pr,0)=0 AND COALESCE(geo_us,0)=0 AND COALESCE(geo_latam_caribbean,0)=0")
        else:
            column = geography_columns.get(geography)
            if column is None:
                raise ValueError("Unsupported geography filter")
            conditions.append(f"{column}=?")
            params.append(1)
    if peer_reviewed is not None:
        conditions.append("peer_review_status=?" if peer_reviewed else "peer_review_status<>?")
        params.append("CONFIRMED")
    if open_access is not None:
        conditions.append("access_status=?" if open_access else "access_status<>?")
        params.append("OPEN_ACCESS")
    if full_text is not None:
        conditions.append("fulltext_available=?")
        params.append(1 if full_text else 0)
    if evidence_type:
        conditions.append("UPPER(evidence_type)=UPPER(?)")
        params.append(evidence_type.strip())
    if retracted is not None:
        conditions.append("retraction_status=?" if retracted else "retraction_status<>?")
        params.append("RETRACTED")
    if peer_review_status:
        conditions.append("peer_review_status=?")
        params.append(peer_review_status)
    if access_status:
        conditions.append("access_status=?")
        params.append(access_status)
    if retraction_status:
        conditions.append("retraction_status=?")
        params.append(retraction_status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend((int(limit), int(offset)))
    con = connect()
    try:
        rows = con.execute(
            f"SELECT * FROM papers {where} "
            "ORDER BY relevance_score DESC, published_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


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
    survey_id = insert_returning_id(
        con,
        "INSERT INTO surveys(title,description) VALUES (?,?)",
        (title, description),
    )
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
    stats["puerto_rico"] = con.execute("SELECT COUNT(*) FROM papers WHERE geo_pr=1").fetchone()[0]
    stats["united_states"] = con.execute("SELECT COUNT(*) FROM papers WHERE geo_us=1").fetchone()[0]
    stats["latam_caribbean"] = con.execute("SELECT COUNT(*) FROM papers WHERE geo_latam_caribbean=1").fetchone()[0]
    stats["with_abstract"] = con.execute("SELECT COUNT(*) FROM papers WHERE LENGTH(COALESCE(abstract,''))>0").fetchone()[0]
    stats["with_doi"] = con.execute("SELECT COUNT(*) FROM papers WHERE LENGTH(COALESCE(doi,''))>0").fetchone()[0]
    stats["open_access"] = con.execute("SELECT COUNT(*) FROM papers WHERE access_status='OPEN_ACCESS'").fetchone()[0]
    stats["requires_login"] = con.execute("SELECT COUNT(*) FROM papers WHERE requires_login=1").fetchone()[0]
    stats["retracted"] = con.execute("SELECT COUNT(*) FROM papers WHERE retraction_status='RETRACTED'").fetchone()[0]
    stats["multi_source_metadata"] = con.execute("SELECT COUNT(*) FROM papers WHERE metadata_sources_count>1").fetchone()[0]
    con.close()
    return stats


def evidence_observability():
    """Return v21 corpus facets with one aggregate query (safe for polling)."""
    con = connect()
    try:
        row = con.execute(
            """SELECT
              COUNT(*) AS total_papers,
              COALESCE(SUM(CASE WHEN geo_pr=1 THEN 1 ELSE 0 END),0) AS puerto_rico,
              COALESCE(SUM(CASE WHEN geo_us=1 THEN 1 ELSE 0 END),0) AS united_states,
              COALESCE(SUM(CASE WHEN geo_latam_caribbean=1 THEN 1 ELSE 0 END),0) AS latam_caribbean,
              COALESCE(SUM(CASE WHEN COALESCE(geo_pr,0)=0 AND COALESCE(geo_us,0)=0 AND COALESCE(geo_latam_caribbean,0)=0 THEN 1 ELSE 0 END),0) AS global_or_unknown,
              COALESCE(SUM(CASE WHEN LENGTH(COALESCE(doi,''))>0 THEN 1 ELSE 0 END),0) AS with_doi,
              COALESCE(SUM(CASE WHEN LENGTH(COALESCE(abstract,''))>0 THEN 1 ELSE 0 END),0) AS with_abstract,
              COALESCE(SUM(CASE WHEN fulltext_available=1 THEN 1 ELSE 0 END),0) AS with_fulltext,
              COALESCE(SUM(CASE WHEN peer_review_status='CONFIRMED' THEN 1 ELSE 0 END),0) AS peer_reviewed,
              COALESCE(SUM(CASE WHEN UPPER(COALESCE(evidence_type,'')) IN ('PREPRINT','PREPRINT') OR peer_review_status='NOT_PEER_REVIEWED' THEN 1 ELSE 0 END),0) AS preprints,
              COALESCE(SUM(CASE WHEN UPPER(COALESCE(evidence_type,''))='SYSTEMATIC_REVIEW' THEN 1 ELSE 0 END),0) AS systematic_reviews,
              COALESCE(SUM(CASE WHEN UPPER(COALESCE(evidence_type,''))='META_ANALYSIS' THEN 1 ELSE 0 END),0) AS meta_analyses,
              COALESCE(SUM(CASE WHEN retraction_status='RETRACTED' THEN 1 ELSE 0 END),0) AS retracted,
              COALESCE(SUM(CASE WHEN access_status='OPEN_ACCESS' THEN 1 ELSE 0 END),0) AS open_access,
              COALESCE(SUM(CASE WHEN access_status='INSTITUTIONAL_ACCESS' THEN 1 ELSE 0 END),0) AS institutional_access,
              COALESCE(SUM(CASE WHEN access_status='PROVIDER_LOGIN' THEN 1 ELSE 0 END),0) AS provider_login,
              COALESCE(SUM(CASE WHEN access_status IN ('METADATA_ONLY','UNKNOWN') THEN 1 ELSE 0 END),0) AS metadata_only,
              COALESCE(SUM(CASE WHEN requires_login=1 THEN 1 ELSE 0 END),0) AS requires_login,
              COALESCE(SUM(CASE WHEN metadata_sources_count>1 THEN 1 ELSE 0 END),0) AS multi_source_metadata
              FROM papers"""
        ).fetchone()
        return {key: int(value or 0) for key, value in dict(row).items()}
    finally:
        con.close()
