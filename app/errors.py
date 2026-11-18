"""Domain exceptions. Each maps to one HTTP status and a stable machine-readable code."""


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code

    def to_dict(self):
        return {"error": self.code, "message": self.message}


class ValidationError(AppError):
    status = 400
    code = "validation_error"


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class Forbidden(AppError):
    status = 403
    code = "forbidden"


class NotFound(AppError):
    status = 404
    code = "not_found"


class Conflict(AppError):
    """A valid request that the current state of the system does not allow
    (slot full, out of stock, low balance, invalid status change)."""
    status = 409
    code = "conflict"
