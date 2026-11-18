import pytest

from app.errors import Forbidden, NotFound, ValidationError
from app.services import menu_service, order_service, report_service
from tests.conftest import NOW, SLOT


def test_ut28_admin_can_add_and_edit_items(conn, admin):
    item = menu_service.create_item(conn, admin, 1, {"name": " Poha ", "category": "Breakfast", "price_paise": 2500, "stock": 15})
    assert item["name"] == "Poha" and item["is_available"] == 1 and item["prep_minutes"] == 5
    item = menu_service.update_item(conn, admin, item["id"], {"stock": 0, "is_available": False, "ignored": "x"})
    assert item["stock"] == 0 and item["is_available"] == 0


@pytest.mark.parametrize("data", [
    {"category": "X", "price_paise": 100},
    {"name": "X", "category": "X", "price_paise": 0},
    {"name": "X", "category": "X", "price_paise": "ten"},
    {"name": "X", "category": "X", "price_paise": 100, "stock": -1},
])
def test_ut29_item_validation(conn, admin, data):
    with pytest.raises(ValidationError):
        menu_service.create_item(conn, admin, 1, data)


def test_ut30_admin_is_limited_to_their_canteen(conn, admin):
    with pytest.raises(Forbidden):
        menu_service.update_item(conn, admin, 10, {"stock": 5})            # item 10 is in Night Canteen
    with pytest.raises(NotFound):
        menu_service.update_item(conn, admin, 9999, {"stock": 5})


def test_ut31_slot_configuration_is_validated(conn, admin):
    assert menu_service.configure_slots(conn, admin, 1, 30, 40)["slot_capacity"] == 40
    with pytest.raises(ValidationError):
        menu_service.configure_slots(conn, admin, 1, 7, 40)
    with pytest.raises(ValidationError):
        menu_service.configure_slots(conn, admin, 1, 15, 0)


def test_ut32_wallet_top_up(conn, admin):
    assert menu_service.top_up_wallet(conn, admin, "student@iiita.ac.in", 10000, NOW)["wallet_paise"] == 60000
    with pytest.raises(NotFound):
        menu_service.top_up_wallet(conn, admin, "staff@iiita.ac.in", 10000, NOW)
    with pytest.raises(ValidationError):
        menu_service.top_up_wallet(conn, admin, "student@iiita.ac.in", 50, NOW)


def test_ut33_report_counts_sales_but_not_cancellations(conn, student):
    order_service.place_order(conn, student, 1, [{"item_id": 3, "quantity": 2}], SLOT, NOW)       # Rs 160
    order_service.place_order(conn, student, 1, [{"item_id": 5, "quantity": 1}], SLOT, NOW)       # Rs 20
    c = order_service.place_order(conn, student, 1, [{"item_id": 1, "quantity": 1}], SLOT, NOW)   # cancelled
    order_service.cancel_order(conn, student, c["id"], NOW)
    r = report_service.daily_report(conn, 1, NOW.date())
    assert r["orders_total"] == 3 and r["orders_by_status"]["CANCELLED"] == 1
    assert r["revenue_paise"] == 18000 and r["average_order_paise"] == 9000
    assert r["busiest_slot"] == SLOT
    assert r["top_items"][0]["name"] == "Veg Thali" and r["top_items"][0]["quantity"] == 2
