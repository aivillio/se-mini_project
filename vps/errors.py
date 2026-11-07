"""Error hierarchy (SAD 4.4 Error Handling).

Every domain error carries a stable machine-readable ``code`` and an HTTP status,
so the API layer can translate it into a uniform JSON error body:
``{"error": {"code": "...", "message": "...", "details": {...}}}``.
"""

from __future__ import annotations


class VPSError(Exception):
    status = 400
    code = "VPS_ERROR"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationError(VPSError):
    status = 400
    code = "INVALID_INPUT"


class InvalidPlate(VPSError):
    status = 400
    code = "INVALID_PLATE"


class PlateUnreadable(VPSError):
    status = 422
    code = "PLATE_UNREADABLE"


class NotFound(VPSError):
    status = 404
    code = "NOT_FOUND"


class Conflict(VPSError):
    status = 409
    code = "CONFLICT"


class LotFull(VPSError):
    status = 409
    code = "LOT_FULL"


class AuthError(VPSError):
    status = 401
    code = "UNAUTHENTICATED"


class Forbidden(VPSError):
    status = 403
    code = "FORBIDDEN"


class SecurityViolation(VPSError):
    status = 403
    code = "SECURITY_VIOLATION"


class PaymentError(VPSError):
    status = 402
    code = "PAYMENT_FAILED"


class EdgeOffline(VPSError):
    status = 503
    code = "EDGE_CONTROLLER_OFFLINE"


class HardwareFault(VPSError):
    status = 503
    code = "HARDWARE_FAULT"
