# Live harvest recovery

The existing single-writer coordinator still owns live and historical jobs. No
new service, database migration, schedule or paid infrastructure is introduced.

Live query attempts are recorded in `deep_harvest.query_retries` in the shared
settings store before calling providers. A query leaves that queue only after
its records are saved and the search reports no source errors. An interrupted
query therefore remains retryable. Writes remain at-least-once; paper upserts
handle duplicate records. This is a query retry queue, not a generic task system.

The next live sweep prioritizes queued queries whose cooldown has elapsed, then
performs the regular taxonomy rotation. Cooldown starts at five minutes,
increases with successive attempts, and is capped at 24 hours. A failed query is
attempted at most once per sweep. **The cooldown does not schedule a new run:**
retries occur when an existing scheduled or manual live sweep starts. Historical
backfill keeps its separate checkpoints and pause setting.

`queries_processed` counts attempts, not successful responses from every source.
`retry_queue_pending` counts queries requiring another attempt, including
interrupted requests. `retry_queue_deferred` is the subset whose cooldown has not
elapsed at the time of the snapshot. A nonempty queue makes the completed run
partial even if all taxonomy queries were attempted.

The queue stores only known taxonomy queries, attempt counts and retry timestamps;
it does not persist provider error bodies or credentials. Invalid state fails
closed instead of silently dropping pending work. Removed taxonomy queries are
ignored on subsequent runs. Reverting the change restores previous sweep
behavior while retaining all collected records and the unused queue setting.

Regression tests simulate a restart, provider failure, partial source response,
storage failure and repeated retry cooldowns. Production deployment requires the
repository's human review process.
