import pytest

from app.errors import Conflict
from app.order_state import TERMINAL, Status, assert_transition, can_transition, parse_status


@pytest.mark.parametrize("a, b", [
    ("PLACED", "ACCEPTED"), ("PLACED", "REJECTED"), ("PLACED", "CANCELLED"),
    ("ACCEPTED", "PREPARING"), ("PREPARING", "READY"), ("READY", "PICKED_UP"),
])
def test_ut01_allowed_transitions(a, b):
    assert can_transition(a, b)


@pytest.mark.parametrize("a, b", [
    ("PLACED", "READY"), ("PLACED", "PICKED_UP"), ("ACCEPTED", "CANCELLED"),
    ("READY", "PREPARING"), ("PREPARING", "PLACED"),
])
def test_ut02_skipping_or_going_back_is_refused(a, b):
    assert not can_transition(a, b)
    with pytest.raises(Conflict) as e:
        assert_transition(a, b)
    assert e.value.code == "invalid_transition"


@pytest.mark.parametrize("terminal", sorted(TERMINAL, key=lambda s: s.value))
def test_ut03_terminal_states_have_no_exit(terminal):
    assert all(not can_transition(terminal, s) for s in Status)


def test_ut04_parse_status_is_case_insensitive_and_rejects_unknown():
    assert parse_status("ready") is Status.READY
    with pytest.raises(Conflict):
        parse_status("EATEN")
