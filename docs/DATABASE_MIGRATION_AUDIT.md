# Orion persistence audit

## Baseline

The Phase 3 branch was created from `origin/main` after Phase 1 and Phase 2 were merged. Before any change, `pio_dashboard.db` was 808 KiB with SHA-256 `f26d97cb4b4a1da1688dd96118d4a6ee221fd85703bb71f127bfeebe81962e52`. It must remain the rollback source and must not be deleted or overwritten.

Baseline row counts were: 149 papers, 19 cache entries, 8 search-history entries, 5 source-health entries, and 1 radar run. All other active tables contained zero rows.

## Active SQLite schema

| Table | Primary key | Important columns and constraints |
| --- | --- | --- |
| `papers` | text `id` | required title; research metadata; integer flags; numeric scores; created/updated timestamps |
| `clients` | integer auto ID | required name; contact/status fields |
| `projects` | integer auto ID | optional client FK; required name; status/value/due date |
| `proposals` | integer auto ID | optional client FK; required title; status/amount/follow-up |
| `generated_assets` | integer auto ID | required asset type; optional paper reference |
| `radar_runs` | integer auto ID | JSON text for sources/topics/errors; result counts |
| `surveys` | integer auto ID | required title |
| `survey_questions` | integer auto ID | required survey FK and question; scale bounds |
| `survey_responses` | integer auto ID | required survey FK and answers JSON text |
| `orion_search_history` | integer auto ID | required query/domain/JSON text/timestamp and result metrics |
| `orion_search_cache` | text cache key | source/query/payload and expiry timestamps |
| `orion_source_health` | text source | counters, circuit state, error and check timestamp |
| `orion_collections` | integer auto ID | unique required name, description and timestamp |
| `orion_collection_items` | collection + paper | collection FK with cascade and added timestamp |
| `orion_alerts` | integer auto ID | query/domain/sources/cadence/enabled/last run |
| `orion_settings` | text key | JSON value and updated timestamp |

The live SQLite schema has no explicit user-created indexes. The D1-oriented `site_migration/schema.sql` is a separate, partial browser-site schema; it uses different table names and user fields and is not the authoritative application migration source.

## Connection and transaction patterns

- `data_store.py` opens short-lived connections per operation and initializes its schema defensively.
- `platform_store.py` uses a context manager, WAL mode, foreign keys, and commit/rollback per operation.
- `daily_agent.py`, `weekly_agent.py`, `app.py`, and `orion_platform.py` call those stores rather than opening SQLite directly.
- Cache, health, alerts, collections, and history share `pio_dashboard.db` by default.

## PostgreSQL differences

- SQLite `?` placeholders become psycopg `%s` placeholders.
- `INTEGER PRIMARY KEY AUTOINCREMENT` becomes `BIGSERIAL PRIMARY KEY`.
- SQLite `REAL` becomes PostgreSQL `DOUBLE PRECISION`.
- SQLite `PRAGMA` and `sqlite_master` are engine-specific.
- `INSERT OR IGNORE` becomes `ON CONFLICT DO NOTHING`.
- SQLite `lastrowid` becomes `INSERT ... RETURNING id`.
- SQLite scalar `MAX(a,b)` becomes PostgreSQL `GREATEST(a,b)`.
- Existing JSON and timestamp values remain text in Phase 3 to preserve exact behavior and enable reversible migration without changing application semantics.
- Explicit migrated serial IDs require sequence synchronization after insertion.

## Risks

- Partial migration could break foreign-key relationships; therefore all writes run in one PostgreSQL transaction and roll back together.
- Existing destination rows may conflict; inserts are idempotent and never delete or overwrite them automatically.
- An invalid or leaked connection URL is a credential risk; it is read only from the environment and never returned by health/status output.
- Text timestamps depend on consistent ISO formatting, matching current application behavior.
- SQLite and PostgreSQL can diverge if both receive writes after cutover. During the compatibility period, choose one active engine per deployment.

## Migration plan

1. Create a consistent SQLite backup with SQLite's backup API.
2. Configure `DATABASE_URL` through the deployment secret manager.
3. Run the migration script with `--dry-run`; this performs no schema or data writes.
4. Inspect source/destination counts and resolve unexpected destination data.
5. Run `--verify` to understand current key-level differences.
6. With explicit human approval, run `--apply`; schema creation and all inserts share one transaction.
7. Run `--verify` again and run `scripts/db_status.py`.
8. Start one controlled Orion deployment with PostgreSQL and monitor behavior.
9. Retain SQLite and its backup throughout the compatibility period.

## Rollback

Stop the application, remove or disable `DATABASE_URL` in the deployment environment, and restart Orion. The application will immediately select the unchanged SQLite database. PostgreSQL data is not deleted by rollback. Restore from a verified SQLite backup only if the original file itself was damaged; never overwrite an active WAL database by direct file copy.

## Data that must not be lost

All rows and IDs in every active table must be preserved, including paper flags/analysis, CRM records, surveys and responses, generated assets, radar history, cache/history, source-health counters, collections/items, alerts, settings, timestamps, JSON text, and foreign-key relationships.
