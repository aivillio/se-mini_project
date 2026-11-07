"""Egress Module (VPS-F-011, VPS-F-012, VPS-F-013, VPS-SR-004).

Flow (SAD 4.2, Flow 2): scan QR / plate -> fetch invoice -> pay (UPI/card/wallet)
-> gateway webhook PAID -> raise exit barrier -> release slot -> receipt.
The exit barrier is never raised for a ticket that is not PAID.
"""

from __future__ import annotations

import json
import time

from vps.alerts import get_alerts
from vps.allocation import get_allocation
from vps.audit import get_audit
from vps.edge_queue import get_edge
from vps.errors import Conflict, Forbidden, NotFound, SecurityViolation, ValidationError
from vps.hardware import get_hardware
from vps.ingress import get_ingress
from vps.payment import get_payments
from vps.plates import mask_plate, validate_plate
from vps.security import get_signer
from vps.tariff import get_tariff_engine


class EgressService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.hw = get_hardware(ctx)
        self.ingress = get_ingress(ctx)
        self.tariff = get_tariff_engine(ctx)
        self.payments = get_payments(ctx)
        self.signer = get_signer(ctx)
        self.alloc = get_allocation(ctx)
        self.edge = get_edge(ctx)
        self.audit = get_audit(ctx)
        self.alerts = get_alerts(ctx)

    # ------------------------------------------------------------------ lookup
    def _ticket_from_qr(self, qr_payload: str, lane_id: str) -> dict:
        try:
            claims = self.signer.verify(qr_payload)
        except SecurityViolation:
            self.audit.record("system", "COUNTERFEIT_TICKET", {"lane": lane_id, "payload_prefix": qr_payload[:24]})
            self.alerts.raise_alert("COUNTERFEIT_TICKET", "Tampered QR ticket presented at exit", "CRITICAL", lane_id)
            raise
        ticket = self.ingress.get_ticket(claims["tid"])
        if ticket["qr_payload"] != qr_payload.strip():
            raise SecurityViolation("QR does not match issued ticket", code="TAMPERED_TICKET")
        return ticket

    def lookup(self, *, qr_payload: str | None = None, plate_number: str | None = None,
               coupon_code: str | None = None, lane_id: str = "EXIT-1") -> dict:
        start = time.perf_counter()
        if qr_payload:
            ticket = self._ticket_from_qr(qr_payload, lane_id)
        elif plate_number:
            ticket = self.ingress.find_active_by_plate(validate_plate(plate_number))
            if not ticket:
                raise NotFound("No active parking session for this vehicle")
        else:
            raise ValidationError("Provide qr_payload or plate_number")
        view = self.ingress.public_view(ticket)
        if ticket["status"] != "ACTIVE":
            return {**view, "invoice": None, "message": f"Ticket already {ticket['status']}",
                    "latency_ms": round((time.perf_counter() - start) * 1000, 3)}
        fare = self.tariff.calculate(ticket["category"], ticket["entry_time"], self.ctx.now(), coupon_code)
        return {**view, "invoice": fare.to_dict(), "latency_ms": round((time.perf_counter() - start) * 1000, 3)}

    # ------------------------------------------------------------------ checkout
    def checkout(self, ticket_id: str, payment_method: str, *, coupon_code: str | None = None,
                 card_number: str | None = None, lane_id: str = "EXIT-1") -> dict:
        self.hw.get(lane_id, direction="EXIT")
        ticket = self.ingress.get_ticket(ticket_id)
        if ticket["status"] != "ACTIVE":
            raise Conflict(f"Ticket already {ticket['status']}", code="TICKET_NOT_ACTIVE")
        fare = self.tariff.calculate(ticket["category"], ticket["entry_time"], self.ctx.now(), coupon_code).to_dict()
        if fare["total"] == 0:   # grace period / 100% coupon: no payment needed (VPS-F-009)
            order = self.payments.create_order(ticket_id, 0.0, "none", fare, coupon_code=fare["coupon_code"])
            return self._finalize(order["order_id"], lane_id, gateway_ref="ZERO_FARE")
        order = self.payments.create_order(ticket_id, fare["total"], payment_method, fare,
                                           card_number=card_number, coupon_code=fare["coupon_code"])
        return {"status": "PENDING", "barrier_action": "HOLD", "order": order, "invoice": fare, "receipt_url": None}

    def handle_webhook(self, body: bytes, signature: str | None, lane_id: str = "EXIT-1") -> dict:
        event = self.payments.verify_webhook(body, signature)
        order = self.payments.get(event["order_id"])
        if order["status"] == "CAPTURED":       # idempotent re-delivery
            return self.status(order["ticket_id"])
        if event["event"] == "payment.captured":
            if abs(float(event["amount"]) - order["amount"]) > 0.001:
                raise SecurityViolation("Webhook amount mismatch", code="AMOUNT_MISMATCH")
            return self._finalize(order["id"], lane_id, gateway_ref=event.get("payment_id"))
        self.payments.mark(order["id"], "FAILED", event.get("payment_id"))
        self.alerts.raise_alert("PAYMENT_FAILED", f"Payment failed for order {order['id']}", "WARNING", lane_id)
        return {"status": "FAILED", "barrier_action": "HOLD", "ticket_id": order["ticket_id"], "receipt_url": None}

    def cash_payment(self, ticket_id: str, attendant: str, lane_id: str = "EXIT-1") -> dict:
        ticket = self.ingress.get_ticket(ticket_id)
        if ticket["status"] != "ACTIVE":
            raise Conflict(f"Ticket already {ticket['status']}", code="TICKET_NOT_ACTIVE")
        fare = self.tariff.calculate(ticket["category"], ticket["entry_time"], self.ctx.now()).to_dict()
        order = self.payments.create_order(ticket_id, fare["total"], "cash", fare)
        self.audit.record(attendant, "CASH_COLLECTED", {"ticket_id": ticket_id, "amount": fare["total"], "lane": lane_id})
        return self._finalize(order["order_id"], lane_id, gateway_ref=f"CASH:{attendant}")

    def _finalize(self, order_id: str, lane_id: str, gateway_ref: str | None) -> dict:
        order = self.payments.mark(order_id, "CAPTURED", gateway_ref)
        fare = json.loads(order["fare_json"])
        ticket_id = order["ticket_id"]
        with self.db.transaction():
            cur = self.db.execute(
                "UPDATE tickets SET status = 'PAID', amount = ?, exit_time = ?, exit_lane = ? "
                "WHERE id = ? AND status = 'ACTIVE'", (order["amount"], fare["exit_time"], lane_id, ticket_id))
            if cur.rowcount == 0:
                raise Conflict("Ticket was already settled", code="TICKET_NOT_ACTIVE")
        if order["coupon_code"]:
            self.tariff.redeem_coupon(order["coupon_code"])
        barrier = self.open_exit_barrier(ticket_id, lane_id)
        ticket = self.ingress.get_ticket(ticket_id)
        self.alloc.release(ticket["slot_id"])
        from vps.sensors import get_sensor_hub
        get_sensor_hub(self.ctx).refresh_vms()
        self.edge.record(lane_id, "EXIT", {"ticket_id": ticket_id, "amount": order["amount"],
                                           "method": order["method"], "exit_time": fare["exit_time"]})
        return {"status": "PAID", "ticket_id": ticket_id, "amount": order["amount"], "method": order["method"],
                "receipt_url": f"/api/v1/receipts/{ticket_id}.pdf", "barrier_action": "OPEN",
                "barrier": barrier["state"], "invoice": fare}

    # ------------------------------------------------------------------ gate
    def open_exit_barrier(self, ticket_id: str, lane_id: str) -> dict:
        ticket = self.ingress.get_ticket(ticket_id)
        if ticket["status"] not in ("PAID", "CLOSED"):
            raise Forbidden("Exit barrier cannot open for an unpaid ticket", code="UNPAID_TICKET")
        lane = self.hw.get(lane_id, direction="EXIT")
        return lane.barrier.raise_barrier()

    def status(self, ticket_id: str) -> dict:
        t = self.ingress.get_ticket(ticket_id)
        paid = t["status"] in ("PAID", "CLOSED")
        return {"ticket_id": ticket_id, "status": t["status"], "amount": t["amount"],
                "barrier_action": "OPEN" if paid else "HOLD",
                "receipt_url": f"/api/v1/receipts/{ticket_id}.pdf" if paid else None,
                "plate_masked": mask_plate(self.ingress.vault.decrypt(t["plate_enc"]))}


def get_egress(ctx) -> EgressService:
    return ctx.service("egress", EgressService)
