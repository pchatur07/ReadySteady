"""Integration tests: HTTP routes + services + a real SQLite database, through Flask's test client."""
from tests.conftest import SLOT, login


def order_body(**over):
    return {"canteen_id": 1, "slot_start": SLOT, "items": [{"item_id": 1, "quantity": 1}], **over}


def test_it01_protected_endpoints_need_login(client):
    for method, url in [("get", "/api/me"), ("get", "/api/canteens"), ("post", "/api/orders"), ("get", "/api/staff/queue")]:
        res = getattr(client, method)(url)
        assert res.status_code == 401 and res.get_json()["error"] == "unauthorized"


def test_it02_roles_are_enforced(client):
    login(client, "student@iiita.ac.in", "student123")
    assert client.get("/api/staff/queue").status_code == 403
    assert client.get("/api/admin/report").status_code == 403
    login(client, "staff@iiita.ac.in", "staff1234")
    assert client.post("/api/orders", json=order_body()).status_code == 403
    assert client.patch("/api/admin/items/1", json={"stock": 1}).status_code == 403


def test_it03_register_logs_in_and_logout_ends_session(client):
    res = client.post("/api/auth/register", json={"name": "Ravi", "email": "ravi@iiita.ac.in", "password": "longpass1"})
    assert res.status_code == 201 and res.get_json()["role"] == "student"
    assert client.get("/api/me").get_json()["email"] == "ravi@iiita.ac.in"
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401


def test_it04_bad_login_and_bad_json_return_clear_errors(client):
    assert client.post("/api/auth/login", json={"email": "student@iiita.ac.in", "password": "x"}).status_code == 401
    login(client, "student@iiita.ac.in", "student123")
    res = client.post("/api/orders", data="not json", content_type="application/json")
    assert res.status_code == 400 and res.get_json()["error"] == "validation_error"


def test_it05_menu_and_slots(client):
    login(client, "student@iiita.ac.in", "student123")
    menu = client.get("/api/canteens/1/menu").get_json()
    assert menu["canteen"]["name"] == "Main Canteen" and len(menu["items"]) == 9
    slots = client.get("/api/canteens/1/slots").get_json()
    assert len(slots) == 52 and slots[0]["available"] is False
    assert client.get("/api/canteens/99/menu").status_code == 404


def test_it06_place_order_then_see_it_in_my_orders_and_wallet(client):
    login(client, "student@iiita.ac.in", "student123")
    res = client.post("/api/orders", json=order_body(items=[{"item_id": 3, "quantity": 2}]))
    assert res.status_code == 201
    order = res.get_json()
    assert order["total_paise"] == 16000 and order["canteen_name"] == "Main Canteen"
    assert [o["id"] for o in client.get("/api/orders").get_json()] == [order["id"]]
    assert client.get("/api/me").get_json()["wallet_paise"] == 34000


def test_it07_business_rule_errors_map_to_409(client):
    login(client, "student@iiita.ac.in", "student123")
    res = client.post("/api/orders", json=order_body(items=[{"item_id": 1, "quantity": 10}, {"item_id": 3, "quantity": 10}]))
    assert res.status_code == 409 and res.get_json()["error"] == "insufficient_balance"
    res = client.post("/api/orders", json=order_body(slot_start="2026-11-19T09:00"))
    assert res.status_code == 409 and res.get_json()["error"] == "slot_unavailable"


def test_it08_students_cannot_read_each_others_orders(client):
    login(client, "student@iiita.ac.in", "student123")
    order_id = client.post("/api/orders", json=order_body()).get_json()["id"]
    client.post("/api/auth/register", json={"name": "Other", "email": "other@iiita.ac.in", "password": "longpass1"})
    assert client.get(f"/api/orders/{order_id}").status_code == 403


def test_it09_staff_sees_the_order_and_moves_it_along(client):
    login(client, "student@iiita.ac.in", "student123")
    order = client.post("/api/orders", json=order_body()).get_json()
    login(client, "staff@iiita.ac.in", "staff1234")
    queue = client.get("/api/staff/queue").get_json()
    assert queue[0]["slot_start"] == SLOT and queue[0]["orders"][0]["id"] == order["id"]
    res = client.post(f"/api/staff/orders/{order['id']}/status", json={"status": "READY"})
    assert res.status_code == 409 and res.get_json()["error"] == "invalid_transition"
    res = client.post(f"/api/staff/orders/{order['id']}/status", json={"status": "ACCEPTED"})
    assert res.get_json()["status"] == "ACCEPTED"


def test_it10_admin_menu_slots_topup_and_report(client):
    login(client, "admin@iiita.ac.in", "admin1234")
    res = client.post("/api/admin/canteens/1/items", json={"name": "Poha", "category": "Breakfast", "price_paise": 2500, "stock": 10})
    assert res.status_code == 201
    assert client.patch(f"/api/admin/items/{res.get_json()['id']}", json={"stock": 3}).get_json()["stock"] == 3
    assert client.patch("/api/admin/canteens/1/slots", json={"slot_minutes": 30, "slot_capacity": 25}).status_code == 200
    assert client.post("/api/admin/wallets/topup", json={"email": "student@iiita.ac.in", "amount_paise": 5000}).get_json()["wallet_paise"] == 55000
    assert client.get("/api/admin/report?date=bad").status_code == 400
    assert client.get("/api/admin/report").get_json()["orders_total"] == 0


def test_it11_health_and_index_are_served(client):
    assert client.get("/health").get_json() == {"status": "ok"}
    assert b"ReadySteady" in client.get("/").data
