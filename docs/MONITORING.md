# Orion Monitoring and Observability

Phase 7 adds a read-only system monitor that runs independently in GitHub Actions once per hour. It checks the public Render health endpoint and, when `DATABASE_URL` is configured, opens a PostgreSQL transaction in read-only mode to collect safe operational metrics.

## Checks and severity

| Check | Evidence | Severity rules |
| --- | --- | --- |
| Orion API | `/health` HTTP status and sanitized JSON | Critical unless HTTP 200 reports `status=ok`, PostgreSQL, and reachable database. |
| PostgreSQL | Connection, read-only transaction, required tables | Critical if unavailable or required tables are missing. Skipped when `DATABASE_URL` is absent; SQLite is never used by this cloud check. |
| Papers | Row count and latest `updated_at` | Warning when no papers exist. |
| Daily Radar | Search-history count and latest `created_at` | Warning after 48 hours; critical after 72 hours. |
| Weekly Radar | Latest `radar_runs.run_at` | Warning after 9 days; critical after 14 days. |
| Source health | Status, consecutive failures, open circuits | Warning for failures; critical when a circuit breaker is open. |

The monitor never selects `last_error`, prints exception messages, or includes connection URLs, keys, tokens, or API response bodies. PostgreSQL statements are limited to `SET TRANSACTION READ ONLY` and `SELECT`; the transaction is rolled back and closed after collection.

## Run locally

Without database access, the database checks are explicitly marked `SKIPPED`:

```bash
python scripts/orion_health_check.py --output orion-health.json
```

The command prints a human summary and writes structured JSON. It exits nonzero only for an overall `CRITICAL` state, allowing warnings and intentionally skipped local database checks to remain visible without making local diagnostics unusable.

Do not put `DATABASE_URL` on the command line. For an authorized environment, supply it through the environment or a managed secret store.

## GitHub Actions

`.github/workflows/orion-health-monitor.yml` supports manual dispatch and runs at minute 17 of every hour. It uses `contents: read`, receives only `DATABASE_URL`, and uploads `artifacts/orion-health.json` for 30 days with `actions/upload-artifact@v4`.

The upload step uses `if: always()` so a critical monitor exit still preserves diagnostic JSON. Upload success cannot turn a failed health step green. The workflow never commits or pushes repository content.

## Current limits

Database timestamps are operational proxies for Daily and Weekly Radar completion; the monitor does not call the GitHub Runs API. Future observability can add authenticated workflow-run checks, alert delivery, historical metric storage, latency trends, and service-level objectives without changing this read-only core.
