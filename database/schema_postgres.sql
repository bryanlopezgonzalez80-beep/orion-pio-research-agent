CREATE TABLE IF NOT EXISTS papers (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors TEXT,
  year INTEGER,
  published_date TEXT,
  source TEXT,
  journal TEXT,
  work_type TEXT,
  doi TEXT,
  url TEXT,
  oa_url TEXT,
  pdf_url TEXT,
  abstract TEXT,
  topics TEXT,
  discovered_via TEXT,
  cited_by_count INTEGER DEFAULT 0,
  relevance_score DOUBLE PRECISION DEFAULT 0,
  practical_score DOUBLE PRECISION DEFAULT 0,
  evidence_score DOUBLE PRECISION DEFAULT 0,
  recency_score DOUBLE PRECISION DEFAULT 0,
  summary TEXT,
  why_it_matters TEXT,
  applications TEXT,
  limitations TEXT,
  evidence_level TEXT,
  evidence_type TEXT,
  peer_review_status TEXT DEFAULT 'UNKNOWN',
  publication_type TEXT,
  retraction_status TEXT DEFAULT 'UNKNOWN',
  correction_status TEXT DEFAULT 'UNKNOWN',
  doi_verified INTEGER DEFAULT 0,
  metadata_sources_count INTEGER DEFAULT 1,
  metadata_provenance TEXT DEFAULT '{}',
  evidence_flags TEXT DEFAULT '[]',
  abstract_available INTEGER DEFAULT 0,
  apa_citation TEXT,
  geography_primary TEXT,
  geography_tags TEXT,
  geography_confidence DOUBLE PRECISION DEFAULT 0,
  geography_basis TEXT,
  study_location TEXT,
  author_affiliation_location TEXT,
  affiliation_locations TEXT,
  publication_location TEXT,
  geographic_mentions TEXT,
  geo_pr INTEGER DEFAULT 0,
  geo_us INTEGER DEFAULT 0,
  geo_latam_caribbean INTEGER DEFAULT 0,
  access_status TEXT DEFAULT 'UNKNOWN',
  best_access_url TEXT,
  access_provider TEXT,
  access_type TEXT,
  requires_login INTEGER DEFAULT 0,
  institutional_access_possible INTEGER DEFAULT 0,
  open_access INTEGER DEFAULT 0,
  pdf_available INTEGER DEFAULT 0,
  html_available INTEGER DEFAULT 0,
  doi_url TEXT,
  alternative_access_options TEXT DEFAULT '[]',
  fulltext_available INTEGER DEFAULT 0,
  read_full INTEGER DEFAULT 0 CHECK (read_full IN (0, 1)),
  favorite INTEGER DEFAULT 0 CHECK (favorite IN (0, 1)),
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text),
  updated_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);
ALTER TABLE papers ADD COLUMN IF NOT EXISTS evidence_type TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS peer_review_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS publication_type TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS retraction_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS correction_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS doi_verified INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS metadata_sources_count INTEGER DEFAULT 1;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS metadata_provenance TEXT DEFAULT '{}';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS evidence_flags TEXT DEFAULT '[]';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS abstract_available INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geography_primary TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geography_tags TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geography_confidence DOUBLE PRECISION DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geography_basis TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS study_location TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS author_affiliation_location TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS affiliation_locations TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS publication_location TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geographic_mentions TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geo_pr INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geo_us INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS geo_latam_caribbean INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS access_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS best_access_url TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS access_provider TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS access_type TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS requires_login INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS institutional_access_possible INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS open_access INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS pdf_available INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS html_available INTEGER DEFAULT 0;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS doi_url TEXT;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS alternative_access_options TEXT DEFAULT '[]';
ALTER TABLE papers ADD COLUMN IF NOT EXISTS fulltext_available INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_papers_date ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_library_order ON papers(relevance_score DESC, published_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
CREATE INDEX IF NOT EXISTS idx_papers_geo_pr ON papers(geo_pr) WHERE geo_pr = 1;
CREATE INDEX IF NOT EXISTS idx_papers_geo_us ON papers(geo_us) WHERE geo_us = 1;
CREATE INDEX IF NOT EXISTS idx_papers_geo_latam ON papers(geo_latam_caribbean) WHERE geo_latam_caribbean = 1;
CREATE INDEX IF NOT EXISTS idx_papers_access_status ON papers(access_status);
CREATE INDEX IF NOT EXISTS idx_papers_peer_review ON papers(peer_review_status);

CREATE TABLE IF NOT EXISTS paper_external_ids (
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  id_type TEXT NOT NULL,
  external_id TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text),
  PRIMARY KEY(id_type, external_id)
);

CREATE TABLE IF NOT EXISTS clients (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  organization TEXT,
  email TEXT,
  phone TEXT,
  status TEXT DEFAULT 'Prospecto',
  notes TEXT,
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE TABLE IF NOT EXISTS projects (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  name TEXT NOT NULL,
  category TEXT,
  status TEXT DEFAULT 'Idea',
  due_date TEXT,
  value DOUBLE PRECISION DEFAULT 0,
  notes TEXT,
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE TABLE IF NOT EXISTS proposals (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  title TEXT NOT NULL,
  status TEXT DEFAULT 'Borrador',
  amount DOUBLE PRECISION DEFAULT 0,
  sent_date TEXT,
  followup_date TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE TABLE IF NOT EXISTS generated_assets (
  id BIGSERIAL PRIMARY KEY,
  paper_id TEXT,
  asset_type TEXT NOT NULL,
  title TEXT,
  content TEXT,
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE TABLE IF NOT EXISTS radar_runs (
  id BIGSERIAL PRIMARY KEY,
  run_at TEXT DEFAULT (CURRENT_TIMESTAMP::text),
  sources TEXT,
  topics TEXT,
  found INTEGER DEFAULT 0,
  unique_saved INTEGER DEFAULT 0,
  errors TEXT
);
CREATE TABLE IF NOT EXISTS surveys (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE TABLE IF NOT EXISTS survey_questions (
  id BIGSERIAL PRIMARY KEY,
  survey_id BIGINT NOT NULL REFERENCES surveys(id),
  question_text TEXT NOT NULL,
  scale_min INTEGER DEFAULT 1,
  scale_max INTEGER DEFAULT 5
);
CREATE TABLE IF NOT EXISTS survey_responses (
  id BIGSERIAL PRIMARY KEY,
  survey_id BIGINT NOT NULL REFERENCES surveys(id),
  respondent_label TEXT,
  answers_json TEXT NOT NULL,
  created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS orion_search_history (
  id BIGSERIAL PRIMARY KEY,
  query TEXT NOT NULL,
  domain TEXT NOT NULL,
  sources_json TEXT NOT NULL DEFAULT '[]',
  found INTEGER NOT NULL DEFAULT 0,
  unique_saved INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  errors_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orion_search_cache (
  cache_key TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  query TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orion_cache_expiry ON orion_search_cache(expires_at);
CREATE TABLE IF NOT EXISTS orion_source_health (
  source TEXT PRIMARY KEY,
  last_status TEXT NOT NULL DEFAULT 'unknown',
  last_error TEXT NOT NULL DEFAULT '',
  success_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  circuit_open_until TEXT,
  last_checked TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orion_source_metrics (
  source TEXT PRIMARY KEY, requests INTEGER NOT NULL DEFAULT 0,
  successes INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
  rate_limits INTEGER NOT NULL DEFAULT 0, latency_ms INTEGER NOT NULL DEFAULT 0,
  records_received INTEGER NOT NULL DEFAULT 0, unique_records INTEGER NOT NULL DEFAULT 0,
  last_success TEXT, last_failure TEXT, health_status TEXT NOT NULL DEFAULT 'INACTIVE'
);
CREATE TABLE IF NOT EXISTS orion_harvest_checkpoints (
  month TEXT NOT NULL, provider TEXT NOT NULL, task_type TEXT NOT NULL,
  task_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
  attempts INTEGER NOT NULL DEFAULT 0, records_received INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
  PRIMARY KEY(month,provider,task_type,task_key)
);
CREATE TABLE IF NOT EXISTS orion_enrichment_queue (
  paper_id TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT, last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orion_collections (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orion_collection_items (
  collection_id BIGINT NOT NULL REFERENCES orion_collections(id) ON DELETE CASCADE,
  paper_id TEXT NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY(collection_id, paper_id)
);
CREATE TABLE IF NOT EXISTS orion_alerts (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  domain TEXT NOT NULL DEFAULT 'auto',
  sources_json TEXT NOT NULL DEFAULT '[]',
  cadence TEXT NOT NULL DEFAULT 'daily' CHECK (cadence IN ('daily', 'weekly')),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  last_run TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orion_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
