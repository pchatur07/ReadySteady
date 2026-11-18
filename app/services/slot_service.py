"""Pickup slots: generation, availability and validation (FR-05, FR-14)."""
from datetime import datetime, timedelta

from ..errors import Conflict, ValidationError
from ..order_state import HOLDS_SLOT
from ..repository import OrderRepo
from . import TIME_FMT

MIN_LEAD_MINUTES = 10  # the kitchen needs at least 10 minutes before a slot starts


def _at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m)


def slot_starts(canteen, day):
    start, end = _at(day, canteen["open_time"]), _at(day, canteen["close_time"])
    step = timedelta(minutes=canteen["slot_minutes"])
    t = start
    while t + step <= end:
        yield t
        t += step


def list_slots(conn, canteen, now):
    day = now.date()
    booked = OrderRepo.counts_by_slot(conn, canteen["id"], day.isoformat(), [s.value for s in HOLDS_SLOT])
    cutoff = now + timedelta(minutes=MIN_LEAD_MINUTES)
    slots = []
    for t in slot_starts(canteen, day):
        key = t.strftime(TIME_FMT)
        taken = booked.get(key, 0)
        remaining = max(canteen["slot_capacity"] - taken, 0)
        slots.append({
            "start": key,
            "label": f"{t:%H:%M} to {(t + timedelta(minutes=canteen['slot_minutes'])):%H:%M}",
            "capacity": canteen["slot_capacity"],
            "booked": taken,
            "remaining": remaining,
            "available": remaining > 0 and t >= cutoff,
        })
    return slots


def validate_slot(canteen, slot_start, now):
    """Return the slot's datetime, or raise if it is malformed, misaligned or too soon."""
    try:
        t = datetime.strptime(slot_start or "", TIME_FMT)
    except ValueError:
        raise ValidationError("Pickup slot must look like 2026-11-19T12:30.") from None
    if t not in set(slot_starts(canteen, t.date())):
        raise ValidationError("That is not a pickup slot for this canteen.", code="invalid_slot")
    if t.date() != now.date() or t < now + timedelta(minutes=MIN_LEAD_MINUTES):
        raise Conflict(
            f"Choose a slot today, at least {MIN_LEAD_MINUTES} minutes from now.", code="slot_unavailable"
        )
    return t
