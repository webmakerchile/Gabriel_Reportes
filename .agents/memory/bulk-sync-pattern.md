---
name: Bulk upsert pattern for Obuma ETL syncs
description: How to convert row-by-row ORM syncs to bulk mappings without changing semantics, and how to test them with real savepoints on sqlite.
---

# Bulk upsert pattern (proven twice: ventas, then clientes+cartera)

**Rule:** Any `sync_*` in the ETL that does per-item SELECT/flush against the DB will eventually become an hours-long bottleneck in prod (~464 rows/min ORM vs seconds in bulk). Convert to: 1 lightweight preload query (only key columns, never full ORM objects), resolve all conflicts in memory, then flush with `bulk_update_mappings`/`bulk_insert_mappings` in batches of 1000-2000.

**Why:** Twice the scheduled reports arrived hours late because a sync inside `sync_for_report` ran O(n) queries or O(n) ORM UPDATEs. The client's hard deadline (Monday cobranza email before 09:00) only holds if syncs finish in minutes.

**How to apply:**
- Preserve semantics exactly: omit empty API fields from update mappings to reproduce `field or existing.field`; keep conflict rules (e.g. synthetic RUT `OBU-{id}`, "first rut wins") by mutating in-memory owner maps in item order.
- Flush updates BEFORE inserts (inserts only claim keys freed by updates).
- On unique-constraint IntegrityError of a batch, fall back row-by-row ONLY for that batch (savepoint via `begin_nested`); any other exception must propagate (abort-on-failure so reports are never sent with stale data).
- SQLAlchemy 2.0.46: `bulk_update_mappings` accepts heterogeneous key-set dicts, preserves statement order across key-set groups, and applies `onupdate` (verified empirically).
- Still ORM (candidates if they grow): `sync_ventas_items_incremental`, `sync_ventas_cobros`.

# Testing recipe: real savepoints on in-memory sqlite

pysqlite breaks SAVEPOINT by default. Recipe that makes `begin_nested()` work in tests:
- engine with `poolclass=StaticPool`, `connect_args={"check_same_thread": False}`, and `isolation_level=None` on the DBAPI connection via `event.listens_for(engine, "connect")` setting `dbapi_conn.isolation_level = None`, plus `event.listens_for(engine, "begin")` emitting `BEGIN`.
- This lets tests exercise the batch-IntegrityError fallback path with real nested transactions instead of mocks. See `tests/test_sync_clientes_bulk.py`.
