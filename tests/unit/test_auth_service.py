import pytest

from app.errors import Conflict, Unauthorized, ValidationError
from app.repository import UserRepo
from app.services import auth_service
from tests.conftest import NOW


def test_ut10_register_stores_a_salted_hash_not_the_password(conn):
    u = auth_service.register_student(conn, "Asha", "Asha@IIITA.ac.in", "secret123", NOW, ".ac.in")
    row = UserRepo.get(conn, u["id"])
    assert row["email"] == "asha@iiita.ac.in" and row["role"] == "student"
    assert "secret123" not in row["password_hash"] and row["password_hash"].startswith("pbkdf2:sha256")
    assert "password_hash" not in u


@pytest.mark.parametrize("name, email, password, code", [
    ("", "a@iiita.ac.in", "secret123", "validation_error"),
    ("Asha", "not-an-email", "secret123", "validation_error"),
    ("Asha", "asha@gmail.com", "secret123", "email_domain"),
    ("Asha", "asha@iiita.ac.in", "short", "validation_error"),
])
def test_ut11_register_validates_input(conn, name, email, password, code):
    with pytest.raises(ValidationError) as e:
        auth_service.register_student(conn, name, email, password, NOW, ".ac.in")
    assert e.value.code == code


def test_ut12_duplicate_email_is_refused(conn):
    with pytest.raises(Conflict):
        auth_service.register_student(conn, "Again", "student@iiita.ac.in", "secret123", NOW, ".ac.in")


def test_ut13_login_checks_password_with_one_generic_message(conn):
    assert auth_service.login(conn, "STUDENT@iiita.ac.in", "student123")["role"] == "student"
    with pytest.raises(Unauthorized) as wrong_pw:
        auth_service.login(conn, "student@iiita.ac.in", "nope")
    with pytest.raises(Unauthorized) as no_user:
        auth_service.login(conn, "ghost@iiita.ac.in", "nope")
    assert wrong_pw.value.message == no_user.value.message
