"""Presentation layer: JSON REST API. Routes only parse input, check roles and call services."""
from datetime import date
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from .db import get_db
from .errors import AppError, Forbidden, NotFound, Unauthorized, ValidationError
from .repository import CanteenRepo, UserRepo
from .services import auth_service, menu_service, order_service, report_service, slot_service

bp = Blueprint("api", __name__, url_prefix="/api")


def now():
    return current_app.config["CLOCK"]()


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")
    return data


def current_user():
    user_id = session.get("user_id")
    user = UserRepo.get(get_db(), user_id) if user_id else None
    return auth_service.public_user(user) if user else None


def requires(*roles):
    """Role-based access control on every protected endpoint (FR-02)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                raise Unauthorized("Please log in.")
            if roles and user["role"] not in roles:
                raise Forbidden("You do not have access to this page.")
            return fn(user, *args, **kwargs)
        return wrapper
    return deco


def staff_canteen(user):
    canteen_id = user["canteen_id"] or request.args.get("canteen_id", type=int)
    if not canteen_id:
        raise ValidationError("canteen_id is required.")
    return canteen_id


@bp.errorhandler(AppError)
def handle_app_error(err):
    return jsonify(err.to_dict()), err.status


# ---------- auth ----------
@bp.post("/auth/register")
def register():
    d = body()
    user = auth_service.register_student(
        get_db(), d.get("name"), d.get("email"), d.get("password"), now(), current_app.config["EMAIL_SUFFIX"]
    )
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(user), 201


@bp.post("/auth/login")
def login():
    d = body()
    user = auth_service.login(get_db(), d.get("email"), d.get("password"))
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(user)


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/me")
@requires()
def me(user):
    return jsonify(user)


# ---------- menu & slots (any logged-in user) ----------
@bp.get("/canteens")
@requires()
def canteens(_user):
    return jsonify(CanteenRepo.all(get_db()))


@bp.get("/canteens/<int:canteen_id>/menu")
@requires()
def canteen_menu(_user, canteen_id):
    return jsonify(menu_service.menu(get_db(), canteen_id))


@bp.get("/canteens/<int:canteen_id>/slots")
@requires()
def canteen_slots(_user, canteen_id):
    canteen = CanteenRepo.get(get_db(), canteen_id)
    if not canteen:
        raise NotFound("Canteen not found.")
    return jsonify(slot_service.list_slots(get_db(), canteen, now()))


# ---------- student orders ----------
@bp.post("/orders")
@requires("student")
def place_order(user):
    d = body()
    order = order_service.place_order(get_db(), user, d.get("canteen_id"), d.get("items"), d.get("slot_start"), now())
    return jsonify(order), 201


@bp.get("/orders")
@requires("student")
def list_orders(user):
    return jsonify(order_service.my_orders(get_db(), user))


@bp.get("/orders/<int:order_id>")
@requires()
def get_order(user, order_id):
    return jsonify(order_service.get_order_for_user(get_db(), user, order_id))


@bp.post("/orders/<int:order_id>/cancel")
@requires("student")
def cancel(user, order_id):
    return jsonify(order_service.cancel_order(get_db(), user, order_id, now()))


# ---------- staff ----------
@bp.get("/staff/queue")
@requires("staff", "admin")
def queue(user):
    return jsonify(order_service.staff_queue(get_db(), staff_canteen(user), now()))


@bp.post("/staff/orders/<int:order_id>/status")
@requires("staff", "admin")
def set_status(user, order_id):
    d = body()
    return jsonify(order_service.update_status(get_db(), user, order_id, d.get("status"), now(), d.get("token")))


# ---------- admin ----------
@bp.post("/admin/canteens/<int:canteen_id>/items")
@requires("admin")
def create_item(user, canteen_id):
    return jsonify(menu_service.create_item(get_db(), user, canteen_id, body())), 201


@bp.patch("/admin/items/<int:item_id>")
@requires("admin")
def update_item(user, item_id):
    return jsonify(menu_service.update_item(get_db(), user, item_id, body()))


@bp.patch("/admin/canteens/<int:canteen_id>/slots")
@requires("admin")
def configure_slots(user, canteen_id):
    d = body()
    return jsonify(menu_service.configure_slots(get_db(), user, canteen_id, d.get("slot_minutes"), d.get("slot_capacity")))


@bp.post("/admin/wallets/topup")
@requires("admin")
def top_up(user):
    d = body()
    return jsonify(menu_service.top_up_wallet(get_db(), user, d.get("email"), d.get("amount_paise"), now()))


@bp.get("/admin/report")
@requires("admin")
def report(user):
    day = request.args.get("date")
    try:
        day = date.fromisoformat(day) if day else now().date()
    except ValueError:
        raise ValidationError("date must look like 2026-11-19.") from None
    return jsonify(report_service.daily_report(get_db(), staff_canteen(user), day))
