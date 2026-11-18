# Software Maintenance Plan

**Project:** ReadySteady — Campus Canteen Pre-Ordering System
**Version:** 1.0 · **Date:** 18 November 2026
Companion documents: `SRS.md`, `ARCHITECTURE.md`, `PROJECT-PLAN.md`, `uml/`.

## 1. Why this system is maintainable by design

- **Layering:** a change to pricing rules touches `services/`, never routes or SQL; a schema change
  touches `repository.py` + `schema.sql`, never business rules (ARCHITECTURE §2).
- **Audit ledgers:** `order_events` and `wallet_transactions` let maintainers reconstruct any
  dispute ("who moved this order, when, and what happened to the money") without guesswork.
- **Safety net:** 75 automated tests (unit/integration/system, including threaded concurrency
  races) run against a temporary database with a frozen clock, so regressions surface in ~1 minute
  on any machine without touching live data.
- **Deterministic time:** the injected clock means time-dependent bugs are reproducible in tests.
- **Stable contracts:** REST paths and JSON shapes are specified in SRS §6.1; the UI revision was
  deliberately frontend-only so existing clients keep working.

## 2. Maintenance categories with concrete examples

| Category | Example for ReadySteady | Where the change lands |
|---|---|---|
| Corrective | Fix a refund double-credit if a cancel races a reject | `order_service.cancel_order/update_status` + new regression test first |
| Adaptive | Upgrade Flask/Python; new browser dropping `backdrop-filter` | `requirements.txt`; CSS fallback in `style.css` |
| Perfective | Add email/SMS notification when an order becomes READY | new `notification_service.py` called from `update_status`; UI toast already exists |
| Preventive | Rotate `READYTEADY_SECRET`, back up the SQLite file, review indexes | ops runbook §5; `schema.sql` |

## 3. Change workflow (corrective/adaptive/perfective)

1. **Reproduce as a failing test** at the lowest level that shows the bug (unit preferred).
2. Fix in the owning layer only; keep the REST contract identical unless the SRS is amended.
3. Run `python -m pytest` (all 75+ tests) — concurrency tests included, never skipped.
4. Update traceability: SRS requirement id in the module docstring, and the test id in SRS §4/§5.
5. If behaviour changed visibly: update the matching UML diagram source (`.mmd`) and re-render PNG.
6. Reviewed PR; deploy by restarting the server process (the operator restarts their own instance).

## 4. Extension recipes (perfective maintenance)

| Extension | Touch points | Notes |
|---|---|---|
| New canteen | `seed.py` MENU dict or admin UI | No code change; slots/menu derive from the canteen row |
| Real payment gateway | `menu_service.top_up_wallet` → gateway webhook crediting via `UserRepo.change_wallet` | Keep the ledger as source of truth; idempotency key on webhook |
| READY notifications | `order_service.update_status` post-commit hook | Must fire **after** COMMIT, never inside the transaction |
| Multi-day advance booking | `slot_service.validate_slot` day check + `list_slots` day loop | SRS FR-05 amendment required; capacity queries already day-scoped |
| Report CSV export | `report_service.daily_report` + a new route | Pure addition; no existing contract change |
| Menu photos for admin-created items | add `image_url` column + migration §6 | Today photos are a client-side name map with a placeholder fallback |
| Rate limiting / HTTPS | reverse proxy (nginx/caddy) in front of Flask | Dev server is not production-hardened by design |

## 5. Operations runbook (preventive)

- **Start:** `python run.py` (seeds once on empty DB). **Health:** `GET /health`.
- **Config:** `READYTEADY_DB`, `READYTEADY_SECRET` (set in production!), `READYTEADY_EMAIL_SUFFIX`.
  The legacy `READYTEADY_` prefix is intentionally retained after the rename (ARCHITECTURE §3 #13).
- **Backup:** stop writes or use SQLite online backup API; copy the single DB file; restore by
  replacing the file while the server is stopped. Test restores quarterly.
- **Secret rotation:** change `READYTEADY_SECRET` → all sessions invalidate (acceptable; users re-login).
- **Log/ledger growth:** `order_events`/`wallet_transactions` are append-only; archive rows older
  than the academic year to a cold copy before pruning (never prune without an archive).
- **Dependency hygiene:** review `requirements.txt` each semester; run the suite after any bump.

## 6. Schema evolution strategy

Current bootstrap is `CREATE TABLE IF NOT EXISTS` (idempotent, no migrations). For any column
addition: add a `schema_version` table and numbered, additive migration scripts applied in order
at startup; never drop/rename columns in place — add new, backfill, switch readers, then retire.
Every migration ships with a test that runs it against a copy of a seeded database.

## 7. Known limitations and future work (honest debt list)

1. Single-process SQLite: fine for one canteen host; horizontal scale needs Postgres + row locks.
2. Polling ≤5 s latency; SSE/WebSocket is the documented upgrade path (ARCHITECTURE §3 #7).
3. No password reset / email verification; college-email gate is the only identity proof.
4. No rate limiting or HTTPS in the dev server; put a reverse proxy in front for real deployment.
5. Menu photos keyed by item name client-side; admin-created items show a placeholder until §4 row 6.
6. Admin wallet top-up stands in for a payment gateway (deliberate academic scope, SRS §1.2).

Each item is a *scheduled* improvement candidate, not a hidden defect: they are listed here so
future maintainers inherit intent, not archaeology.