"""Reservation Module (VPS-F-015, VPS-F-016).

* Drivers may book a slot up to 48 h in advance for a 1-24 h window.
* Booking locks the nearest vacant slot of the category (status RESERVED)
  and issues an 8-character reservation code.
* Check-in at the entry lane is allowed from 60 min before the start time
  until 30 min after it; the plate must match the booking.
* A scheduler releases bookings whose holder has not arrived 30 min after
  the start time (status EXPIRED, slot back to VACANT).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from vps.allocation import get_allocation
from vps.audit import get_audit
from vps.context import parse_ts
from vps.errors import Conflict, NotFound, SecurityViolation, ValidationError
from vps.plates import mask_plate, validate_category, validate_plate
from vps.security import get_vault

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O/1/I confusion
EARLY_CHECKIN_MINUTES = 60


class ReservationService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.alloc = get_allocation(ctx)
        self.vault = get_vault(ctx)
        self.audit = get_audit(ctx)

    def _view(self, r: dict) -> dict:
        return {
            "reservation_id": r["id"], "code": r["code"], "status": r["status"], "category": r["category"],
            "slot_id": r["slot_id"], "level": self.alloc.get(r["slot_id"])["level"],
            "plate_masked": mask_plate(self.vault.decrypt(r["plate_enc"])),
            "start_time": r["start_time"], "end_time": r["end_time"],
            "no_show_deadline": (parse_ts(r["start_time"])
                                 + timedelta(minutes=self.ctx.settings.no_show_minutes)).isoformat(),
        }

    def _by_code(self, code: str) -> dict:
        r = self.db.query_one("SELECT * FROM reservations WHERE code = ?", ((code or "").strip().upper(),))
        if not r:
            raise NotFound("Reservation not found")
        return r

    # ------------------------------------------------------------------ booking
    def create(self, plate_number: str, category: str, start_time, duration_hours: int = 2,
               contact: str | None = None) -> dict:
        plate = validate_plate(plate_number)
        category = validate_category(category)
        try:
            start = parse_ts(start_time)
        except (TypeError, ValueError):
            raise ValidationError("start_time must be ISO-8601") from None
        now = self.ctx.now()
        if start < now - timedelta(minutes=5):
            raise ValidationError("start_time is in the past", code="INVALID_WINDOW")
        if start > now + timedelta(hours=self.ctx.settings.reservation_window_hours):
            raise ValidationError("Reservations are allowed at most 48 hours in advance", code="INVALID_WINDOW")
        if not 1 <= int(duration_hours) <= 24:
            raise ValidationError("duration_hours must be between 1 and 24", code="INVALID_WINDOW")
        fp = self.vault.fingerprint(plate)
        if self.db.query_one("SELECT 1 FROM reservations WHERE plate_fp = ? AND status = 'BOOKED'", (fp,)):
            raise Conflict("This vehicle already has an active reservation", code="DUPLICATE_RESERVATION")
        slot = self.alloc.reserve_slot(category)
        rid = str(uuid.uuid4())
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        self.db.execute(
            "INSERT INTO reservations (id, code, plate_enc, plate_fp, category, slot_id, start_time, end_time, status,"
            " contact_enc, created_at) VALUES (?,?,?,?,?,?,?,?, 'BOOKED', ?,?)",
            (rid, code, self.vault.encrypt(plate), fp, category, slot["id"], start.isoformat(),
             (start + timedelta(hours=int(duration_hours))).isoformat(),
             self.vault.encrypt(contact) if contact else None, now.isoformat()),
        )
        return self._view(self._by_code(code))

    def get(self, code: str) -> dict:
        return self._view(self._by_code(code))

    def list(self, status: str | None = None, limit: int = 200) -> list[dict]:
        if status:
            rows = self.db.query("SELECT * FROM reservations WHERE status = ? ORDER BY start_time LIMIT ?",
                                 (status, limit))
        else:
            rows = self.db.query("SELECT * FROM reservations ORDER BY start_time DESC LIMIT ?", (limit,))
        return [self._view(r) for r in rows]

    def cancel(self, code: str, plate_number: str) -> dict:
        r = self._by_code(code)
        if r["plate_fp"] != self.vault.fingerprint(validate_plate(plate_number)):
            raise SecurityViolation("Plate does not match reservation", code="RESERVATION_MISMATCH")
        if r["status"] != "BOOKED":
            raise Conflict(f"Reservation is {r['status']}", code="RESERVATION_NOT_ACTIVE")
        self._close(r, "CANCELLED")
        return self.get(code)

    # ------------------------------------------------------------------ arrival
    def check_in(self, code: str, plate: str, category: str) -> dict:
        r = self._by_code(code)
        if r["plate_fp"] != self.vault.fingerprint(plate):
            raise SecurityViolation("Plate does not match reservation", code="RESERVATION_MISMATCH")
        if r["status"] != "BOOKED":
            raise Conflict(f"Reservation is {r['status']}", code="RESERVATION_NOT_ACTIVE")
        if r["category"] != category:
            raise ValidationError(f"Reservation is for category {r['category']}", code="RESERVATION_MISMATCH")
        now, start = self.ctx.now(), parse_ts(r["start_time"])
        if now < start - timedelta(minutes=EARLY_CHECKIN_MINUTES):
            raise Conflict("Too early for this reservation", code="RESERVATION_TOO_EARLY")
        if now > start + timedelta(minutes=self.ctx.settings.no_show_minutes):
            self._close(r, "EXPIRED")
            raise Conflict("Reservation expired (no-show window passed)", code="RESERVATION_EXPIRED")
        self.alloc.claim_reserved(r["slot_id"])
        self.db.execute("UPDATE reservations SET status = 'CHECKED_IN', updated_at = ? WHERE id = ?",
                        (now.isoformat(), r["id"]))
        return {**r, "status": "CHECKED_IN"}

    def release_no_shows(self) -> list[str]:
        cutoff = self.ctx.now() - timedelta(minutes=self.ctx.settings.no_show_minutes)
        released = []
        for r in self.db.query("SELECT * FROM reservations WHERE status = 'BOOKED'"):
            if parse_ts(r["start_time"]) < cutoff:
                self._close(r, "EXPIRED")
                released.append(r["code"])
        if released:
            self.audit.record("scheduler", "NO_SHOW_RELEASED", {"codes": released})
        return released

    def _close(self, r: dict, status: str) -> None:
        with self.db.transaction():
            self.db.execute("UPDATE reservations SET status = ?, updated_at = ? WHERE id = ?",
                            (status, self.ctx.now_iso(), r["id"]))
            slot = self.alloc.get(r["slot_id"])
            if slot["status"] == "RESERVED":
                self.alloc.release(r["slot_id"])


def get_reservations(ctx) -> ReservationService:
    return ctx.service("reservations", ReservationService)
