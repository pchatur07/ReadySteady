"""Menu and canteen administration (FR-03, FR-13, FR-14)."""
from ..db import transaction
from ..errors import Forbidden, NotFound, ValidationError
from ..repository import CanteenRepo, MenuRepo, UserRepo
from . import stamp

FIELDS = {
    "name": str,
    "category": str,
    "price_paise": int,
    "prep_minutes": int,
    "stock": int,
    "is_available": bool,
}


def _clean(data, partial):
    out = {}
    for field, kind in FIELDS.items():
        if field not in data:
            if not partial and field in ("name", "category", "price_paise"):
                raise ValidationError(f"'{field}' is required.")
            continue
        value = data[field]
        try:
            value = (str(value).strip() if kind is str else bool(value) if kind is bool else int(value))
        except (TypeError, ValueError):
            raise ValidationError(f"'{field}' has the wrong type.") from None
        out[field] = value
    if "name" in out and not (1 <= len(out["name"]) <= 60):
        raise ValidationError("Item name must be 1 to 60 characters.")
    if "category" in out and not out["category"]:
        raise ValidationError("Category is required.")
    if "price_paise" in out and not (1 <= out["price_paise"] <= 100000):
        raise ValidationError("Price must be between Rs 0.01 and Rs 1000.")
    if "prep_minutes" in out and not (1 <= out["prep_minutes"] <= 120):
        raise ValidationError("Prep time must be 1 to 120 minutes.")
    if "stock" in out and not (0 <= out["stock"] <= 10000):
        raise ValidationError("Stock must be 0 to 10000.")
    if "is_available" in out:
        out["is_available"] = int(out["is_available"])
    return out


def _check_canteen(admin, canteen_id):
    if admin["canteen_id"] not in (None, canteen_id):
        raise Forbidden("You manage a different canteen.")


def menu(conn, canteen_id):
    canteen = CanteenRepo.get(conn, canteen_id)
    if not canteen:
        raise NotFound("Canteen not found.")
    return {"canteen": canteen, "items": MenuRepo.for_canteen(conn, canteen_id)}


def create_item(conn, admin, canteen_id, data):
    _check_canteen(admin, canteen_id)
    if not CanteenRepo.get(conn, canteen_id):
        raise NotFound("Canteen not found.")
    f = _clean(data, partial=False)
    item_id = MenuRepo.create(
        conn, canteen_id, f["name"], f["category"], f["price_paise"],
        f.get("prep_minutes", 5), f.get("stock", 0), f.get("is_available", 1),
    )
    return MenuRepo.get(conn, item_id)


def update_item(conn, admin, item_id, data):
    item = MenuRepo.get(conn, item_id)
    if not item:
        raise NotFound("Item not found.")
    _check_canteen(admin, item["canteen_id"])
    MenuRepo.update(conn, item_id, _clean(data, partial=True))
    return MenuRepo.get(conn, item_id)


def configure_slots(conn, admin, canteen_id, slot_minutes, slot_capacity):
    _check_canteen(admin, canteen_id)
    if not CanteenRepo.get(conn, canteen_id):
        raise NotFound("Canteen not found.")
    try:
        slot_minutes, slot_capacity = int(slot_minutes), int(slot_capacity)
    except (TypeError, ValueError):
        raise ValidationError("Slot length and capacity must be whole numbers.") from None
    if slot_minutes not in (5, 10, 15, 20, 30, 60):
        raise ValidationError("Slot length must be 5, 10, 15, 20, 30 or 60 minutes.")
    if not 1 <= slot_capacity <= 500:
        raise ValidationError("Capacity must be 1 to 500 orders per slot.")
    CanteenRepo.update_slots(conn, canteen_id, slot_minutes, slot_capacity)
    return CanteenRepo.get(conn, canteen_id)


def top_up_wallet(conn, admin, email, amount_paise, now):
    try:
        amount_paise = int(amount_paise)
    except (TypeError, ValueError):
        raise ValidationError("Amount must be a whole number of paise.") from None
    if not 100 <= amount_paise <= 500000:
        raise ValidationError("Top-up must be between Rs 1 and Rs 5000.")
    with transaction(conn):
        student = UserRepo.by_email(conn, (email or "").strip().lower())
        if not student or student["role"] != "student":
            raise NotFound("No student with that email.")
        UserRepo.change_wallet(conn, student["id"], amount_paise, f"top-up by admin {admin['id']}", stamp(now))
    return {"email": student["email"], "wallet_paise": UserRepo.get(conn, student["id"])["wallet_paise"]}
