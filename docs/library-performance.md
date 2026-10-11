# Library performance

The optional `cursor=start` parameter on GET `/api/v1/library` starts an archive scan ordered by immutable paper ID (descending). The response includes `metadata.next_cursor`; pass it unchanged to retrieve the next page. A null cursor marks completion. Cursor and nonzero offset cannot be combined. Cursor payloads are validated and bound as SQL parameters; they never contain executable SQL. Authentication and quotas are unchanged.

Legacy offset clients retain their existing relevance/date order. Cursor scans intentionally use the primary-key order to avoid traversing all preceding records and to avoid movement caused by relevance updates. New inserts ahead of a scan are visible on the next refresh; this is not a frozen database snapshot. The Site still orders its displayed articles separately. Existing local checkpoints without a cursor continue using the old order, preventing a mixed-order resume. No migration or data deletion is required.

Shared corpus and geographic aggregates are cached per database/process for at most 120 seconds, with a lock preventing simultaneous duplicate recalculations. Errors are not cached and values are copied before returning. Live run progress is read separately; its polling is unchanged. SQLite development bypasses this cache. Reverting the commit preserves legacy API behavior and stored data.
