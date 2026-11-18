"""Load demo data: two canteens, a menu, and one account per role.

    python seed.py            # adds demo data to the configured database (once)
"""
from datetime import datetime

from app import create_app
from app.db import connect
from app.repository import CanteenRepo, MenuRepo, UserRepo
from app.services.auth_service import create_user

MENU = {
    1: [  # Main Canteen
        ("Masala Dosa", "South Indian", 5000, 8, 40),
        ("Idli Sambar", "South Indian", 3500, 5, 40),
        ("Veg Thali", "Meals", 8000, 10, 30),
        ("Rajma Chawal", "Meals", 6000, 6, 30),
        ("Samosa (2 pcs)", "Snacks", 2000, 3, 60),
        ("Veg Sandwich", "Snacks", 3500, 5, 40),
        ("Paneer Roll", "Snacks", 6000, 7, 25),
        ("Masala Chai", "Beverages", 1000, 2, 100),
        ("Cold Coffee", "Beverages", 4000, 4, 40),
    ],
    2: [  # Night Canteen
        ("Maggi", "Snacks", 3000, 5, 50),
        ("Cheese Maggi", "Snacks", 4500, 6, 40),
        ("Egg Roll", "Snacks", 5000, 7, 30),
        ("Bread Omelette", "Snacks", 4000, 6, 30),
        ("Lemon Iced Tea", "Beverages", 3000, 2, 50),
    ],
}


def seed(conn, now=None):
    now = now or datetime.now()
    if CanteenRepo.all(conn):
        return False
    conn.execute(
        "INSERT INTO canteens (name, location, open_time, close_time, slot_minutes, slot_capacity)"
        " VALUES ('Main Canteen', 'Academic Block', '08:00', '21:00', 15, 20),"
        "        ('Night Canteen', 'Boys Hostel', '18:00', '23:45', 15, 15)"
    )
    for canteen_id, items in MENU.items():
        for name, cat, price, prep, stock in items:
            MenuRepo.create(conn, canteen_id, name, cat, price, prep, stock, True)
    create_user(conn, "Demo Student", "student@iiita.ac.in", "student123", "student", now, wallet_paise=50000)
    create_user(conn, "Counter Staff", "staff@iiita.ac.in", "staff1234", "staff", now, canteen_id=1)
    create_user(conn, "Canteen Manager", "admin@iiita.ac.in", "admin1234", "admin", now, canteen_id=1)
    return True


if __name__ == "__main__":
    app = create_app()
    c = connect(app.config["DATABASE"])
    print("Seeded demo data." if seed(c) else "Database already has data; nothing to do.")
    print("Logins: student@iiita.ac.in / student123 | staff@iiita.ac.in / staff1234 | admin@iiita.ac.in / admin1234")
    c.close()
