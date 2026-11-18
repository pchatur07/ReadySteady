"""Repository layer: the only module that writes SQL. Every query is parameterised (NFR-03)."""


def _one(conn, sql, args=()):
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def _all(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---------- users ----------
class UserRepo:
    @staticmethod
    def create(conn, name, email, password_hash, role, now, canteen_id=None, wallet_paise=0):
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, role, canteen_id, wallet_paise, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, email, password_hash, role, canteen_id, wallet_paise, now),
        )
        return cur.lastrowid

    @staticmethod
    def get(conn, user_id):
        return _one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))

    @staticmethod
    def by_email(conn, email):
        return _one(conn, "SELECT * FROM users WHERE email = ?", (email,))

    @staticmethod
    def change_wallet(conn, user_id, delta_paise, reason, now, order_id=None):
        conn.execute("UPDATE users SET wallet_paise = wallet_paise + ? WHERE id = ?", (delta_paise, user_id))
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, amount_paise, reason, order_id, at) VALUES (?, ?, ?, ?, ?)",
            (user_id, delta_paise, reason, order_id, now),
        )


# ---------- canteens & menu ----------
class CanteenRepo:
    @staticmethod
    def all(conn):
        return _all(conn, "SELECT * FROM canteens ORDER BY id")

    @staticmethod
    def get(conn, canteen_id):
        return _one(conn, "SELECT * FROM canteens WHERE id = ?", (canteen_id,))

    @staticmethod
    def update_slots(conn, canteen_id, slot_minutes, slot_capacity):
        conn.execute(
            "UPDATE canteens SET slot_minutes = ?, slot_capacity = ? WHERE id = ?",
            (slot_minutes, slot_capacity, canteen_id),
        )


class MenuRepo:
    @staticmethod
    def for_canteen(conn, canteen_id):
        return _all(conn, "SELECT * FROM menu_items WHERE canteen_id = ? ORDER BY category, name", (canteen_id,))

    @staticmethod
    def get(conn, item_id):
        return _one(conn, "SELECT * FROM menu_items WHERE id = ?", (item_id,))

    @staticmethod
    def create(conn, canteen_id, name, category, price_paise, prep_minutes, stock, is_available):
        cur = conn.execute(
            "INSERT INTO menu_items (canteen_id, name, category, price_paise, prep_minutes, stock, is_available)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (canteen_id, name, category, price_paise, prep_minutes, stock, int(is_available)),
        )
        return cur.lastrowid

    @staticmethod
    def update(conn, item_id, fields):
        allowed = ("name", "category", "price_paise", "prep_minutes", "stock", "is_available")
        cols = [c for c in allowed if c in fields]
        if not cols:
            return
        sql = "UPDATE menu_items SET " + ", ".join(f"{c} = ?" for c in cols) + " WHERE id = ?"
        conn.execute(sql, [fields[c] for c in cols] + [item_id])

    @staticmethod
    def change_stock(conn, item_id, delta):
        conn.execute("UPDATE menu_items SET stock = stock + ? WHERE id = ?", (delta, item_id))


# ---------- orders ----------
class OrderRepo:
    @staticmethod
    def count_in_slot(conn, canteen_id, slot_start, statuses):
        marks = ",".join("?" for _ in statuses)
        row = conn.execute(
            f"SELECT COUNT(*) FROM orders WHERE canteen_id = ? AND slot_start = ? AND status IN ({marks})",
            (canteen_id, slot_start, *statuses),
        ).fetchone()
        return row[0]

    @staticmethod
    def counts_by_slot(conn, canteen_id, day_prefix, statuses):
        marks = ",".join("?" for _ in statuses)
        rows = conn.execute(
            f"SELECT slot_start, COUNT(*) AS n FROM orders WHERE canteen_id = ? AND slot_start LIKE ?"
            f" AND status IN ({marks}) GROUP BY slot_start",
            (canteen_id, day_prefix + "%", *statuses),
        ).fetchall()
        return {r["slot_start"]: r["n"] for r in rows}

    @staticmethod
    def token_in_use(conn, canteen_id, token, open_statuses):
        marks = ",".join("?" for _ in open_statuses)
        row = conn.execute(
            f"SELECT 1 FROM orders WHERE canteen_id = ? AND token = ? AND status IN ({marks})",
            (canteen_id, token, *open_statuses),
        ).fetchone()
        return row is not None

    @staticmethod
    def create(conn, user_id, canteen_id, slot_start, status, total_paise, token, now):
        cur = conn.execute(
            "INSERT INTO orders (user_id, canteen_id, slot_start, status, total_paise, token, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, canteen_id, slot_start, status, total_paise, token, now, now),
        )
        return cur.lastrowid

    @staticmethod
    def add_item(conn, order_id, item_id, name, unit_price_paise, quantity):
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, name, unit_price_paise, quantity) VALUES (?, ?, ?, ?, ?)",
            (order_id, item_id, name, unit_price_paise, quantity),
        )

    @staticmethod
    def items(conn, order_id):
        return _all(conn, "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))

    @staticmethod
    def get(conn, order_id):
        return _one(conn, "SELECT * FROM orders WHERE id = ?", (order_id,))

    @staticmethod
    def set_status(conn, order_id, status, now):
        conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (status, now, order_id))

    @staticmethod
    def add_event(conn, order_id, from_status, to_status, actor_id, now):
        conn.execute(
            "INSERT INTO order_events (order_id, from_status, to_status, actor_id, at) VALUES (?, ?, ?, ?, ?)",
            (order_id, from_status, to_status, actor_id, now),
        )

    @staticmethod
    def events(conn, order_id):
        return _all(conn, "SELECT from_status, to_status, at FROM order_events WHERE order_id = ? ORDER BY id", (order_id,))

    @staticmethod
    def for_user(conn, user_id, limit=50):
        return _all(conn, "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))

    @staticmethod
    def queue(conn, canteen_id, day_prefix, statuses):
        marks = ",".join("?" for _ in statuses)
        return _all(
            conn,
            f"SELECT o.*, u.name AS student_name FROM orders o JOIN users u ON u.id = o.user_id"
            f" WHERE o.canteen_id = ? AND o.slot_start LIKE ? AND o.status IN ({marks})"
            f" ORDER BY o.slot_start, o.id",
            (canteen_id, day_prefix + "%", *statuses),
        )

    @staticmethod
    def for_day(conn, canteen_id, day_prefix):
        return _all(conn, "SELECT * FROM orders WHERE canteen_id = ? AND slot_start LIKE ?", (canteen_id, day_prefix + "%"))

    @staticmethod
    def top_items(conn, canteen_id, day_prefix, statuses, limit=5):
        marks = ",".join("?" for _ in statuses)
        return _all(
            conn,
            f"SELECT oi.name, SUM(oi.quantity) AS quantity, SUM(oi.quantity * oi.unit_price_paise) AS revenue_paise"
            f" FROM order_items oi JOIN orders o ON o.id = oi.order_id"
            f" WHERE o.canteen_id = ? AND o.slot_start LIKE ? AND o.status IN ({marks})"
            f" GROUP BY oi.name ORDER BY quantity DESC, oi.name LIMIT ?",
            (canteen_id, day_prefix + "%", *statuses, limit),
        )
