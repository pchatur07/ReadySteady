# Software Requirements Specification (SRS)

**Project:** ReadySteady — Campus Canteen Pre-Ordering System
**Group:** Ready Teady Go & Company
**Course:** Software Engineering
**Version:** 1.0 (reconstructed) · **Date:** 18 November 2026

> **Provenance note.** The implementation cites requirement identifiers (`FR-01`…`FR-15`,
> `NFR-02`, `NFR-03`) in module docstrings, but the original SRS was not shipped with the
> code. This document reconstructs the specification from those citations, the UML use-case
> diagram (`docs/uml/1-use-case.mmd`, UC-01…UC-12) and the verified behaviour of the code and
> its 75 tests. `FR-04` (cart management) and `FR-16` (wallet top-up) are inferred from
> implemented behaviour that no citation covers. If the original SRS surfaces, reconcile
> numbering against it before submission.

---

## 1. Introduction

### 1.1 Purpose
Specify the functional and non-functional requirements of ReadySteady, a web application that
lets students pre-order canteen food for a fixed pickup slot and pay from a campus wallet,
while canteen staff work a live slot-wise queue and the canteen admin manages menu, stock,
slots, wallets and sales reporting.

### 1.2 Scope
In scope: student registration/login, menu browsing, cart, slot selection, wallet-paid
ordering, cancellation, order tracking, staff queue and status workflow with token-verified
handover, admin menu/stock/slot/wallet management and a daily sales report.
Out of scope: online payment gateway integration, delivery, multi-day advance booking,
nutrition information, loyalty schemes, native mobile apps.

### 1.3 Definitions
| Term | Meaning |
|---|---|
| Paise | Integer hundredths of a rupee; all money is stored and computed in paise |
| Slot | A pickup window of `slot_minutes` (default 15) inside canteen opening hours |
| Token | 4-character pickup code (alphabet excludes 0/O/1/I) shown at the counter |
| Open order | Order in PLACED, ACCEPTED, PREPARING or READY (holds a slot place) |
| Terminal order | PICKED_UP, CANCELLED or REJECTED (no further transitions) |

### 1.4 References
- `docs/ARCHITECTURE.md` — design and justification
- `docs/uml/` — use-case, class, sequence, activity and state diagrams
- `docs/PROJECT-PLAN.md`, `docs/MAINTENANCE.md`
- IEEE 830-style structure adapted to course scope

## 2. Overall Description

### 2.1 Product perspective
Self-contained single-node web application: Flask REST API + server-rendered static SPA
(vanilla JS) over a SQLite database. No external services are required at runtime.

### 2.2 User classes
| Actor | Description | Privileges |
|---|---|---|
| Student | Registered with a college email (`*.ac.in` by default) | Browse, cart, order, cancel own PLACED orders, track own orders |
| Canteen staff | Assigned to one canteen | View that canteen's queue, advance/reject orders, verify pickup token |
| Canteen admin | Assigned to one canteen (or unrestricted if unassigned) | Staff privileges plus menu/stock, slot configuration, wallet top-ups, daily report |

### 2.3 Operating environment
Python 3.10+, Flask 3.x, SQLite 3 (file database), any modern browser. Server binds
127.0.0.1:5000 in development; configuration via environment variables (see §6.3).

### 2.4 Constraints
- Single-process, single-node deployment (SQLite write lock serialises writers).
- Slots are offered only for **today**, aligned to opening hours, ≥10 minutes ahead.
- Session-cookie authentication; no anonymous ordering.
- Academic demo: wallet top-ups are performed by the admin, not a payment gateway.

### 2.5 Assumptions
- One canteen account per staff/admin member; canteen scoping enforced server-side.
- The device clock is trustworthy; tests inject a fixed clock for determinism.
- Demo seed data (2 canteens, 14 items, 3 accounts) is loaded once on an empty database.

## 3. Stakeholders and Use Cases

Stakeholders: students (primary), canteen staff, canteen admin/manager, college administration
(indirect: wallet policy), development group (maintenance).

| UC | Use case | Actor(s) | Requirements |
|---|---|---|---|
| UC-01 | Register / log in | Student, Staff, Admin | FR-01, FR-02 |
| UC-02 | Browse menu | Student | FR-03 |
| UC-03 | Manage cart | Student | FR-04 |
| UC-04 | Choose pickup slot | Student | FR-05 |
| UC-05 | Place order | Student | FR-06 (includes UC-04) |
| UC-06 | Track order | Student | FR-08 |
| UC-07 | Cancel order | Student | FR-07 |
| UC-08 | View order queue | Staff, Admin | FR-10 |
| UC-09 | Update order status | Staff, Admin | FR-09, FR-11, FR-12 |
| UC-10 | Manage menu and stock | Admin | FR-13 |
| UC-11 | Configure slots, top up wallets | Admin | FR-14, FR-16 |
| UC-12 | View sales report | Admin | FR-15 |

## 4. Functional Requirements

Each requirement lists acceptance criteria and traceability to implementation and tests
(UT = unit, IT = integration, ST = system; ids match test function names).

### FR-01 Student self-registration
The system shall register a student with name (1–80 chars), a valid college email ending in
the configured suffix (default `.ac.in`, case-insensitive), and a password of ≥8 characters;
duplicate emails are refused; passwords are stored only as salted PBKDF2-SHA256 hashes.
*Accept:* invalid name/email/password → 400 with stable code (`email_domain` for wrong suffix);
duplicate → 409 `email_taken`; response never contains the hash.
*Trace:* `app/services/auth_service.py` · UT-10…UT-13, IT-03.

### FR-02 Authentication and role-based access
The system shall authenticate by email+password with one generic failure message (no account
probing), maintain a server-side session, and enforce role checks on every protected endpoint
(student / staff / admin), including object-level ownership (a student reads only own orders;
staff/admin act only within their canteen).
*Accept:* unauthenticated → 401; wrong role → 403; cross-owner read → 403/404; logout ends session.
*Trace:* `app/api.py` (`requires`), `auth_service.login` · UT-13, UT-22, UT-25, IT-01…IT-04, IT-08.

### FR-03 Browse canteens and menu
The system shall list canteens and, per canteen, its menu items grouped by category with price,
prep time, stock and availability.
*Accept:* unknown canteen → 404; items ordered by category then name.
*Trace:* `app/services/menu_service.py` (`menu`), `app/api.py` · IT-05.

### FR-04 Cart management
The system shall accept cart lines (`item_id`, `quantity`), merge duplicate lines for the same
item, reject quantities <1, >10 per item, or >20 total items per order, and reject empty carts.
*Accept:* merged duplicates produce one order line; limits → 400 `qty_limit` / `empty_cart`.
*Trace:* `app/services/order_service.py` (`_normalise_lines`) · UT-15, UT-16.

### FR-05 Pickup slot listing and validation
The system shall generate slots for today between opening and closing time in `slot_minutes`
steps, report capacity/booked/remaining per slot, mark a slot available only if remaining >0 and
start ≥ now+10 min, and validate a chosen slot for format, alignment, day and lead time.
*Accept:* misaligned/malformed → 400 `invalid_slot`; past/other-day/too-soon → 409 `slot_unavailable`.
*Trace:* `app/services/slot_service.py` · UT-05…UT-09, IT-05, IT-07.

### FR-06 Place order (atomic)
The system shall, in one write transaction: re-check slot capacity, item availability and stock,
and wallet balance; create the order in PLACED with a unique-per-open-orders 4-char token;
reserve stock; debit the wallet; snapshot item name/price; and log the creation event.
*Accept:* any failed check rolls back everything (no partial stock/wallet change); success → 201
with token, items, history; concurrent races cannot oversell or overbook.
*Trace:* `order_service.place_order`, `app/db.py` (`transaction`) · UT-14, UT-17…UT-20, UT-27, IT-06, IT-07, ST-03, ST-04.

### FR-07 Student cancellation
The system shall allow the owning student to cancel only while PLACED, refunding the wallet and
returning stock atomically and freeing the slot place.
*Accept:* after acceptance → 409 `not_cancellable`; non-owner → 404; refund+restock verified.
*Trace:* `order_service.cancel_order`, `_release` · UT-21, UT-22, ST-02.

### FR-08 Order tracking
The system shall expose an order's status, items, canteen name, full status history and a
`cancellable` flag to its owner (and to authorised staff/admin of that canteen), and list a
student's own orders newest-first.
*Trace:* `order_service.order_details`, `get_order_for_user`, `my_orders` · UT-24, IT-06, IT-08, ST-01.

### FR-09 Staff status progression
The system shall advance orders only along the state machine
PLACED→ACCEPTED→PREPARING→READY→PICKED_UP; skipping, regression and moves from terminal states
are refused; staff cannot set CANCELLED (student-only move).
*Accept:* illegal move → 409 `invalid_transition`; staff setting CANCELLED → 403 `forbidden_status`.
*Trace:* `app/order_state.py`, `order_service.update_status` · UT-01…UT-04, UT-25, IT-09.

### FR-10 Staff live queue
The system shall show today's open orders for the staff member's canteen grouped and sorted by
pickup slot, including student name and items, refreshing live in the UI.
*Trace:* `order_service.staff_queue`, `app/static/app.js` (polling) · UT-26, IT-09, ST-01.

### FR-11 Staff rejection with refund
The system shall let staff reject a PLACED order, atomically refunding the wallet and restocking.
*Trace:* `order_service.update_status` (REJECTED branch) · UT-23.

### FR-12 Token-verified handover
The system shall mark an order PICKED_UP only from READY and only when the supplied token matches
the order's token (case-insensitive); the order then leaves the open queue.
*Accept:* wrong token → 409 `invalid_token`.
*Trace:* `order_service.update_status` (PICKED_UP branch) · UT-24, ST-01.

### FR-13 Admin menu and stock management
The system shall let the admin create items (name 1–60, category, price ₹0.01–₹1000, prep 1–120
min, stock 0–10000, availability) and patch any subset of fields, restricted to their canteen.
*Accept:* out-of-range/wrong-type → 400; other canteen → 403; unknown item → 404.
*Trace:* `menu_service.create_item/update_item/_clean` · UT-28…UT-30, IT-10.

### FR-14 Admin slot configuration
The system shall let the admin set slot length ∈ {5,10,15,20,30,60} minutes and capacity 1–500
orders per slot for their canteen; changes affect subsequently generated slots.
*Trace:* `menu_service.configure_slots` · UT-31, IT-10.

### FR-15 Daily sales report
The system shall report, for a chosen day (default today) and canteen: total orders, counts per
status, revenue and average order value **excluding** CANCELLED/REJECTED, busiest slot and top-5
items by quantity with revenue.
*Accept:* invalid date → 400; cancelled orders count in totals but not revenue.
*Trace:* `app/services/report_service.py` · UT-33, IT-10, ST-01.

### FR-16 Admin wallet top-up
The system shall let the admin credit a student's wallet by ₹1–₹5000 (integer paise), recording a
ledger entry; non-student or unknown emails are refused.
*Trace:* `menu_service.top_up_wallet`, `UserRepo.change_wallet` · UT-32, IT-10, ST-01.

## 5. Non-Functional Requirements

### NFR-01 Usability
Role-specific single-page views; responsive layout down to phone widths; status visible within
5 s via polling; labelled controls and ARIA live regions; readable pickup tokens.
*Trace:* `app/static/*` · IT-11, manual UI verification.

### NFR-02 Concurrency safety and atomicity
All multi-row mutations (order placement, cancellation, rejection, top-up) run inside
`BEGIN IMMEDIATE` transactions so capacity, stock and wallet checks cannot race; the database
never oversells or overbooks under concurrent load.
*Trace:* `app/db.py`, `order_service` · ST-03 (8 threads, 1 item), ST-04 (10 threads, 3 seats).

### NFR-03 Security
Parameterised SQL everywhere (no string-built values); salted PBKDF2-SHA256 (600k iterations)
password hashes; generic credential error; HttpOnly, SameSite=Lax session cookie; role and
ownership checks server-side; college-email gate; all server strings HTML-escaped in the UI;
configurable session secret for production.
*Trace:* `app/repository.py`, `auth_service`, `api.py`, `app.js` (`esc`) · UT-10, UT-13, IT-01, IT-02, IT-08.

### NFR-04 Performance
Indexed lookups for slot counts and per-user history; integer-paise arithmetic; 5 s polling
instead of per-keystroke requests; no build step or heavy client framework; page served as static
assets.
*Trace:* `app/schema.sql` (indexes), `app.js` (`poll`) · ST-03/ST-04 complete in seconds.

### NFR-05 Maintainability and auditability
Strict layering (routes → services → repository → DB); one module owns all SQL; every status
change written to `order_events` and every wallet movement to `wallet_transactions`; clock
injected for deterministic tests; requirement ids cited in code.
*Trace:* whole `app/` tree · all 75 tests run against a temporary DB with a frozen clock.

### NFR-06 Data integrity
Schema CHECK constraints (roles, non-negative wallet/stock, positive prices/quantities, slot
bounds); foreign keys enforced; money stored as integer paise; order lines snapshot name and
unit price so history survives menu edits.
*Trace:* `app/schema.sql`, `OrderRepo.add_item` · UT-17, UT-21, UT-33.

## 6. External Interface Requirements

### 6.1 REST API (all JSON; errors = `{error, message}` with stable codes)
| Method & path | Role | Success | Typical errors |
|---|---|---|---|
| POST /api/auth/register | public | 201 user | 400, 409 email_taken |
| POST /api/auth/login | public | 200 user | 401 bad_credentials |
| POST /api/auth/logout | any | 200 | — |
| GET /api/me | logged-in | 200 user | 401 |
| GET /api/canteens | logged-in | 200 list | 401 |
| GET /api/canteens/:id/menu | logged-in | 200 {canteen, items} | 404 |
| GET /api/canteens/:id/slots | logged-in | 200 slots | 404 |
| POST /api/orders | student | 201 order | 400, 404, 409 (slot_full/out_of_stock/insufficient_balance/…) |
| GET /api/orders | student | 200 list | 401 |
| GET /api/orders/:id | owner/staff/admin | 200 order | 403, 404 |
| POST /api/orders/:id/cancel | student owner | 200 order | 404, 409 not_cancellable |
| GET /api/staff/queue | staff/admin | 200 groups | 400, 403 |
| POST /api/staff/orders/:id/status | staff/admin | 200 order | 403, 404, 409 invalid_transition/invalid_token |
| POST /api/admin/canteens/:id/items | admin | 201 item | 400, 403, 404 |
| PATCH /api/admin/items/:id | admin | 200 item | 400, 403, 404 |
| PATCH /api/admin/canteens/:id/slots | admin | 200 canteen | 400, 403, 404 |
| POST /api/admin/wallets/topup | admin | 200 balance | 400, 404 |
| GET /api/admin/report?date= | admin | 200 report | 400, 403 |
| GET /health | public | 200 {status:"ok"} | — |

### 6.2 User interface
One page, three role views (student: menu/cart + orders; staff: live queue; admin: report, queue,
menu & stock, slots & wallets), plus auth screens. Glass navigation drawer, light/dark theme
toggle, toast notifications and an order-confirmation animation (see UI revision notes in README).

### 6.3 Configuration interfaces
| Variable | Default | Purpose |
|---|---|---|
| `READYTEADY_DB` | `instance/readyteady.db` | SQLite file (legacy prefix retained after rename for compatibility) |
| `READYTEADY_SECRET` | dev-only value | Session signing key; must be set in production |
| `READYTEADY_EMAIL_SUFFIX` | `.ac.in` | Allowed college email suffix |

## 7. Verification
Every FR/NFR above maps to at least one automated test (75 total: 60 unit, 11 integration,
4 system) or to a documented manual UI check. Run `python -m pytest`. Concurrency NFR-02 is
verified by threaded race tests ST-03/ST-04 rather than by inspection.