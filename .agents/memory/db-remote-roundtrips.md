---
name: Remote DB round-trips & long-fetch disconnects
description: Why bulk_update_mappings was still slow in prod and why report syncs died with "SSL connection has been closed unexpectedly"; the 3-layer fix pattern.
---

# Executemany UPDATEs = one network round-trip per row (psycopg2 default)

**Rule:** With SQLAlchemy + psycopg2 against a REMOTE Postgres, `bulk_update_mappings` (and any executemany UPDATE/DELETE) sends ONE round-trip PER ROW unless the engine sets `executemany_mode="values_plus_batch"` (+ `executemany_batch_page_size`). INSERTs are already batched (insertmanyvalues); UPDATEs are not.

**Why:** In prod (remote DB, ~70ms RTT) 63k "bulk" updates took ~80 min (~72ms/row) even after converting the sync to bulk mappings — the dev DB is near-local so this never shows up in development. With execute_batch pages of 500 the same work takes minutes.

**How to apply:** Any time a "bulk" write path is inexplicably slow in prod but fast in dev, suspect per-statement round-trips, not the ORM. Check `executemany_mode` first. Caveat: batched executemany loses reliable `cursor.rowcount` — don't count affected rows there; use single-statement `query.update()` when a count is needed.

# Long API fetches kill held DB connections (pre_ping can't save you)

**Rule:** Never hold a Session transaction/connection across a multi-minute external API download. `pool_pre_ping` only runs at pool CHECKOUT — a connection retained by an open (autobegin) transaction is never re-checked, and NAT/proxies/servers silently kill it → `SSL connection has been closed unexpectedly` on the first query after the fetch.

**How to apply (3 layers):**
1. `db.rollback()` immediately BEFORE each long fetch — releases the connection to the pool so the post-fetch query gets a fresh pre_ping'd checkout. Safe when every sync commits its own work before returning.
2. TCP keepalives in `connect_args` (`keepalives=1, keepalives_idle=60, keepalives_interval=20, keepalives_count=5`).
3. Retry-once per sync step on CONNECTION errors only (`OperationalError`, `InterfaceError`, `DBAPIError.connection_invalidated`) with rollback in between — steps must be idempotent (upsert with re-read preload / delete+reinsert). Data errors (IntegrityError) must NOT be retried. Persistent failure still propagates so abort-on-failure (no emails with partial data) stays intact.
