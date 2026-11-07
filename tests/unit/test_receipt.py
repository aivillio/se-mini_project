"""Unit tests - GST receipts (VPS-F-014). Owner: Akarsh Parashuram."""

import pytest

from vps.egress import get_egress
from vps.errors import Conflict, ValidationError
from vps.ingress import get_ingress
from vps.payment import get_payments
from vps.receipt import get_receipts


@pytest.fixture
def parked(ctx, clock):
    t = get_ingress(ctx).process_entry("ENTRY-1", "KA05MN4821", "4W")
    clock.advance(hours=2, minutes=10)
    return t


def pay_upi(ctx, ticket_id):
    out = get_egress(ctx).checkout(ticket_id, "upi")
    body, sig = get_payments(ctx).sandbox_complete(out["order"]["order_id"])
    return get_egress(ctx).handle_webhook(body, sig)


@pytest.mark.tc("TC-PAY-04")
@pytest.mark.req("VPS-F-014")
class TestReceipts:
    def test_gst_invoice(self, ctx, parked):
        pay_upi(ctx, parked["ticket_id"])
        inv = get_receipts(ctx).invoice(parked["ticket_id"])
        assert inv["invoice_no"] == "VPS/2026-27/000001" and inv["sac"] == "996743"
        assert inv["taxable_amount"] == 100.0 and inv["cgst_9"] == inv["sgst_9"] == 9.0 and inv["total"] == 118.0
        assert inv["vehicle"] == "KA05****21" and inv["gstin"] == ctx.settings.facility_gstin

    def test_pdf_and_sms(self, ctx, parked):
        pay_upi(ctx, parked["ticket_id"])
        rs = get_receipts(ctx)
        assert rs.render_pdf(parked["ticket_id"]).startswith(b"%PDF")
        sms = rs.send(parked["ticket_id"], "sms", "9876543210")
        assert sms["status"] == "QUEUED" and "Rs 118.00" in sms["body"] and sms["recipient"] == "98******10"
        assert "9876543210" not in ctx.db.query_one("SELECT recipient FROM notifications")["recipient"]
        assert rs.send(parked["ticket_id"], "EMAIL", "a@b.in")["channel"] == "EMAIL"
        for ch, to in [("FAX", "1"), ("SMS", "12345"), ("EMAIL", "nope")]:
            with pytest.raises(ValidationError):
                rs.send(parked["ticket_id"], ch, to)

    def test_grace_receipt_and_unpaid(self, ctx, clock):
        t = get_ingress(ctx).process_entry("ENTRY-1", "KA05MN4821", "4W")
        with pytest.raises(Conflict):
            get_receipts(ctx).invoice(t["ticket_id"])
        clock.advance(minutes=5)
        get_egress(ctx).checkout(t["ticket_id"], "upi")
        assert get_receipts(ctx).invoice(t["ticket_id"])["grace_applied"] is True
        assert get_receipts(ctx).render_pdf(t["ticket_id"]).startswith(b"%PDF")


@pytest.mark.tc("TC-PAY-04")
def test_receipt_api(client, clock):
    t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA05MN4821", "vehicle_category": "4W"}).json()
    clock.advance(hours=1, minutes=30)
    co = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"], "payment_method": "card",
                                                       "card_number": "4111111111111111"}).json()
    client.post(f"/api/v1/payments/{co['order']['order_id']}/sandbox-pay", json={"success": True})
    assert client.get(f"/api/v1/receipts/{t['ticket_id']}").json()["payment_method"] == "CARD"
    pdf = client.get(f"/api/v1/receipts/{t['ticket_id']}.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    sent = client.post(f"/api/v1/receipts/{t['ticket_id']}/send", json={"channel": "SMS", "recipient": "9876543210"})
    assert sent.status_code == 200
