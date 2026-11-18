"""Ordering: place, cancel, track, and staff status updates (FR-06 to FR-12)."""
import secrets

from ..db import transaction
from ..errors import Conflict, Forbidden, NotFound, ValidationError
from ..order_state import HOLDS_SLOT, STAFF_TARGETS, TERMINAL, Status, assert_transition, parse_status
from ..repository import CanteenRepo, MenuRepo, OrderRepo, UserRepo
from . import stamp
from .slot_service import validate_slot

MAX_QTY_PER_ITEM = 10
MAX_ITEMS_PER_ORDER = 20
TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, so tokens are easy to read out
OPEN_STATUSES = [s.value for s in Status if s not in TERMINAL]


def _normalise_lines(items):
    if not isinstance(items, list) or not items:
        raise ValidationError("Your cart is empty.", code="empty_cart")
    merged = {}
    for line in items:
        try:
            item_id, qty = int(line["item_id"]), int(line["quantity"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Each cart line needs an item_id and a quantity.") from None
        if qty < 1:
            raise ValidationError("Quantity must be at least 1.")
        merged[item_id] = merged.get(item_id, 0) + qty
    for item_id, qty in merged.items():
        if qty > MAX_QTY_PER_ITEM:
            raise ValidationError(f"At most {MAX_QTY_PER_ITEM} of one item per order.", code="qty_limit")
    if sum(merged.values()) > MAX_ITEMS_PER_ORDER:
        raise ValidationError(f"At most {MAX_ITEMS_PER_ORDER} items per order.", code="qty_limit")
    return merged


def _new_token(conn, canteen_id):
    while True:
        token = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(4))
        if not OrderRepo.token_in_use(conn, canteen_id, token, OPEN_STATUSES):
            return token


def order_details(conn, order):
    canteen = CanteenRepo.get(conn, order["canteen_id"])
    return {
        **order,
        "canteen_name": canteen["name"] if canteen else None,
        "items": OrderRepo.items(conn, order["id"]),
        "history": OrderRepo.events(conn, order["id"]),
        "cancellable": order["status"] == Status.PLACED.value,
    }


def place_order(conn, user, canteen_id, items, slot_start, now):
    lines = _normalise_lines(items)
    canteen = CanteenRepo.get(conn, canteen_id)
    if not canteen:
        raise NotFound("Canteen not found.")
    validate_slot(canteen, slot_start, now)
    ts = stamp(now)

    with transaction(conn):
        # Capacity and stock are re-checked inside the write lock, so concurrent orders cannot oversell.
        taken = OrderRepo.count_in_slot(conn, canteen_id, slot_start, [s.value for s in HOLDS_SLOT])
        if taken >= canteen["slot_capacity"]:
            raise Conflict("This pickup slot is full. Please choose another.", code="slot_full")

        priced, total = [], 0
        for item_id, qty in lines.items():
            item = MenuRepo.get(conn, item_id)
            if not item or item["canteen_id"] != canteen_id:
                raise NotFound(f"Item {item_id} is not on this canteen's menu.")
            if not item["is_available"]:
                raise Conflict(f"{item['name']} is not available right now.", code="item_unavailable")
            if item["stock"] < qty:
                raise Conflict(f"Only {item['stock']} {item['name']} left.", code="out_of_stock")
            priced.append((item, qty))
            total += item["price_paise"] * qty

        wallet = UserRepo.get(conn, user["id"])["wallet_paise"]
        if wallet < total:
            raise Conflict(
                f"Wallet balance is short by Rs {(total - wallet) / 100:.2f}.", code="insufficient_balance"
            )

        order_id = OrderRepo.create(
            conn, user["id"], canteen_id, slot_start, Status.PLACED.value, total, _new_token(conn, canteen_id), ts
        )
        for item, qty in priced:
            MenuRepo.change_stock(conn, item["id"], -qty)
            OrderRepo.add_item(conn, order_id, item["id"], item["name"], item["price_paise"], qty)
        UserRepo.change_wallet(conn, user["id"], -total, "order payment", ts, order_id)
        OrderRepo.add_event(conn, order_id, None, Status.PLACED.value, user["id"], ts)

    return order_details(conn, OrderRepo.get(conn, order_id))


def _release(conn, order, reason, ts):
    """Undo an order's effects: refund the wallet and return items to stock."""
    for line in OrderRepo.items(conn, order["id"]):
        MenuRepo.change_stock(conn, line["item_id"], line["quantity"])
    UserRepo.change_wallet(conn, order["user_id"], order["total_paise"], reason, ts, order["id"])


def get_order_for_user(conn, user, order_id):
    order = OrderRepo.get(conn, order_id)
    if not order:
        raise NotFound("Order not found.")
    if user["role"] == "student" and order["user_id"] != user["id"]:
        raise Forbidden("This is not your order.")
    if user["role"] in ("staff", "admin") and user["canteen_id"] not in (None, order["canteen_id"]):
        raise Forbidden("This order belongs to another canteen.")
    return order_details(conn, order)


def cancel_order(conn, user, order_id, now):
    ts = stamp(now)
    with transaction(conn):
        order = OrderRepo.get(conn, order_id)
        if not order or order["user_id"] != user["id"]:
            raise NotFound("Order not found.")
        if order["status"] != Status.PLACED.value:
            raise Conflict("The canteen has already accepted this order. Please speak to the counter.",
                           code="not_cancellable")
        assert_transition(order["status"], Status.CANCELLED)
        _release(conn, order, "refund: cancelled by student", ts)
        OrderRepo.set_status(conn, order_id, Status.CANCELLED.value, ts)
        OrderRepo.add_event(conn, order_id, order["status"], Status.CANCELLED.value, user["id"], ts)
    return order_details(conn, OrderRepo.get(conn, order_id))


def update_status(conn, staff, order_id, target, now, token=None):
    target = parse_status(target)
    if target not in STAFF_TARGETS:
        raise Forbidden("Staff cannot set this status.", code="forbidden_status")
    ts = stamp(now)
    with transaction(conn):
        order = OrderRepo.get(conn, order_id)
        if not order:
            raise NotFound("Order not found.")
        if staff["canteen_id"] not in (None, order["canteen_id"]):
            raise Forbidden("This order belongs to another canteen.")
        assert_transition(order["status"], target)
        if target is Status.PICKED_UP and (token or "").strip().upper() != order["token"]:
            raise Conflict("Pickup token does not match. Check the student's token.", code="invalid_token")
        if target is Status.REJECTED:
            _release(conn, order, "refund: rejected by canteen", ts)
        OrderRepo.set_status(conn, order_id, target.value, ts)
        OrderRepo.add_event(conn, order_id, order["status"], target.value, staff["id"], ts)
    return order_details(conn, OrderRepo.get(conn, order_id))


def my_orders(conn, user):
    return [order_details(conn, o) for o in OrderRepo.for_user(conn, user["id"])]


def staff_queue(conn, canteen_id, now):
    """Today's open orders, grouped by pickup slot (FR-10)."""
    groups = {}
    for order in OrderRepo.queue(conn, canteen_id, now.date().isoformat(), OPEN_STATUSES):
        order = order_details(conn, order)
        groups.setdefault(order["slot_start"], []).append(order)
    return [{"slot_start": k, "orders": v} for k, v in sorted(groups.items())]
