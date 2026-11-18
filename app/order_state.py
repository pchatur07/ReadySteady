"""Order life cycle as an explicit state machine (see the UML state diagram)."""
from enum import Enum

from .errors import Conflict


class Status(str, Enum):
    PLACED = "PLACED"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


TRANSITIONS = {
    Status.PLACED: {Status.ACCEPTED, Status.REJECTED, Status.CANCELLED},
    Status.ACCEPTED: {Status.PREPARING},
    Status.PREPARING: {Status.READY},
    Status.READY: {Status.PICKED_UP},
}

TERMINAL = {Status.PICKED_UP, Status.CANCELLED, Status.REJECTED}

# Orders in these states hold a place in their pickup slot.
HOLDS_SLOT = {Status.PLACED, Status.ACCEPTED, Status.PREPARING, Status.READY, Status.PICKED_UP}

# Moves that only staff may make; CANCELLED is the student's own move.
STAFF_TARGETS = {Status.ACCEPTED, Status.REJECTED, Status.PREPARING, Status.READY, Status.PICKED_UP}


def parse_status(value):
    try:
        return Status(str(value).upper())
    except ValueError:
        raise Conflict(f"Unknown status '{value}'.", code="invalid_status") from None


def can_transition(current, target):
    return Status(target) in TRANSITIONS.get(Status(current), set())


def assert_transition(current, target):
    if not can_transition(current, target):
        raise Conflict(
            f"Cannot move an order from {Status(current).value} to {Status(target).value}.",
            code="invalid_transition",
        )
