"""Egress, payment and receipt endpoints (SAD 4.3: POST /api/v1/egress/checkout)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel

from vps.api.deps import get_ctx, require
from vps.egress import get_egress
from vps.errors import Forbidden
from vps.payment import get_payments

router = APIRouter(prefix="/api/v1", tags=["egress & payments"])


class LookupIn(BaseModel):
    qr_payload: str | None = None
    plate_number: str | None = None
    coupon_code: str | None = None
    lane_id: str = "EXIT-1"


class CheckoutIn(BaseModel):
    ticket_id: str
    payment_method: str = "upi"
    coupon_code: str | None = None
    card_number: str | None = None
    lane_id: str = "EXIT-1"


class SandboxPayIn(BaseModel):
    success: bool = True
    lane_id: str = "EXIT-1"


class CashIn(BaseModel):
    ticket_id: str
    lane_id: str = "EXIT-1"


@router.post("/egress/lookup")
def lookup(body: LookupIn, ctx=Depends(get_ctx)):
    return get_egress(ctx).lookup(qr_payload=body.qr_payload, plate_number=body.plate_number,
                                  coupon_code=body.coupon_code, lane_id=body.lane_id)


@router.post("/egress/checkout")
def checkout(body: CheckoutIn, ctx=Depends(get_ctx)):
    return get_egress(ctx).checkout(body.ticket_id, body.payment_method, coupon_code=body.coupon_code,
                                    card_number=body.card_number, lane_id=body.lane_id)


@router.get("/egress/status/{ticket_id}")
def status(ticket_id: str, ctx=Depends(get_ctx)):
    return get_egress(ctx).status(ticket_id)


@router.post("/egress/cash")
def cash(body: CashIn, ctx=Depends(get_ctx), user=Depends(require("ATTENDANT", "ADMIN"))):
    return get_egress(ctx).cash_payment(body.ticket_id, user["username"], body.lane_id)


@router.post("/payments/webhook")
async def webhook(request: Request, x_vps_signature: str | None = Header(default=None), ctx=Depends(get_ctx)):
    """Gateway -> VPS callback. Body must be signed with HMAC-SHA256 (header X-VPS-Signature)."""
    return get_egress(ctx).handle_webhook(await request.body(), x_vps_signature)


@router.post("/payments/{order_id}/sandbox-pay")
def sandbox_pay(order_id: str, body: SandboxPayIn, ctx=Depends(get_ctx)):
    """Sandbox only: simulates the customer completing payment in their UPI app/card terminal,
    then delivers the signed webhook exactly as the real gateway would."""
    if ctx.settings.env == "production":
        raise Forbidden("Sandbox payments are disabled in production")
    raw, sig = get_payments(ctx).sandbox_complete(order_id, body.success)
    return get_egress(ctx).handle_webhook(raw, sig, body.lane_id)
