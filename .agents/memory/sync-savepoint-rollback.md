---
name: ETL per-row savepoint error handling
description: Why per-row INSERTs AND UPDATEs in ETL syncs must use per-item SAVEPOINTs with flush + explicit state cleanup (expire/expunge), never a session-wide rollback.
---

# Per-row error handling in ETL syncs (sync_clientes pattern)

When a loop mutates many rows in one session and commits once at the end, a
per-row failure on a unique constraint must be recovered with a SAVEPOINT
(`db.begin_nested()`) wrapping an **immediate per-item flush**, NOT a session-wide
`db.rollback()`. This applies to BOTH the insert path (new objects) and the
update path (existing/persistent objects).

**Why:**
- `db.rollback()` reverts the ENTIRE session, discarding every
  already-flushed-but-uncommitted change from the same run. Those rows are never
  retried, so the table silently lags the source while the sync log still reports
  a clean `ok`.
- Wrapping only the insert path in a savepoint but leaving the update path as bare
  attribute assignments (under `autoflush=False`) is worse: the dirty UPDATE is
  flushed lazily (next item's savepoint or the final commit). If the source feeds
  a duplicate of a unique key (e.g. the same rut on two clients), that deferred
  UPDATE violates the constraint. A savepoint rollback does NOT un-dirty a
  persistent object, so it re-flushes on the next item, fails again, and poisons
  the transaction → the final commit raises and the whole step crashes.
- A crashing sync step is especially damaging when downstream dispatch is
  abort-on-failure: one poisoned client sync blocks all report emails too.

**How to apply:**
- Wrap each item's mutation + `flush()` inside `with db.begin_nested():`. Flushing
  per item also makes the in-loop "is this key already taken?" SELECT correct: a
  flushed-but-uncommitted row IS visible to later SELECTs in the same transaction
  (a deferred change under `autoflush=False` is NOT). This largely PREVENTS the
  duplicate-key collision instead of only catching it.
- Catch `IntegrityError` specifically; retry once with a synthetic unique key. Let
  other exceptions propagate so a real DB failure aborts the sync rather than being
  silently skipped.
- After a savepoint failure, clean up object state by type:
  - PERSISTENT (update path): the object stays dirty after savepoint rollback —
    you MUST `db.expire(obj)` to discard the pending change before retrying, or it
    re-flushes and re-fails forever.
  - NEW (insert path): savepoint rollback normally auto-expunges it (transient
    again), so re-adding works. For version-robust symmetry, guard the retry:
    `if obj in db: db.expunge(obj)` before re-`add`, so no pending insert survives.
- Track and surface a `skipped` count in the result and sync log so partial
  failures aren't reported as clean.
- Self-healing of stale source data only happens when the sync actually RUNS
  (scheduler or a manual dashboard trigger); if the API/sync endpoints aren't
  publicly reachable, an external curl can't kick it off.

**Production lag trap (observed in prod):** a merged sync fix does NOTHING for the
scheduled reports until the user REPUBLISHES. The deployment is a VM running the
last `Published your App` commit, not `main`. Symptom: reports stop arriving on a
given morning; deployment logs show the daily cron firing then
`Reporte ... sync inmediato FALLO -- NO se envia ningun correo` with a
`UniqueViolation` traceback whose line numbers DON'T match current `sync_service.py`
(proof prod runs older code). To confirm, compare `git log --oneline`: if the fix
commit is ABOVE the last `Published your App`, prod is stale → tell user to redeploy.
The fix already in code is correct; the action is republish, not another code change.
