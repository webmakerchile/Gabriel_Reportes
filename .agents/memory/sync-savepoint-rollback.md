---
name: sync_clientes savepoint vs global rollback
description: Why per-row inserts in ETL syncs must use SAVEPOINTs, not session-wide rollback, to avoid silent client loss.
---

# Per-row insert error handling in ETL syncs (sync_clientes)

When a loop inserts many rows in one session and commits once at the end, a
per-row `flush()` that fails on a unique constraint must be recovered with a
SAVEPOINT (`db.begin_nested()`), NOT `db.rollback()`.

**Why:** `db.rollback()` reverts the ENTIRE session, discarding every
already-flushed-but-uncommitted insert from the same run. In `sync_clientes`
this silently dropped a set of new clients each run (they were never retried),
so prod `clientes_finales` lagged Obuma by a fixed gap (~148) while
`sync_log` still reported `estado=ok, discrepancias=0`. Downstream effect: those
clients' sales rendered as placeholder "Cliente {id}" / "ID-{id}" in the
per-vendedor Excel evolution report because the real name lived only in Obuma.

**How to apply:**
- Wrap `add()`+`flush()` INSIDE `with db.begin_nested():`. `begin_nested()`
  flushes pending objects when it takes its snapshot, so the risky insert must be
  added *inside* the block (adding before it makes the failure happen at
  snapshot-entry, leaving the session in PendingRollbackError).
- Catch `IntegrityError` specifically (retry with a synthetic unique key, e.g.
  `OBU-{id}`); let other exceptions propagate so a real DB failure aborts the
  sync (estado=error) instead of being silently skipped.
- Track and surface a `skipped` count in the sync result / `_log_sync`
  discrepancias so partial failures aren't reported as a clean `ok`.
- `ventas_dte` table is empty in prod, and venta JSON `detalle` has no
  `cliente_razon_social` for many docs — the only client-name source is
  `clientes_finales` (populated by sync) or Obuma `clientes.findById`.
