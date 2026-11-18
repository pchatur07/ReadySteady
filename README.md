# ReadySteady: Campus Canteen Pre-Ordering System

Software Engineering course project by **Ready Teady Go & Company**.

Students pre-order canteen food for a 15-minute pickup slot and pay from a campus wallet.
Canteen staff work from a live, slot-wise order queue; the canteen admin manages the menu,
stock, slots and wallets, and sees a daily sales report.

## Run it (2 minutes)

```bash
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000. Demo data (2 canteens, 14 menu items) loads automatically.

| Role    | Email               | Password   |
|---------|---------------------|------------|
| Student | student@iiita.ac.in | student123 |
| Staff   | staff@iiita.ac.in   | staff1234  |
| Admin   | admin@iiita.ac.in   | admin1234  |

Tip for the demo: open the student and staff views in two different browsers (or one normal
and one private window) side by side. Status changes appear on the student's screen within 5 seconds.

Slots are only offered for **today**, between opening hours (Main Canteen 08:00 to 21:00),
at least 10 minutes from now.

## Using the interface

- **Hamburger menu (top left):** a liquid-glass drawer with Menu, Cart, Scheduled order,
  Wallet and Previous orders for students (role-specific entries for staff/admin), plus login/logout.
- **Sun/moon button (top right):** smooth light/dark switch — cream + maroon by day,
  warm charcoal + maroon by night. The choice is remembered per browser.
- **Power button:** logs out.
- Menu cards show a reference photo and a struck-through MRP above the selling price.
- Toasts warn about low wallet balance, the next available pickup slot and order status changes;
  placing an order plays a green confirmation tick.

## Run the tests

```bash
python -m pytest            # 75 tests: 60 unit, 11 integration, 4 system
python -m pytest tests/unit # one level at a time
```

Tests run against a temporary database with the clock fixed at 19 Nov 2026, 11:00.

## Software engineering documentation

| Document | Contents |
|---|---|
| [docs/SRS.md](docs/SRS.md) | Functional (FR-01…FR-16) and non-functional requirements, stakeholders, use cases, API contract, traceability to code and tests |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layer design, module responsibilities, justified design decisions, data model, concurrency walkthrough |
| [docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md) | Milestones, schedule, responsibility matrix, risks, definition of done |
| [docs/MAINTENANCE.md](docs/MAINTENANCE.md) | Maintenance categories, change workflow, extension recipes, ops runbook, known limitations |
| [docs/uml/](docs/uml/) | Use-case, class, sequence, activity and state diagrams (Mermaid source + PNG) |

## Project layout

```
app/
  __init__.py        application factory and config
  api.py             REST API: routes, role checks, error -> HTTP code (presentation layer)
  order_state.py     order status state machine
  errors.py          domain exceptions
  repository.py      every SQL query, parameterised (data-access layer)
  db.py, schema.sql  connections, BEGIN IMMEDIATE transactions, tables and constraints
  services/          business rules (service layer)
    auth_service.py  slot_service.py  order_service.py  menu_service.py  report_service.py
  static/            index.html, app.js, style.css (web UI for all three roles)
    img/             logo + web-searched reference photos for the seeded menu items
tests/
  unit/  integration/  system/  conftest.py
docs/                SRS, architecture, plan, maintenance + uml/
seed.py              demo data
run.py               start the server
```

## Configuration (environment variables)

| Variable                  | Default                    | Purpose                                  |
|---------------------------|----------------------------|------------------------------------------|
| `READYTEADY_DB`           | `instance/readyteady.db`   | SQLite database file                     |
| `READYTEADY_SECRET`       | development-only value     | Session signing key; **set in production** |
| `READYTEADY_EMAIL_SUFFIX` | `.ac.in`                   | Allowed email ending for student sign-up |

The `READYTEADY_` prefix is retained from the project's original name so existing deployments
and scripts keep working after the rename to ReadySteady.

To start over with fresh demo data, delete the database file and run `python run.py` again.

Menu reference photos were sourced from public web image search for this academic demo;
they remain the property of their original authors.