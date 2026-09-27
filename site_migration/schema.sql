-- D1-compatible schema for Orion Research Platform.
CREATE TABLE IF NOT EXISTS papers (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors TEXT DEFAULT '',
  year INTEGER DEFAULT 0,
  published_date TEXT DEFAULT '',
  source TEXT DEFAULT '',
  journal TEXT DEFAULT '',
  work_type TEXT DEFAULT '',
  doi TEXT DEFAULT '',
  url TEXT DEFAULT '',
  oa_url TEXT DEFAULT '',
  pdf_url TEXT DEFAULT '',
  abstract TEXT DEFAULT '',
  topics TEXT DEFAULT '',
  discovered_via TEXT DEFAULT '',
  cited_by_count INTEGER DEFAULT 0,
  relevance_score REAL DEFAULT 0,
  practical_score REAL DEFAULT 0,
  evidence_score REAL DEFAULT 0,
  recency_score REAL DEFAULT 0,
  summary TEXT DEFAULT '',
  why_it_matters TEXT DEFAULT '',
  applications TEXT DEFAULT '',
  limitations TEXT DEFAULT '',
  evidence_level TEXT DEFAULT '',
  apa_citation TEXT DEFAULT '',
  favorite INTEGER DEFAULT 0,
  read_full INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_papers_date ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);

CREATE TABLE IF NOT EXISTS searches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL,
  domain TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  found INTEGER DEFAULT 0,
  unique_saved INTEGER DEFAULT 0,
  errors_json TEXT DEFAULT '[]',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id,name)
);

CREATE TABLE IF NOT EXISTS collection_items (
  collection_id INTEGER NOT NULL,
  paper_id TEXT NOT NULL,
  added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(collection_id,paper_id)
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  domain TEXT NOT NULL,
  sources_json TEXT NOT NULL DEFAULT '[]',
  cadence TEXT NOT NULL DEFAULT 'daily',
  enabled INTEGER NOT NULL DEFAULT 1,
  last_run TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);