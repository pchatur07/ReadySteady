"""Registration, login and role checks (FR-01, FR-02)."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import Conflict, Unauthorized, ValidationError
from ..repository import UserRepo
from . import stamp

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
HASH_METHOD = "pbkdf2:sha256:600000"
MIN_PASSWORD = 8


def public_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "canteen_id": user["canteen_id"],
        "wallet_paise": user["wallet_paise"],
    }


def register_student(conn, name, email, password, now, allowed_suffix):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name or len(name) > 80:
        raise ValidationError("Name is required (up to 80 characters).")
    if not EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address.")
    if allowed_suffix and not email.endswith(allowed_suffix):
        raise ValidationError(f"Use your college email (ending in {allowed_suffix}).", code="email_domain")
    if not password or len(password) < MIN_PASSWORD:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD} characters.")
    if UserRepo.by_email(conn, email):
        raise Conflict("An account with this email already exists.", code="email_taken")
    user_id = UserRepo.create(conn, name, email, generate_password_hash(password, HASH_METHOD), "student", stamp(now))
    return public_user(UserRepo.get(conn, user_id))


def create_user(conn, name, email, password, role, now, canteen_id=None, wallet_paise=0):
    """Used by the seed script and tests to create staff/admin accounts."""
    user_id = UserRepo.create(
        conn, name, email.lower(), generate_password_hash(password, HASH_METHOD), role, stamp(now), canteen_id, wallet_paise
    )
    return public_user(UserRepo.get(conn, user_id))


def login(conn, email, password):
    user = UserRepo.by_email(conn, (email or "").strip().lower())
    # Same message for unknown email and wrong password, so accounts cannot be probed.
    if not user or not check_password_hash(user["password_hash"], password or ""):
        raise Unauthorized("Wrong email or password.", code="bad_credentials")
    return public_user(user)
