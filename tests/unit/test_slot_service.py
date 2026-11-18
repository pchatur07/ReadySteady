from datetime import datetime

import pytest

from app.errors import Conflict, ValidationError
from app.repository import CanteenRepo
from app.services import slot_service
from tests.conftest import NOW


def main_canteen(conn):
    return CanteenRepo.get(conn, 1)


def test_ut05_slots_cover_opening_hours_in_15_minute_steps(conn):
    slots = list(slot_service.slot_starts(main_canteen(conn), NOW.date()))
    assert len(slots) == 52                                   # 08:00 to 21:00
    assert slots[0] == datetime(2026, 11, 19, 8, 0)
    assert slots[-1] == datetime(2026, 11, 19, 20, 45)


def test_ut06_past_and_too_soon_slots_are_not_available(conn):
    slots = {s["start"]: s for s in slot_service.list_slots(conn, main_canteen(conn), NOW)}
    assert not slots["2026-11-19T10:45"]["available"]         # already passed
    assert not slots["2026-11-19T11:00"]["available"]         # less than 10 min lead
    assert slots["2026-11-19T11:15"]["available"]
    assert slots["2026-11-19T11:15"]["remaining"] == 20


@pytest.mark.parametrize("bad", ["", "tomorrow", "2026-11-19 12:30", "2026-11-19T12:07", "2026-11-19T07:45"])
def test_ut07_malformed_or_misaligned_slot_is_a_validation_error(conn, bad):
    with pytest.raises(ValidationError):
        slot_service.validate_slot(main_canteen(conn), bad, NOW)


@pytest.mark.parametrize("too_soon", ["2026-11-19T11:00", "2026-11-19T09:00", "2026-11-20T12:00"])
def test_ut08_past_or_other_day_slot_is_refused(conn, too_soon):
    with pytest.raises(Conflict) as e:
        slot_service.validate_slot(main_canteen(conn), too_soon, NOW)
    assert e.value.code == "slot_unavailable"


def test_ut09_valid_slot_returns_its_time(conn):
    assert slot_service.validate_slot(main_canteen(conn), "2026-11-19T12:30", NOW) == datetime(2026, 11, 19, 12, 30)
