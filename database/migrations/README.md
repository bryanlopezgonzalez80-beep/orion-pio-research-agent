# Orion database migrations

Production schema changes are reviewed and applied deliberately; the API's startup
path is not a substitute for migrations. Migration files in this directory are
ordered by their UTC timestamp and must be applied only after reviewing the
matching pull request and confirming the target Supabase project.

## 20261016_lock_orion_public_tables.sql

This migration secures the 20 confirmed Orion tables in `public`:

- Removes table privileges from PostgREST's `anon` and `authenticated` roles.
- Enables RLS without adding end-user policies, so those roles fail closed.
- Leaves the API's `postgres` connection and `service_role` path available; both
  were verified with `BYPASSRLS`.
- Revokes those API-role grants by default for future tables created by
  `postgres` in `public`.

The Orion Site contract routes browser requests through the Orion API and does not
connect to Supabase directly. If another trusted client is later introduced, give
it a narrowly scoped backend endpoint or a separately reviewed RLS policy; do not
restore broad table grants.

### Apply and verify

Rotate the exposed database password first and update Render's
`DATABASE_URL`. Then apply this SQL once to the intended production project
through the reviewed Supabase migration process. The connected migration tool
must be writable; do not apply the statements through an untracked workaround.

Verify the RLS flags for Orion tables with:

```sql
select c.relname, c.relrowsecurity
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
  and c.relname like 'orion_%'
order by c.relname;
```

Also verify `has_table_privilege('anon', ...)` and
`has_table_privilege('authenticated', ...)` are false for every listed table.
Re-run Supabase security advisors and smoke-test API health, radar status, search,
library reads/writes, Daily Radar, and Deep Harvest.

### Rollback

Do not automatically undo this security boundary. If a production client breaks,
identify that client and restore only the minimum needed path through an API or
reviewed RLS policy. Keep RLS enabled and avoid regranting broad table access.
