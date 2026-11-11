"""GST tax receipts (VPS-F-014): thermal-printer PDF, e-mail and SMS.

Parking is SAC 996743; intra-state supply -> CGST 9% + SGST 9%.
SMS/e-mail go through the notification outbox (Twilio in production, see
docs/Deviations.md DEV-04).
"""

from __future__ import annotations

import io
import json

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from vps.context import parse_ts
from vps.errors import Conflict, NotFound, ValidationError
from vps.ingress import get_ingress
from vps.plates import mask_plate

SAC_CODE = "996743"


class ReceiptService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.ingress = get_ingress(ctx)

    def invoice(self, ticket_id: str) -> dict:
        ticket = self.ingress.get_ticket(ticket_id)
        if ticket["status"] not in ("PAID", "CLOSED"):
            raise Conflict("Receipt is available only after payment", code="UNPAID_TICKET")
        pay = self.db.query_one("SELECT * FROM payments WHERE ticket_id = ? AND status = 'CAPTURED' "
                                "ORDER BY created_at DESC LIMIT 1", (ticket_id,))
        if not pay:  # pragma: no cover - PAID tickets always have a captured payment
            raise NotFound("No captured payment for ticket")
        fare = json.loads(pay["fare_json"])
        seq = self.db.scalar("SELECT COUNT(*) FROM payments WHERE status = 'CAPTURED' AND created_at <= ?",
                             (pay["created_at"],))
        issued = parse_ts(pay["updated_at"] or pay["created_at"]).astimezone(self.ctx.tz)
        fy = issued.year if issued.month >= 4 else issued.year - 1
        return {
            "invoice_no": f"VPS/{fy}-{(fy + 1) % 100:02d}/{seq:06d}",
            "issued_at": issued.isoformat(timespec="seconds"),
            "facility": self.ctx.settings.facility_name,
            "gstin": self.ctx.settings.facility_gstin,
            "sac": SAC_CODE,
            "ticket_id": ticket_id,
            "vehicle": mask_plate(self.ingress.vault.decrypt(ticket["plate_enc"])),
            "category": ticket["category"],
            "slot": ticket["slot_id"],
            "entry_time": parse_ts(fare["entry_time"]).astimezone(self.ctx.tz).isoformat(timespec="minutes"),
            "exit_time": parse_ts(fare["exit_time"]).astimezone(self.ctx.tz).isoformat(timespec="minutes"),
            "duration_minutes": fare["duration_minutes"],
            "payment_method": pay["method"].upper(),
            "payment_ref": pay["gateway_ref"],
            "lines": [
                {"label": f"Parking charges ({fare['billable_hours']} h)", "amount": fare["base_amount"]},
                {"label": f"Peak surcharge ({fare['surge_rule']})", "amount": fare["surge_amount"]},
                {"label": f"Discount ({fare['coupon_code']})", "amount": -fare["discount"]},
            ],
            "taxable_amount": fare["taxable_amount"],
            "cgst_9": fare["cgst"],
            "sgst_9": fare["sgst"],
            "total": fare["total"],
            "grace_applied": fare["grace_applied"],
        }

    def render_pdf(self, ticket_id: str) -> bytes:
        inv = self.invoice(ticket_id)
        width, height = 80 * mm, 150 * mm
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(width, height))
        c.setTitle(f"Tax Invoice {inv['invoice_no']}")
        y = height - 10 * mm

        def line(text, size=8, bold=False, right=None):
            nonlocal y
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawString(5 * mm, y, text)
            if right is not None:
                c.drawRightString(width - 5 * mm, y, right)
            y -= size + 3

        line("TAX INVOICE", 11, True)
        line(inv["facility"], 7)
        line(f"GSTIN: {inv['gstin']}   SAC: {inv['sac']}", 7)
        line(f"Invoice: {inv['invoice_no']}", 7)
        line(f"Date: {inv['issued_at']}", 7)
        y -= 4
        line(f"Vehicle: {inv['vehicle']} ({inv['category']})  Slot: {inv['slot']}", 7)
        line(f"In : {inv['entry_time']}", 7)
        line(f"Out: {inv['exit_time']}  ({inv['duration_minutes']} min)", 7)
        y -= 4
        for item in inv["lines"]:
            if item["amount"]:
                line(item["label"], 8, right=f"{item['amount']:.2f}")
        if inv["grace_applied"]:
            line("Grace period (<= 15 min) - no charge", 8)
        line("Taxable value", 8, right=f"{inv['taxable_amount']:.2f}")
        line("CGST @ 9%", 8, right=f"{inv['cgst_9']:.2f}")
        line("SGST @ 9%", 8, right=f"{inv['sgst_9']:.2f}")
        line("TOTAL (INR)", 10, True, right=f"{inv['total']:.2f}")
        y -= 4
        line(f"Paid via {inv['payment_method']}  Ref: {inv['payment_ref'] or '-'}", 7)
        line("Thank you for parking with us!", 7)
        c.showPage()
        c.save()
        return buf.getvalue()

    def sms_text(self, ticket_id: str) -> str:
        inv = self.invoice(ticket_id)
        return (f"VPS: Paid Rs {inv['total']:.2f} (incl. GST Rs {inv['cgst_9'] + inv['sgst_9']:.2f}) for "
                f"{inv['vehicle']}, {inv['duration_minutes']} min. Invoice {inv['invoice_no']}.")

    def send(self, ticket_id: str, channel: str, recipient: str) -> dict:
        channel = channel.upper()
        if channel not in ("SMS", "EMAIL"):
            raise ValidationError("channel must be SMS or EMAIL")
        if channel == "SMS" and not (recipient.isdigit() and len(recipient) == 10):
            raise ValidationError("SMS recipient must be a 10-digit mobile number")
        if channel == "EMAIL" and "@" not in recipient:
            raise ValidationError("invalid e-mail address")
        body = self.sms_text(ticket_id)
        # recipient is PII -> stored encrypted (VPS-SR-002); response shows a masked value
        cur = self.db.execute("INSERT INTO notifications (ts, channel, recipient, body) VALUES (?,?,?,?)",
                              (self.ctx.now_iso(), channel, self.ingress.vault.encrypt(recipient), body))
        masked = recipient[:2] + "*" * (len(recipient) - 4) + recipient[-2:]
        return {"id": cur.lastrowid, "channel": channel, "recipient": masked, "body": body, "status": "QUEUED"}


def get_receipts(ctx) -> ReceiptService:
    return ctx.service("receipts", ReceiptService)
