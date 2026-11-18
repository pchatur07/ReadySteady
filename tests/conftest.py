import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.db import connect  # noqa: E402
from app.repository import UserRepo  # noqa: E402
from app.services.auth_service import public_user  # noqa: E402
from seed import seed  # noqa: E402

# Every test runs at a fixed time: 11:00 on evaluation day.
NOW = datetime(2026, 11, 19, 11, 0)
SLOT = "2026-11-19T12:30"


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def app(db_path):
    app = create_app({"DATABASE": db_path, "TESTING": True, "SECRET_KEY": "test", "CLOCK": lambda: NOW})
    conn = connect(db_path)
    seed(conn, NOW)
    conn.close()
    return app


@pytest.fixture
def conn(app, db_path):
    c = connect(db_path)
    yield c
    c.close()


@pytest.fixture
def client(app):
    return app.test_client()


def user(conn, email):
    return public_user(UserRepo.by_email(conn, email))


@pytest.fixture
def student(conn):
    return user(conn, "student@iiita.ac.in")


@pytest.fixture
def staff(conn):
    return user(conn, "staff@iiita.ac.in")


@pytest.fixture
def admin(conn):
    return user(conn, "admin@iiita.ac.in")


def login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.get_json()
    return res.get_json()
