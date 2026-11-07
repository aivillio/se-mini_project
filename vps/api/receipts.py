"""GST receipt endpoints (VPS-F-014): JSON invoice, thermal-printer PDF, SMS / e-mail dispatch."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from vps.api.deps import get_ctx
from vps.receipt import get_receipts

router = APIRouter(prefix="/api/v1", tags=["receipts"])


class SendIn(BaseModel):
    channel: str
    recipient: str


@router.get("/receipts/{ticket_id}.pdf")
def receipt_pdf(ticket_id: str, ctx=Depends(get_ctx)):
    pdf = get_receipts(ctx).render_pdf(ticket_id)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="receipt-{ticket_id[:8]}.pdf"'})


# declared after the .pdf route so "<id>.pdf" is not captured as an id
@router.get("/receipts/{ticket_id}")
def receipt_json(ticket_id: str, ctx=Depends(get_ctx)):
    return get_receipts(ctx).invoice(ticket_id)


@router.post("/receipts/{ticket_id}/send")
def receipt_send(ticket_id: str, body: SendIn, ctx=Depends(get_ctx)):
    return get_receipts(ctx).send(ticket_id, body.channel, body.recipient)
