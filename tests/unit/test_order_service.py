import re

import pytest

from app.errors import Conflict, Forbidden, NotFound, ValidationError
from app.repository import CanteenRepo, MenuRepo, OrderRepo, UserRepo
from app.services import order_service
from tests.conftest import NOW, SLOT

DOSA, THALI, SAMOSA = 1, 3, 5          # seeded Main Canteen items: Rs 50, Rs 80, Rs 20
MAGGI = 10                             # Night Canteen item


def place(conn, student, items=None, slot=SLOT):
    return order_service.place_order(conn, student, 1, items or [{"item_id": DOSA, "quantity": 2}], slot, NOW)


def wallet(conn, user):
    return UserRepo.get(conn, user["id"])["wallet_paise"]


def stock(conn, item_id):
    return MenuRepo.get(conn, item_id)["stock"]


def test_ut14_place_order_reserves_stock_charges_wallet_and_issues_token(conn, student):
    order = place(conn, student, [{"item_id": DOSA, "quantity": 2}, {"item_id": SAMOSA, "quantity": 1}])
    assert order["status"] == "PLACED"
    assert order["total_paise"] == 2 * 5000 + 2000
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{4}", order["token"])
    assert stock(conn, DOSA) == 38 and stock(conn, SAMOSA) == 59
    assert wallet(conn, student) == 50000 - 12000
    assert [e["to_status"] for e in order["history"]] == ["PLACED"]


def test_ut15_duplicate_cart_lines_are_merged(conn, student):
    order = place(conn, student, [{"item_id": DOSA, "quantity": 1}, {"item_id": DOSA, "quantity": 2}])
    assert len(order["items"]) == 1 and order["items"][0]["quantity"] == 3


@pytest.mark.parametrize("items, code", [
    ([], "empty_cart"),
    ([{"item_id": DOSA, "quantity": 0}], "validation_error"),
    ([{"item_id": DOSA, "quantity": 11}], "qty_limit"),
    ([{"item_id": DOSA, "quantity": 7}, {"item_id": THALI, "quantity": 7}, {"item_id": SAMOSA, "quantity": 7}], "qty_limit"),
    ([{"quantity": 1}], "validation_error"),
])
def test_ut16_invalid_carts_are_rejected(conn, student, items, code):
    with pytest.raises(ValidationError) as e:
        order_service.place_order(conn, student, 1, items, SLOT, NOW)
    assert e.value.code == code


def test_ut17_out_of_stock_fails_and_changes_nothing(conn, student):
    MenuRepo.update(conn, DOSA, {"stock": 1})
    with pytest.raises(Conflict) as e:
        place(conn, student, [{"item_id": SAMOSA, "quantity": 1}, {"item_id": DOSA, "quantity": 2}])
    assert e.value.code == "out_of_stock" and "Only 1" in e.value.message
    assert stock(conn, SAMOSA) == 60 and wallet(conn, student) == 50000      # rolled back


def test_ut18_unavailable_item_and_other_canteens_item_are_refused(conn, student):
    MenuRepo.update(conn, THALI, {"is_available": 0})
    with pytest.raises(Conflict) as e:
        place(conn, student, [{"item_id": THALI, "quantity": 1}])
    assert e.value.code == "item_unavailable"
    with pytest.raises(NotFound):
        place(conn, student, [{"item_id": MAGGI, "quantity": 1}])


def test_ut19_low_wallet_balance_is_refused(conn, student):
    UserRepo.change_wallet(conn, student["id"], -45000, "test", "t")        # Rs 50 left
    with pytest.raises(Conflict) as e:
        place(conn, student, [{"item_id": THALI, "quantity": 1}])
    assert e.value.code == "insufficient_balance" and "30.00" in e.value.message
    assert stock(conn, THALI) == 30


def test_ut20_full_slot_is_refused(conn, student):
    CanteenRepo.update_slots(conn, 1, 15, 2)
    place(conn, student, [{"item_id": SAMOSA, "quantity": 1}])
    place(conn, student, [{"item_id": SAMOSA, "quantity": 1}])
    with pytest.raises(Conflict) as e:
        place(conn, student, [{"item_id": SAMOSA, "quantity": 1}])
    assert e.value.code == "slot_full"


def test_ut21_cancel_refunds_restocks_and_frees_the_slot(conn, student):
    CanteenRepo.update_slots(conn, 1, 15, 1)
    order = place(conn, student)
    cancelled = order_service.cancel_order(conn, student, order["id"], NOW)
    assert cancelled["status"] == "CANCELLED" and not cancelled["cancellable"]
    assert wallet(conn, student) == 50000 and stock(conn, DOSA) == 40
    place(conn, student)                                                       # the one place is free again


def test_ut22_cannot_cancel_after_acceptance_or_someone_elses_order(conn, student, staff):
    order = place(conn, student)
    order_service.update_status(conn, staff, order["id"], "ACCEPTED", NOW)
    with pytest.raises(Conflict) as e:
        order_service.cancel_order(conn, student, order["id"], NOW)
    assert e.value.code == "not_cancellable"
    other = {**student, "id": 999}
    with pytest.raises(NotFound):
        order_service.cancel_order(conn, other, order["id"], NOW)


def test_ut23_reject_refunds_the_student(conn, student, staff):
    order = place(conn, student)
    assert order_service.update_status(conn, staff, order["id"], "REJECTED", NOW)["status"] == "REJECTED"
    assert wallet(conn, student) == 50000 and stock(conn, DOSA) == 40


def test_ut24_handover_requires_the_matching_token(conn, student, staff):
    order = place(conn, student)
    for s in ("ACCEPTED", "PREPARING", "READY"):
        order_service.update_status(conn, staff, order["id"], s, NOW)
    with pytest.raises(Conflict) as e:
        order_service.update_status(conn, staff, order["id"], "PICKED_UP", NOW, token="ZZZZ")
    assert e.value.code == "invalid_token"
    done = order_service.update_status(conn, staff, order["id"], "PICKED_UP", NOW, token=order["token"].lower())
    assert done["status"] == "PICKED_UP"
    assert [e["to_status"] for e in done["history"]] == ["PLACED", "ACCEPTED", "PREPARING", "READY", "PICKED_UP"]


def test_ut25_staff_cannot_skip_steps_cancel_or_touch_another_canteen(conn, student, staff):
    order = place(conn, student)
    with pytest.raises(Conflict):
        order_service.update_status(conn, staff, order["id"], "READY", NOW)
    with pytest.raises(Forbidden):
        order_service.update_status(conn, staff, order["id"], "CANCELLED", NOW)
    night_staff = {**staff, "canteen_id": 2}
    with pytest.raises(Forbidden):
        order_service.update_status(conn, night_staff, order["id"], "ACCEPTED", NOW)


def test_ut26_staff_queue_groups_open_orders_by_slot(conn, student, staff):
    a = place(conn, student, slot="2026-11-19T12:30")
    b = place(conn, student, slot="2026-11-19T12:00")
    c = place(conn, student, slot="2026-11-19T12:00")
    order_service.cancel_order(conn, student, c["id"], NOW)
    queue = order_service.staff_queue(conn, 1, NOW)
    assert [g["slot_start"] for g in queue] == ["2026-11-19T12:00", "2026-11-19T12:30"]
    assert [o["id"] for o in queue[0]["orders"]] == [b["id"]]
    assert queue[1]["orders"][0]["id"] == a["id"]


def test_ut27_tokens_are_unique_among_open_orders(conn, student):
    tokens = {place(conn, student, [{"item_id": SAMOSA, "quantity": 1}], slot=f"2026-11-19T{h}:00")["token"]
              for h in range(12, 21)}
    assert len(tokens) == 9
    assert OrderRepo.count_in_slot(conn, 1, "2026-11-19T12:00", ["PLACED"]) == 1
