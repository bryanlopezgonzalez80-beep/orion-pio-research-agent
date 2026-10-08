# Independent harvesting

Daily Radar runs at 06:00 Puerto Rico (10:00 UTC), handling eight core topics and
due alerts. The complete Deep Harvest runs separately at 07:00 Puerto Rico
(11:00 UTC), covering the current taxonomy, journal watch and geographic
discovery. Both use the existing GitHub Actions runners and PostgreSQL database;
they do not depend on the Render web process staying awake.

The new Cloud Deep and Historical Harvest workflow also reserves four historical
slots, six hours apart: 04:23, 10:23, 16:23 and 22:23 Puerto Rico. Each historical
run targets **24 months**, with a 50-minute runtime budget and a default floor of
1940. An incomplete run retains its current month and completed checkpoints;
the next run resumes unfinished work rather than skipping or repeating completed
tasks. This is a target block size, not a guarantee that two years finish in one
slot. GitHub may delay scheduled starts.

## Pause and manual runs

The historical schedule is **paused by default**, respecting the user's latest
stop request. In GitHub Actions, open **Orion Cloud Deep and Historical Harvest**
and select **Run workflow**:

- `job=verify`, `historical_action=preserve`: check the database without harvesting.
- `job=deep`, `historical_action=preserve`: run the complete current sweep.
- `job=backfill`, `historical_action=preserve`: run one two-year historical block,
  without enabling later automatic blocks.
- `job=verify`, `historical_action=pause`: persistently pause future historical slots.
- `job=verify`, `historical_action=resume`: explicitly enable future historical slots.

Pausing the schedule does not cancel an already running task. Use GitHub's
**Cancel workflow** to interrupt an active cloud task; persisted checkpoints
allow later recovery. The Site's existing manual controls remain available.

## Coordination and status

The Daily and cloud workflows share a GitHub concurrency group. A PostgreSQL
session advisory lock also prevents API and cloud harvest workers from writing
at the same time. The session is checked during progress updates; a lost session
stops the job. Locks release automatically when a runner exits or is terminated.

The API checks the actual shared lock before declaring an external worker's
status abandoned. Partial runs report `partial_retryable`; a provider warning
reports `completed_with_warnings`. Failure summaries contain exception types and
counters, without connection strings or credentials.

The workflow uses the already configured `DATABASE_URL` and provider secrets.
It provisions no new service or database and performs no database migration.
An immediate Deep Harvest is triggered when these runner files are merged into
main. Historical work stays paused unless explicitly enabled.

## Rollback

Disable the new cloud workflow, then revert its PR. Do not delete PostgreSQL
settings, papers or checkpoints. The previous Daily behavior returns after the
revert; historical data already saved remains intact.
