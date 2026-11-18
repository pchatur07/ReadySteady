"""System tests: whole user journeys across all three roles, plus a concurrency check."""
import threading

from app.db import connect
from app.errors import Conflict
from app.repository import MenuRepo, UserRepo
from app.services import order_service
from app.services.auth_service import public_user
from tests.conftest import NOW, SLOT, login


def test_st01_full_order_life_cycle_across_three_roles(app):
    student, staff, admin = app.test_client(), app.test_client(), app.test_client()

    # 1. A new student signs up; the admin tops up their wallet.
    assert student.post("/api/auth/register", json={"name": "Meera", "email": "meera@iiita.ac.in", "password": "meera1234"}).status_code == 201
    login(admin, "admin@iiita.ac.in", "admin1234")
    admin.post("/api/admin/wallets/topup", json={"email": "meera@iiita.ac.in", "amount_paise": 20000})

    # 2. The student picks an available slot and orders.
    slot = next(s for s in student.get("/api/canteens/1/slots").get_json() if s["available"])["start"]
    order = student.post("/api/orders", json={"canteen_id": 1, "slot_start": slot,
                                              "items": [{"item_id": 1, "quantity": 1}, {"item_id": 8, "quantity": 2}]}).get_json()
    assert order["status"] == "PLACED" and order["total_paise"] == 7000

    # 3. Staff works through the order; the student sees each status.
    login(staff, "staff@iiita.ac.in", "staff1234")
    for status in ("ACCEPTED", "PREPARING", "READY"):
        staff.post(f"/api/staff/orders/{order['id']}/status", json={"status": status})
        assert student.get(f"/api/orders/{order['id']}").get_json()["status"] == status

    # 4. Handover with the student's token closes the order and removes it from the queue.
    res = staff.post(f"/api/staff/orders/{order['id']}/status", json={"status": "PICKED_UP", "token": order["token"]})
    assert res.get_json()["status"] == "PICKED_UP"
    assert staff.get("/api/staff/queue").get_json() == []

    # 5. The admin's report shows the sale.
    report = admin.get("/api/admin/report").get_json()
    assert report["revenue_paise"] == 7000 and report["orders_by_status"]["PICKED_UP"] == 1
    assert student.get("/api/me").get_json()["wallet_paise"] == 13000


def test_st02_cancel_journey_restores_everything(app):
    client = app.test_client()
    login(client, "student@iiita.ac.in", "student123")
    order = client.post("/api/orders", json={"canteen_id": 1, "slot_start": SLOT, "items": [{"item_id": 3, "quantity": 1}]}).get_json()
    assert client.post(f"/api/orders/{order['id']}/cancel").get_json()["status"] == "CANCELLED"
    assert client.get("/api/me").get_json()["wallet_paise"] == 50000
    assert client.post(f"/api/orders/{order['id']}/cancel").status_code == 409


def test_st03_two_students_racing_for_the_last_item_cannot_both_win(app, db_path):
    """NFR-02: stock is checked and reduced inside one write transaction."""
    setup = connect(db_path)
    MenuRepo.update(setup, 7, {"stock": 1})                                  # one Paneer Roll left
    for i in range(8):
        UserRepo.create(setup, f"S{i}", f"s{i}@iiita.ac.in", "x", "student", "t", wallet_paise=10000)
    students = [public_user(UserRepo.by_email(setup, f"s{i}@iiita.ac.in")) for i in range(8)]
    setup.close()

    results, barrier = [], threading.Barrier(len(students))

    def attempt(stu):
        conn = connect(db_path)
        barrier.wait()
        try:
            order_service.place_order(conn, stu, 1, [{"item_id": 7, "quantity": 1}], SLOT, NOW)
            results.append("ok")
        except Conflict as e:
            results.append(e.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=attempt, args=(s,)) for s in students]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check = connect(db_path)
    assert results.count("ok") == 1 and results.count("out_of_stock") == 7
    assert MenuRepo.get(check, 7)["stock"] == 0
    check.close()


def test_st04_slot_capacity_holds_under_concurrent_orders(app, db_path):
    setup = connect(db_path)
    setup.execute("UPDATE canteens SET slot_capacity = 3 WHERE id = 1")
    for i in range(10):
        UserRepo.create(setup, f"C{i}", f"c{i}@iiita.ac.in", "x", "student", "t", wallet_paise=10000)
    students = [public_user(UserRepo.by_email(setup, f"c{i}@iiita.ac.in")) for i in range(10)]
    setup.close()
    results, barrier = [], threading.Barrier(10)

    def attempt(stu):
        conn = connect(db_path)
        barrier.wait()
        try:
            order_service.place_order(conn, stu, 1, [{"item_id": 8, "quantity": 1}], SLOT, NOW)
            results.append("ok")
        except Conflict as e:
            results.append(e.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=attempt, args=(s,)) for s in students]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count("ok") == 3 and results.count("slot_full") == 7
