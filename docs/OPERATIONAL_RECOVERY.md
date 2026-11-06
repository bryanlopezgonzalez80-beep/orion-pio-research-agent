# Operational recovery — 2026-11-06

Daily Radar, weekly Radar, cloud harvest and periodic health monitoring are intentionally manual-only. Keep workflow_dispatch; do not restore schedules merely to make tests pass. CodeQL and dependency auditing remain scheduled.

The Supabase restore operation reported that the 2.0 GB database cannot be restored on the Free Plan. Restoring the existing database requires a paid-plan decision or a separately reviewed export/migration plan. Do not replace it with an empty database or delete research data.

The Site uses D1 separately. Recover and verify each datastore independently. Before resuming writers, confirm the authoritative database, a restorable backup, read/write health, and credential configuration. Test a controlled synthetic record and its cleanup only with explicit approval; do not use real user records.

The production container now uses the same Python 3.12 minor version as CI and defaults ORION_ENV to production. Before deploying, ensure a minimum 32-character ORION_API_KEY and explicit HTTPS ORION_ALLOWED_ORIGINS are configured. Missing configuration must stop startup, not expose an unauthenticated API. Local development retains its existing defaults.

The tracked pio_dashboard.db was not deleted, overwritten or migrated. New database files are ignored. Make the repository private and review historical data exposure separately; ignoring an already tracked file does not remove it or its history.

After the code review and successful CI, configure Render to deploy only after CI checks pass. Validate /health, a 401 from a protected route without credentials, and an authenticated read. A 200 health response with status=degraded means reads may work but writers are not ready; keep harvests paused.

Rollback: revert the reviewed commit. No production data or schema changes are part of this change. Reverting the container security default must not be used to bypass missing credentials.
