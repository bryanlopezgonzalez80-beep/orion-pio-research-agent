from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

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
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    init_schema(con)
    try:
        yield con
        con.commit()
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
    return json.loads(row[0]) if row else None

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
    return not row or not row[0] or row[0] <= _iso()

def record_source_success(source, *, path=None):
    with connect(path) as con:
        con.execute("""INSERT INTO orion_source_health(source,last_status,last_error,success_count,failure_count,consecutive_failures,circuit_open_until,last_checked)
          VALUES(?,'ok','',1,0,0,NULL,?) ON CONFLICT(source) DO UPDATE SET
          last_status='ok',last_error='',success_count=success_count+1,consecutive_failures=0,circuit_open_until=NULL,last_checked=excluded.last_checked""",(source,_iso()))

def record_source_failure(source, error, *, path=None, threshold=3, cooldown_minutes=15):
    now=_utcnow()
    with connect(path) as con:
        row=con.execute("SELECT consecutive_failures FROM orion_source_health WHERE source=?",(source,)).fetchone()
        n=int(row[0] if row else 0)+1
        until=_iso(now+timedelta(minutes=cooldown_minutes)) if n>=threshold else None
        con.execute("""INSERT INTO orion_source_health(source,last_status,last_error,success_count,failure_count,consecutive_failures,circuit_open_until,last_checked)
          VALUES(?,'error',?,0,1,?,?,?) ON CONFLICT(source) DO UPDATE SET
          last_status='error',last_error=excluded.last_error,failure_count=failure_count+1,
          consecutive_failures=excluded.consecutive_failures,circuit_open_until=excluded.circuit_open_until,last_checked=excluded.last_checked""",
          (source,str(error)[:1000],n,until,_iso(now)))

def get_source_health(*, path=None):
    with connect(path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM orion_source_health ORDER BY source").fetchall()]

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
        return int(con.execute("SELECT id FROM orion_collections WHERE name=?",(name,)).fetchone()[0])

def get_collections(*, path=None):
    with connect(path) as con:
        return [dict(r) for r in con.execute("""SELECT c.*,COUNT(i.paper_id) AS item_count FROM orion_collections c
          LEFT JOIN orion_collection_items i ON i.collection_id=c.id GROUP BY c.id ORDER BY c.name""").fetchall()]

def add_to_collection(collection_id, paper_id, *, path=None):
    with connect(path) as con:
        con.execute("INSERT OR IGNORE INTO orion_collection_items(collection_id,paper_id,added_at) VALUES(?,?,?)",(int(collection_id),str(paper_id),_iso()))

def create_alert(name, query, domain="auto", sources=(), cadence="daily", *, path=None):
    if cadence not in {"daily","weekly"}: raise ValueError("Unsupported cadence")
    with connect(path) as con:
        cur=con.execute("INSERT INTO orion_alerts(name,query,domain,sources_json,cadence,enabled,created_at) VALUES(?,?,?,?,?,1,?)",
          (name.strip() or query.strip(),query.strip(),domain,json.dumps(list(sources),ensure_ascii=False),cadence,_iso()))
        return int(cur.lastrowid)

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

def platform_stats(*, path=None):
    with connect(path) as con:
        return {
          "searches":con.execute("SELECT COUNT(*) FROM orion_search_history").fetchone()[0],
          "collections":con.execute("SELECT COUNT(*) FROM orion_collections").fetchone()[0],
          "alerts":con.execute("SELECT COUNT(*) FROM orion_alerts WHERE enabled=1").fetchone()[0],
          "cache_entries":con.execute("SELECT COUNT(*) FROM orion_search_cache WHERE expires_at>?",(_iso(),)).fetchone()[0],
        }
