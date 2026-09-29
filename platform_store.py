from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from database.connection import (
    connect_database,
    ensure_postgres_schema,
    first_value,
    insert_returning_id,
)

DEFAULT_DB = Path(os.getenv("ORION_DB_PATH", "pio_dashboard.db"))

def _utcnow():
    return datetime.now(timezone.utc)

def _iso(dt=None):
    return (dt or _utcnow()).isoformat(timespec="seconds")

def db_path():
    return Path(os.getenv("ORION_DB_PATH", str(DEFAULT_DB)))

@contextmanager
def connect(path=None):
    p = Path(path) if path else db_path()
    con = connect_database(
        sqlite_path=p,
        force_sqlite=path is not None,
        sqlite_foreign_keys=True,
    )
    if con.engine == "postgres":
        ensure_postgres_schema(con)
        con.commit()
    else:
        con.execute("PRAGMA journal_mode=WAL")
        init_schema(con)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init_schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS orion_search_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT NOT NULL, domain TEXT NOT NULL,
      sources_json TEXT NOT NULL DEFAULT '[]', found INTEGER NOT NULL DEFAULT 0,
      unique_saved INTEGER NOT NULL DEFAULT 0, duration_ms INTEGER NOT NULL DEFAULT 0,
      errors_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orion_search_cache(
      cache_key TEXT PRIMARY KEY, source TEXT NOT NULL, query TEXT NOT NULL,
      payload_json TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orion_source_health(
      source TEXT PRIMARY KEY, last_status TEXT NOT NULL DEFAULT 'unknown',
      last_error TEXT NOT NULL DEFAULT '', success_count INTEGER NOT NULL DEFAULT 0,
      failure_count INTEGER NOT NULL DEFAULT 0, consecutive_failures INTEGER NOT NULL DEFAULT 0,
      circuit_open_until TEXT, last_checked TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orion_source_metrics(
      source TEXT PRIMARY KEY, requests INTEGER NOT NULL DEFAULT 0,
      successes INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
      rate_limits INTEGER NOT NULL DEFAULT 0, latency_ms INTEGER NOT NULL DEFAULT 0,
      records_received INTEGER NOT NULL DEFAULT 0, unique_records INTEGER NOT NULL DEFAULT 0,
      last_success TEXT, last_failure TEXT, health_status TEXT NOT NULL DEFAULT 'INACTIVE');
    CREATE TABLE IF NOT EXISTS orion_harvest_checkpoints(
      month TEXT NOT NULL, provider TEXT NOT NULL, task_type TEXT NOT NULL,
      task_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
      attempts INTEGER NOT NULL DEFAULT 0, records_received INTEGER NOT NULL DEFAULT 0,
      last_error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
      PRIMARY KEY(month,provider,task_type,task_key));
    CREATE TABLE IF NOT EXISTS orion_enrichment_queue(
      paper_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'PENDING',
      attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT,
      last_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orion_collections(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
      description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orion_collection_items(
      collection_id INTEGER NOT NULL, paper_id TEXT NOT NULL, added_at TEXT NOT NULL,
      PRIMARY KEY(collection_id,paper_id),
      FOREIGN KEY(collection_id) REFERENCES orion_collections(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS orion_alerts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, query TEXT NOT NULL,
      domain TEXT NOT NULL DEFAULT 'auto', sources_json TEXT NOT NULL DEFAULT '[]',
      cadence TEXT NOT NULL DEFAULT 'daily', enabled INTEGER NOT NULL DEFAULT 1,
      last_run TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orion_settings(
      key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)

def make_cache_key(source, query, days, per_source):
    raw = json.dumps({"source":source,"query":query.strip().casefold(),"days":int(days),"per_source":int(per_source)}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def get_cache(source, query, days, per_source, *, path=None):
    key = make_cache_key(source, query, days, per_source)
    with connect(path) as con:
        row = con.execute("SELECT payload_json FROM orion_search_cache WHERE cache_key=? AND expires_at>?", (key,_iso())).fetchone()
    return json.loads(first_value(row)) if row else None

def set_cache(source, query, days, per_source, payload, ttl_hours=8, *, path=None):
    key = make_cache_key(source, query, days, per_source)
    now = _utcnow()
    with connect(path) as con:
        con.execute("""INSERT INTO orion_search_cache(cache_key,source,query,payload_json,created_at,expires_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET
          payload_json=excluded.payload_json,created_at=excluded.created_at,expires_at=excluded.expires_at""",
          (key,source,query,json.dumps(payload,ensure_ascii=False),_iso(now),_iso(now+timedelta(hours=ttl_hours))))

def purge_expired_cache(*, path=None):
    with connect(path) as con:
        cur=con.execute("DELETE FROM orion_search_cache WHERE expires_at<=?",(_iso(),))
        return int(cur.rowcount or 0)

def source_available(source, *, path=None):
    with connect(path) as con:
        row=con.execute("SELECT circuit_open_until FROM orion_source_health WHERE source=?",(source,)).fetchone()
    value = first_value(row)
    return not row or not value or value <= _iso()

def record_source_success(source, *, path=None):
    with connect(path) as con:
        con.execute("""INSERT INTO orion_source_health(source,last_status,last_error,success_count,failure_count,consecutive_failures,circuit_open_until,last_checked)
          VALUES(?,'ok','',1,0,0,NULL,?) ON CONFLICT(source) DO UPDATE SET
          last_status=excluded.last_status,last_error=excluded.last_error,
          success_count=COALESCE(orion_source_health.success_count,0)+1,
          consecutive_failures=excluded.consecutive_failures,
          circuit_open_until=excluded.circuit_open_until,last_checked=excluded.last_checked""",(source,_iso()))

def record_source_inactive(source, *, path=None):
    """Mark an optional/unconfigured provider inactive without fabricating success."""
    with connect(path) as con:
        con.execute(
            """INSERT INTO orion_source_health(source,last_status,last_error,success_count,failure_count,consecutive_failures,circuit_open_until,last_checked)
               VALUES(?,'inactive','',0,0,0,NULL,?) ON CONFLICT(source) DO UPDATE SET
               last_status=excluded.last_status,last_error=excluded.last_error,
               consecutive_failures=excluded.consecutive_failures,
               circuit_open_until=excluded.circuit_open_until,last_checked=excluded.last_checked""",
            (source, _iso()),
        )


def record_source_failure(source, error, *, path=None, threshold=3, cooldown_minutes=15):
    now=_utcnow()
    with connect(path) as con:
        row=con.execute("SELECT consecutive_failures FROM orion_source_health WHERE source=?",(source,)).fetchone()
        n=int(first_value(row) if row else 0)+1
        until=_iso(now+timedelta(minutes=cooldown_minutes)) if n>=threshold else None
        con.execute("""INSERT INTO orion_source_health(source,last_status,last_error,success_count,failure_count,consecutive_failures,circuit_open_until,last_checked)
          VALUES(?,'error',?,0,1,?,?,?) ON CONFLICT(source) DO UPDATE SET
          last_status=excluded.last_status,last_error=excluded.last_error,
          failure_count=COALESCE(orion_source_health.failure_count,0)+1,
          consecutive_failures=excluded.consecutive_failures,circuit_open_until=excluded.circuit_open_until,last_checked=excluded.last_checked""",
          (source,str(error)[:1000],n,until,_iso(now)))

def get_source_health(*, path=None):
    with connect(path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM orion_source_health ORDER BY source").fetchall()]


def record_source_metrics(source, *, requests=0, successes=0, failures=0, rate_limits=0, latency_ms=0, records_received=0, unique_records=0, health_status="HEALTHY", path=None):
    now = _iso()
    with connect(path) as con:
        con.execute(
            """INSERT INTO orion_source_metrics(source,requests,successes,failures,rate_limits,latency_ms,records_received,unique_records,last_success,last_failure,health_status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET
               requests=orion_source_metrics.requests+excluded.requests,
               successes=orion_source_metrics.successes+excluded.successes,
               failures=orion_source_metrics.failures+excluded.failures,
               rate_limits=orion_source_metrics.rate_limits+excluded.rate_limits,
               latency_ms=excluded.latency_ms,
               records_received=orion_source_metrics.records_received+excluded.records_received,
               unique_records=orion_source_metrics.unique_records+excluded.unique_records,
               last_success=CASE WHEN excluded.successes>0 THEN excluded.last_success ELSE orion_source_metrics.last_success END,
               last_failure=CASE WHEN excluded.failures>0 THEN excluded.last_failure ELSE orion_source_metrics.last_failure END,
               health_status=excluded.health_status""",
            (source, int(requests), int(successes), int(failures), int(rate_limits), int(latency_ms), int(records_received), int(unique_records), now if successes else None, now if failures else None, health_status),
        )


def get_source_metrics(*, path=None):
    with connect(path) as con:
        return [dict(row) for row in con.execute("SELECT * FROM orion_source_metrics ORDER BY source").fetchall()]


def get_checkpoint(month, provider, task_type, task_key, *, path=None):
    with connect(path) as con:
        row = con.execute(
            "SELECT * FROM orion_harvest_checkpoints WHERE month=? AND provider=? AND task_type=? AND task_key=?",
            (month, provider, task_type, task_key),
        ).fetchone()
    return dict(row) if row else None


def set_checkpoint(month, provider, task_type, task_key, status, *, records_received=0, error="", path=None):
    allowed = {"PENDING", "RUNNING", "COMPLETED", "RATE_LIMITED", "FAILED_RETRYABLE", "FAILED_FINAL"}
    if status not in allowed:
        raise ValueError("Unsupported checkpoint status")
    with connect(path) as con:
        con.execute(
            """INSERT INTO orion_harvest_checkpoints(month,provider,task_type,task_key,status,attempts,records_received,last_error,updated_at)
               VALUES(?,?,?,?,?,CASE WHEN ?='RUNNING' THEN 1 ELSE 0 END,?,?,?) ON CONFLICT(month,provider,task_type,task_key) DO UPDATE SET
               status=excluded.status,attempts=orion_harvest_checkpoints.attempts+CASE WHEN excluded.status='RUNNING' THEN 1 ELSE 0 END,
               records_received=excluded.records_received,last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (month, provider, task_type, task_key, status, status, int(records_received), str(error)[:500], _iso()),
        )


def checkpoint_summary(*, path=None):
    with connect(path) as con:
        rows = con.execute(
            "SELECT month,status,COUNT(*) AS total FROM orion_harvest_checkpoints GROUP BY month,status ORDER BY month DESC,status"
        ).fetchall()
    return [dict(row) for row in rows]


def enqueue_enrichment(paper_ids, *, path=None):
    now = _iso()
    rows = [
        {"paper_id": str(paper_id), "created_at": now, "updated_at": now}
        for paper_id in dict.fromkeys(paper_ids)
        if str(paper_id or "").strip()
    ]
    if not rows:
        return 0
    with connect(path) as con:
        con.executemany(
            """INSERT INTO orion_enrichment_queue(paper_id,status,attempts,last_error,created_at,updated_at)
               VALUES(:paper_id,'PENDING',0,'',:created_at,:updated_at)
               ON CONFLICT(paper_id) DO NOTHING""",
            rows,
        )
    return len(rows)


def enrichment_summary(*, path=None):
    with connect(path) as con:
        rows = con.execute(
            "SELECT status,COUNT(*) AS total FROM orion_enrichment_queue GROUP BY status ORDER BY status"
        ).fetchall()
    counts = {str(row["status"]): int(row["total"] or 0) for row in rows}
    return {
        "completed": counts.get("COMPLETED", 0),
        "pending": sum(counts.get(status, 0) for status in ("PENDING", "RUNNING", "FAILED_RETRYABLE")),
        "by_status": counts,
    }

def log_search(query, domain, sources:Iterable[str], found, unique_saved, duration_ms, errors, *, path=None):
    with connect(path) as con:
        con.execute("INSERT INTO orion_search_history(query,domain,sources_json,found,unique_saved,duration_ms,errors_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
          (query,domain,json.dumps(list(sources),ensure_ascii=False),int(found),int(unique_saved),int(duration_ms),json.dumps(list(errors),ensure_ascii=False),_iso()))

def get_search_history(limit=50, *, path=None):
    with connect(path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM orion_search_history ORDER BY id DESC LIMIT ?",(int(limit),)).fetchall()]

def create_collection(name, description="", *, path=None):
    name=name.strip()
    if not name: raise ValueError("Collection name cannot be empty")
    with connect(path) as con:
        con.execute("INSERT INTO orion_collections(name,description,created_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET description=excluded.description",(name,description.strip(),_iso()))
        return int(first_value(con.execute("SELECT id FROM orion_collections WHERE name=?",(name,)).fetchone()))

def get_collections(*, path=None):
    with connect(path) as con:
        return [dict(r) for r in con.execute("""SELECT c.*,COUNT(i.paper_id) AS item_count FROM orion_collections c
          LEFT JOIN orion_collection_items i ON i.collection_id=c.id GROUP BY c.id ORDER BY c.name""").fetchall()]

def add_to_collection(collection_id, paper_id, *, path=None):
    with connect(path) as con:
        if con.engine == "postgres":
            sql = "INSERT INTO orion_collection_items(collection_id,paper_id,added_at) VALUES(?,?,?) ON CONFLICT(collection_id,paper_id) DO NOTHING"
        else:
            sql = "INSERT OR IGNORE INTO orion_collection_items(collection_id,paper_id,added_at) VALUES(?,?,?)"
        con.execute(sql,(int(collection_id),str(paper_id),_iso()))

def create_alert(name, query, domain="auto", sources=(), cadence="daily", *, path=None):
    if cadence not in {"daily","weekly"}: raise ValueError("Unsupported cadence")
    with connect(path) as con:
        return insert_returning_id(
          con,
          "INSERT INTO orion_alerts(name,query,domain,sources_json,cadence,enabled,created_at) VALUES(?,?,?,?,?,1,?)",
          (name.strip() or query.strip(),query.strip(),domain,json.dumps(list(sources),ensure_ascii=False),cadence,_iso()),
        )

def get_alerts(enabled_only=False, *, path=None):
    where="WHERE enabled=1" if enabled_only else ""
    with connect(path) as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM orion_alerts {where} ORDER BY id DESC").fetchall()]

def alerts_due(*, path=None):
    now=_utcnow(); due=[]
    for a in get_alerts(True,path=path):
        if not a.get("last_run"): due.append(a); continue
        try:
            last=datetime.fromisoformat(a["last_run"])
            if last.tzinfo is None: last=last.replace(tzinfo=timezone.utc)
        except Exception:
            due.append(a); continue
        if now-last >= timedelta(days=1 if a["cadence"]=="daily" else 7): due.append(a)
    return due

def mark_alert_run(alert_id, *, path=None):
    with connect(path) as con:
        con.execute("UPDATE orion_alerts SET last_run=? WHERE id=?",(_iso(),int(alert_id)))

def get_setting(key, default=None, *, path=None):
    with connect(path) as con:
        row = con.execute(
            "SELECT value_json FROM orion_settings WHERE key=?",
            (str(key),),
        ).fetchone()
    if not row:
        return default
    try:
        return json.loads(first_value(row))
    except Exception:
        return default


def set_setting(key, value, *, path=None):
    with connect(path) as con:
        con.execute(
            """INSERT INTO orion_settings(key,value_json,updated_at)
               VALUES(?,?,?)
               ON CONFLICT(key) DO UPDATE SET
               value_json=excluded.value_json,updated_at=excluded.updated_at""",
            (str(key), json.dumps(value, ensure_ascii=False), _iso()),
        )


def platform_stats(*, path=None):
    with connect(path) as con:
        return {
          "searches":first_value(con.execute("SELECT COUNT(*) FROM orion_search_history").fetchone()),
          "collections":first_value(con.execute("SELECT COUNT(*) FROM orion_collections").fetchone()),
          "alerts":first_value(con.execute("SELECT COUNT(*) FROM orion_alerts WHERE enabled=1").fetchone()),
          "cache_entries":first_value(con.execute("SELECT COUNT(*) FROM orion_search_cache WHERE expires_at>?",(_iso(),)).fetchone()),
        }
