"""Ingress Module (VPS-F-001..004, VPS-NF-001, VPS-SR-004).

Flow (SAD 4.2, Flow 1): ANPR read -> slot request -> signed QR ticket ->
dispense ticket -> raise barrier -> ground-loop safety -> lower barrier.
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

from vps.alerts import get_alerts
from vps.allocation import get_allocation
from vps.audit import get_audit
from vps.context import parse_ts
from vps.edge_queue import get_edge
from vps.errors import Conflict, HardwareFault, NotFound, ValidationError
from vps.hardware import get_hardware
from vps.plates import mask_plate, validate_category, validate_plate
from vps.security import get_signer, get_vault


class IngressService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.hw = get_hardware(ctx)
        self.alloc = get_allocation(ctx)
        self.signer = get_signer(ctx)
        self.vault = get_vault(ctx)
        self.edge = get_edge(ctx)
        self.audit = get_audit(ctx)
        self.alerts = get_alerts(ctx)

    # ------------------------------------------------------------------ helpers
    def _resolve_timestamp(self, timestamp) -> str:
        now = self.ctx.now()
        if timestamp is None:
            return now.isoformat()
        try:
            ts = parse_ts(timestamp)
        except (TypeError, ValueError):
            raise ValidationError("timestamp must be ISO-8601") from None
        if ts > now + timedelta(seconds=5):
            raise ValidationError("timestamp cannot be in the future")
        if now - ts > timedelta(hours=self.ctx.settings.max_entry_backdate_hours):
            raise ValidationError("timestamp is older than the edge offline window")
        return ts.isoformat()

    def get_ticket(self, ticket_id: str) -> dict:
        t = self.db.query_one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not t:
            raise NotFound(f"Ticket {ticket_id} not found")
        return t

    def find_active_by_plate(self, plate: str) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM tickets WHERE plate_fp = ? AND status = 'ACTIVE' ORDER BY entry_time DESC LIMIT 1",
            (self.vault.fingerprint(plate),),
        )

    def public_view(self, ticket: dict) -> dict:
        plate = self.vault.decrypt(ticket["plate_enc"])
        return {
            "ticket_id": ticket["id"],
            "plate_masked": mask_plate(plate),
            "category": ticket["category"],
            "slot_id": ticket["slot_id"],
            "entry_time": ticket["entry_time"],
            "exit_time": ticket["exit_time"],
            "status": ticket["status"],
            "amount": ticket["amount"],
        }

    # ------------------------------------------------------------------ main flow
    def process_entry(self, lane_id: str, plate_number: str, vehicle_category: str, *,
                      confidence: float = 0.97, timestamp=None, reservation_code: str | None = None,
                      attendant: str | None = None) -> dict:
        t0 = time.perf_counter()
        lane = self.hw.get(lane_id, direction="ENTRY")
        category = validate_category(vehicle_category)

        # 1-2. plate capture (attendant manual entry bypasses the OCR confidence gate)
        if attendant:
            plate, mode = validate_plate(plate_number), "MANUAL"
        else:
            plate, mode = lane.camera.capture(plate_number, confidence).plate, "ANPR"
        t_plate = time.perf_counter()

        fp = self.vault.fingerprint(plate)
        if self.find_active_by_plate(plate):
            raise Conflict("Vehicle already has an active ticket (anti-passback)", code="VEHICLE_ALREADY_INSIDE",
                           details={"plate": mask_plate(plate)})
        entry_time = self._resolve_timestamp(timestamp)

        # 3-4. slot request
        reservation_id = None
        if reservation_code:
            from vps.reservation import get_reservations  # optional module (Sprint 2)
            res = get_reservations(self.ctx).check_in(reservation_code, plate, category)
            slot = self.alloc.get(res["slot_id"])
            reservation_id = res["id"]
        else:
            slot = self.alloc.allocate(category)

        # 5. signed ticket
        ticket_id = str(uuid.uuid4())
        qr = self.signer.sign({"tid": ticket_id, "slot": slot["id"], "ts": entry_time, "pf": fp[:12]})
        self.db.execute(
            "INSERT INTO tickets (id, plate_enc, plate_fp, category, slot_id, entry_lane, entry_time, status,"
            " qr_payload, reservation_id, entry_mode, created_at) VALUES (?,?,?,?,?,?,?, 'ACTIVE', ?,?,?,?)",
            (ticket_id, self.vault.encrypt(plate), fp, category, slot["id"], lane_id, entry_time, qr,
             reservation_id, mode, self.ctx.now_iso()),
        )
        t_ticket = time.perf_counter()

        # 6. dispense ticket (printer fault -> attendant alert + digital ticket fallback)
        delivery = "PRINTED"
        try:
            lane.printer.print_ticket({"ticket_id": ticket_id, "slot": slot["id"], "qr": qr})
        except HardwareFault as exc:
            delivery = "DIGITAL_ONLY"
            self.alerts.raise_alert("PRINTER_FAULT", exc.message, "WARNING", lane_id)

        # 7-8. raise barrier
        barrier = lane.barrier.raise_barrier()
        t_end = time.perf_counter()

        self.edge.record(lane_id, "ENTRY", {"ticket_id": ticket_id, "slot": slot["id"], "category": category,
                                            "entry_time": entry_time, "mode": mode})
        if attendant:
            self.audit.record(attendant, "MANUAL_ENTRY", {"ticket_id": ticket_id, "lane": lane_id,
                                                          "plate": mask_plate(plate)})
        ms = lambda a, b: round((b - a) * 1000, 3)  # noqa: E731
        return {
            "ticket_id": ticket_id,
            "qr_payload": qr,
            "allocated_slot": slot["id"],
            "level": slot["level"],
            "category": category,
            "entry_time": entry_time,
            "plate_masked": mask_plate(plate),
            "entry_mode": mode,
            "ticket_delivery": delivery,
            "reservation_id": reservation_id,
            "barrier": barrier["state"],
            "timings_ms": {"plate_capture": ms(t0, t_plate), "ticket_issue": ms(t_plate, t_ticket),
                           "barrier_raise": barrier["latency_ms"], "total": ms(t0, t_end)},
        }


def get_ingress(ctx) -> IngressService:
    return ctx.service("ingress", IngressService)
