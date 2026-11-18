"""Service layer: business rules. Services take a DB connection and a clock value so they
can be unit-tested without HTTP and with a fixed time."""

TIME_FMT = "%Y-%m-%dT%H:%M"


def stamp(now):
    return now.strftime("%Y-%m-%dT%H:%M:%S")
