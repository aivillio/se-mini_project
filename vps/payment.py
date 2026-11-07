"""Payment Gateway adapter (VPS-F-012, VPS-NF-004).

Production target is Razorpay/Stripe; this build ships a sandbox that behaves
like Razorpay's order + signed-webhook model so the egress logic is identical:

1. ``create_order``   -> order id + dynamic UPI QR (``upi://pay?...``)
2. customer pays in their UPI app / card terminal
3. gateway POSTs a webhook signed with HMAC-SHA256 (``X-VPS-Signature``)
4. we verify the signature before trusting the PAID status

Card handling never stores the PAN: only the last four digits after a Luhn check.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from urllib.parse import quote

from vps.errors import NotFound, PaymentError, SecurityViolation, ValidationError

METHODS = ("upi", "card", "wallet", "netbanking", "cash")
UPI_VPA = "vpsparking@okaxis"


def luhn_ok(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 12 or len(digits) != len([c for c in number if not c.isspace()]):
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        checksum += d
    return checksum % 10 == 0


class PaymentGateway:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self._secret = ctx.settings.payment_webhook_secret.encode()
        self.available = True

    # ---------------------------------------------------------------- orders
    def create_order(self, ticket_id: str, amount: float, method: str, fare: dict, *,
                     card_number: str | None = None, coupon_code: str | None = None) -> dict:
        if method == "none":
            if amount != 0:
                raise ValidationError("method 'none' is only valid for zero-value settlements")
        elif method not in METHODS:
            raise ValidationError(f"payment_method must be one of {METHODS}")
        if amount < 0:
            raise ValidationError("amount cannot be negative")
        if not self.available and method not in ("cash", "none"):
            raise PaymentError("Payment gateway unavailable - use attendant cash desk", code="GATEWAY_UNAVAILABLE")
        last4 = None
        if method == "card":
            if not card_number or not luhn_ok(card_number):
                raise ValidationError("Invalid card number", code="INVALID_CARD")
            last4 = card_number.replace(" ", "")[-4:]
        order_id = "order_" + uuid.uuid4().hex[:14]
        now = self.ctx.now_iso()
        self.db.execute(
            "INSERT INTO payments (id, ticket_id, amount, method, status, card_last4, coupon_code, fare_json,"
            " created_at) VALUES (?,?,?,?, 'CREATED', ?,?,?,?)",
            (order_id, ticket_id, amount, method, last4, coupon_code, json.dumps(fare), now),
        )
        order = {"order_id": order_id, "ticket_id": ticket_id, "amount": amount, "method": method, "status": "CREATED"}
        if method == "upi":
            order["upi_qr"] = f"upi://pay?pa={UPI_VPA}&pn={quote('VPS Parking')}&am={amount:.2f}&cu=INR&tr={order_id}"
        return order

    def get(self, order_id: str) -> dict:
        p = self.db.query_one("SELECT * FROM payments WHERE id = ?", (order_id,))
        if not p:
            raise NotFound(f"Order {order_id} not found")
        return p

    def mark(self, order_id: str, status: str, gateway_ref: str | None = None) -> dict:
        self.db.execute("UPDATE payments SET status = ?, gateway_ref = COALESCE(?, gateway_ref), updated_at = ?"
                        " WHERE id = ?", (status, gateway_ref, self.ctx.now_iso(), order_id))
        return self.get(order_id)

    # ---------------------------------------------------------------- webhooks
    def sign(self, body: bytes) -> str:
        return hmac.new(self._secret, body, hashlib.sha256).hexdigest()

    def verify_webhook(self, body: bytes, signature: str | None) -> dict:
        if not signature or not hmac.compare_digest(self.sign(body), signature):
            raise SecurityViolation("Invalid payment webhook signature", code="BAD_WEBHOOK_SIGNATURE")
        return json.loads(body)

    def sandbox_complete(self, order_id: str, success: bool = True) -> tuple[bytes, str]:
        """What the real gateway does after the customer pays: build + sign the webhook."""
        order = self.get(order_id)
        event = {
            "event": "payment.captured" if success else "payment.failed",
            "order_id": order_id,
            "amount": order["amount"],
            "payment_id": "pay_" + uuid.uuid4().hex[:14],
            "method": order["method"],
        }
        body = json.dumps(event, sort_keys=True).encode()
        return body, self.sign(body)


def get_payments(ctx) -> PaymentGateway:
    return ctx.service("payments", PaymentGateway)
