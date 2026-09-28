# PostgreSQL setup and migration

## Configuration

`DATABASE_URL` is the connection string supplied by a PostgreSQL service. Orion accepts `postgresql://` and `postgres://`. Store the real value only in the local shell's secure environment or the deployment provider's secret manager.

Never commit, log, paste into reports, or include the value in screenshots or complete error messages. `.env.example` contains only an empty placeholder. Orion is provider-agnostic; any standards-compatible managed PostgreSQL service can be used.

Without `DATABASE_URL`, Orion continues to use `pio_dashboard.db` through SQLite.

## Backup SQLite

From the repository root:

```bash
python scripts/backup_sqlite.py --source pio_dashboard.db
```

The script uses SQLite's online backup API, validates the copy, and writes to the ignored `backups/` directory. It does not directly copy a potentially active WAL file.

## Inspect status

```bash
python scripts/db_status.py
```

The command reports engine, reachability, tables, row counts, and migration readiness without displaying the connection URL.

## Migration sequence

After configuring `DATABASE_URL` securely:

```bash
python scripts/migrate_sqlite_to_postgres.py --dry-run
python scripts/migrate_sqlite_to_postgres.py --verify
```

`--dry-run` is read-only and does not create PostgreSQL tables. `--verify` compares source keys, row contents, and counts against an existing destination. An empty new destination is expected to show missing rows before the first approved migration.

Only after reviewing the dry-run, backup, and destination should a human explicitly authorize:

```bash
python scripts/migrate_sqlite_to_postgres.py --apply
python scripts/migrate_sqlite_to_postgres.py --verify
python scripts/db_status.py
```

`--apply` creates missing tables, inserts rows with conflict-safe semantics, synchronizes serial sequences, validates source keys, and commits once. Any error triggers a full rollback. It never deletes destination rows or the SQLite source.

## Rollback to SQLite

1. Stop Orion to avoid concurrent writes.
2. Remove or disable `DATABASE_URL` in the environment; do not commit configuration changes containing it.
3. Restart Orion. SQLite is selected automatically.
4. Confirm with `python scripts/db_status.py`.

Keep `pio_dashboard.db` and the verified backup. Do not delete PostgreSQL during the initial rollback window; retaining both makes investigation and reconciliation possible.

## Health checks

The internal `check_database_health()` function and `scripts/db_status.py` return only non-sensitive status. A healthy result confirms a basic query, not application-level data parity; always run `--verify` after migration.
