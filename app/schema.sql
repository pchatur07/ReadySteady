-- ReadySteady database schema (SQLite). Money is stored in paise (integer) to avoid float rounding.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('student', 'staff', 'admin')),
    canteen_id    INTEGER REFERENCES canteens(id),          -- staff/admin: the canteen they work at
    wallet_paise  INTEGER NOT NULL DEFAULT 0 CHECK (wallet_paise >= 0),
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS canteens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    location      TEXT    NOT NULL,
    open_time     TEXT    NOT NULL,                         -- 'HH:MM'
    close_time    TEXT    NOT NULL,                         -- 'HH:MM'
    slot_minutes  INTEGER NOT NULL DEFAULT 15 CHECK (slot_minutes BETWEEN 5 AND 60),
    slot_capacity INTEGER NOT NULL DEFAULT 20 CHECK (slot_capacity BETWEEN 1 AND 500)
);

CREATE TABLE IF NOT EXISTS menu_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    canteen_id    INTEGER NOT NULL REFERENCES canteens(id),
    name          TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    price_paise   INTEGER NOT NULL CHECK (price_paise > 0),
    prep_minutes  INTEGER NOT NULL DEFAULT 5 CHECK (prep_minutes > 0),
    stock         INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    is_available  INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1))
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    canteen_id    INTEGER NOT NULL REFERENCES canteens(id),
    slot_start    TEXT    NOT NULL,                         -- 'YYYY-MM-DDTHH:MM'
    status        TEXT    NOT NULL,
    total_paise   INTEGER NOT NULL CHECK (total_paise > 0),
    token         TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id         INTEGER NOT NULL REFERENCES orders(id),
    item_id          INTEGER NOT NULL REFERENCES menu_items(id),
    name             TEXT    NOT NULL,                      -- copied so history survives menu edits
    unit_price_paise INTEGER NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity > 0)
);

-- Audit trail of every status change (supports maintenance and dispute resolution).
CREATE TABLE IF NOT EXISTS order_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    from_status TEXT,
    to_status   TEXT    NOT NULL,
    actor_id    INTEGER NOT NULL REFERENCES users(id),
    at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    amount_paise INTEGER NOT NULL,                          -- + top-up/refund, - payment
    reason       TEXT    NOT NULL,
    order_id     INTEGER REFERENCES orders(id),
    at           TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_slot ON orders (canteen_id, slot_start, status);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders (user_id, created_at);
