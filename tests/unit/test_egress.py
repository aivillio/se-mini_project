"""Unit tests - egress flow, payments, receipts (VPS-F-011..014, VPS-SR-004). Owner: Akarsh Parashuram."""

import json

import pytest

from vps.allocation import get_allocation
from vps.egress import get_egress
from vps.errors import Conflict, Forbidden, NotFound, SecurityViolation, ValidationError
from vps.hardware import get_hardware
from vps.ingress import get_ingress
from vps.payment import get_payments


@pytest.fixture
def parked(ctx, clock):
    t = get_ingress(ctx).process_entry("ENTRY-1", "KA05MN4821", "4W")
    clock.advance(hours=2, minutes=10)                    # 3 billable hours -> Rs 100 + GST
    return t


def pay_upi(ctx, ticket_id, success=True, coupon=None):
    eg = get_egress(ctx)
    out = eg.checkout(ticket_id, "upi", coupon_code=coupon)
    body, sig = get_payments(ctx).sandbox_complete(out["order"]["order_id"], success)
    return out, eg.handle_webhook(body, sig)


@pytest.mark.tc("TC-PAY-01")
@pytest.mark.req("VPS-F-011")
def test_lookup_by_qr_and_plate(ctx, parked):
    eg = get_egress(ctx)
    r = eg.lookup(qr_payload=parked["qr_payload"])
    assert r["ticket_id"] == parked["ticket_id"] and r["invoice"]["total"] == 118.0 and r["latency_ms"] <= 1000
    assert eg.lookup(plate_number="ka05mn4821")["ticket_id"] == parked["ticket_id"]
    with pytest.raises(NotFound):
        eg.lookup(plate_number="KA05MN0000")
    with pytest.raises(ValidationError):
        eg.lookup()


@pytest.mark.tc("TC-SEC-04")
@pytest.mark.req("VPS-SR-004")
def test_counterfeit_ticket_rejected_and_alerted(ctx, parked):
    qr = parked["qr_payload"]
    forged = qr[:5] + ("A" if qr[5] != "A" else "B") + qr[6:]
    with pytest.raises(SecurityViolation):
        get_egress(ctx).lookup(qr_payload=forged)
    assert ctx.db.query_one("SELECT * FROM alerts")["kind"] == "COUNTERFEIT_TICKET"
    assert ctx.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'COUNTERFEIT_TICKET'") == 1


def test_valid_signature_but_reissued_ticket_rejected(ctx, parked):
    from vps.security import get_signer
    clone = get_signer(ctx).sign({"tid": parked["ticket_id"], "slot": "L3-C024", "ts": parked["entry_time"], "pf": "x"})
    with pytest.raises(SecurityViolation):
        get_egress(ctx).lookup(qr_payload=clone)


@pytest.mark.tc("TC-PAY-02", "TC-PAY-03")
@pytest.mark.req("VPS-F-012", "VPS-F-013")
def test_upi_payment_opens_barrier_and_releases_slot(ctx, parked):
    pending, done = pay_upi(ctx, parked["ticket_id"])
    assert pending["status"] == "PENDING" and pending["barrier_action"] == "HOLD"
    assert done["status"] == "PAID" and done["barrier_action"] == "OPEN" and done["amount"] == 118.0
    assert get_hardware(ctx).get("EXIT-1").barrier.state == "UP"
    assert get_allocation(ctx).get(parked["allocated_slot"])["status"] == "VACANT"
    assert ctx.db.scalar("SELECT COUNT(*) FROM central_events WHERE kind = 'EXIT'") == 1
    assert get_egress(ctx).lookup(qr_payload=parked["qr_payload"])["invoice"] is None    # already settled


@pytest.mark.tc("TC-PAY-03")
@pytest.mark.req("VPS-F-013")
def test_barrier_never_opens_unpaid(ctx, parked):
    with pytest.raises(Forbidden) as e:
        get_egress(ctx).open_exit_barrier(parked["ticket_id"], "EXIT-1")
    assert e.value.code == "UNPAID_TICKET"
    assert get_hardware(ctx).get("EXIT-1").barrier.state == "DOWN"


@pytest.mark.tc("TC-PAY-05")
def test_failed_payment_keeps_barrier_closed(ctx, parked):
    _, r = pay_upi(ctx, parked["ticket_id"], success=False)
    assert r["status"] == "FAILED" and r["barrier_action"] == "HOLD"
    assert get_hardware(ctx).get("EXIT-1").barrier.state == "DOWN"
    assert ctx.db.query_one("SELECT kind FROM alerts")["kind"] == "PAYMENT_FAILED"
    _, ok = pay_upi(ctx, parked["ticket_id"])                    # retry succeeds
    assert ok["status"] == "PAID"


@pytest.mark.tc("TC-PAY-05")
def test_webhook_idempotent_and_amount_checked(ctx, parked, clock):
    eg, pay = get_egress(ctx), get_payments(ctx)
    out = eg.checkout(parked["ticket_id"], "upi")
    body, sig = pay.sandbox_complete(out["order"]["order_id"])
    assert eg.handle_webhook(body, sig)["status"] == "PAID"
    assert eg.handle_webhook(body, sig)["status"] == "PAID"         # re-delivery is harmless
    t2 = get_ingress(ctx).process_entry("ENTRY-1", "KA05MN4822", "4W")
    clock.advance(hours=1)
    out2 = eg.checkout(t2["ticket_id"], "upi")
    tampered = json.dumps({**json.loads(pay.sandbox_complete(out2["order"]["order_id"])[0]), "amount": 1.0},
                          sort_keys=True).encode()
    with pytest.raises(SecurityViolation):
        eg.handle_webhook(tampered, pay.sign(tampered))


@pytest.mark.tc("TC-BILL-02")
def test_grace_period_exit_needs_no_payment(ctx, clock):
    t = get_ingress(ctx).process_entry("ENTRY-1", "KA05MN4821", "2W")
    clock.advance(minutes=12)
    r = get_egress(ctx).checkout(t["ticket_id"], "upi")
    assert r["status"] == "PAID" and r["amount"] == 0.0 and r["method"] == "none"


def test_coupon_redeemed_on_payment(ctx, parked):
    _, done = pay_upi(ctx, parked["ticket_id"], coupon="WELCOME10")
    assert done["amount"] == 106.2
    assert ctx.db.scalar("SELECT used_count FROM coupons WHERE code = 'WELCOME10'") == 1


def test_cash_payment_is_audited(ctx, parked):
    r = get_egress(ctx).cash_payment(parked["ticket_id"], "attendant")
    assert r["status"] == "PAID" and r["method"] == "cash"
    assert ctx.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'CASH_COLLECTED'") == 1
    with pytest.raises(Conflict):
        get_egress(ctx).cash_payment(parked["ticket_id"], "attendant")


def test_checkout_guards(ctx, parked):
    eg = get_egress(ctx)
    with pytest.raises(ValidationError):
        eg.checkout(parked["ticket_id"], "upi", lane_id="ENTRY-1")
    pay_upi(ctx, parked["ticket_id"])
    with pytest.raises(Conflict):
        eg.checkout(parked["ticket_id"], "upi")
    with pytest.raises(Conflict):
        eg._finalize(ctx.db.query_one("SELECT id FROM payments")["id"], "EXIT-1", None)
    st = eg.status(parked["ticket_id"])
    assert st["status"] == "PAID" and st["receipt_url"].endswith(".pdf")


class TestEgressApi:
    def test_full_api_flow(self, client, ctx, clock):
        t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA05MN4821", "vehicle_category": "4W"}).json()
        clock.advance(hours=1, minutes=30)
        inv = client.post("/api/v1/egress/lookup", json={"qr_payload": t["qr_payload"]}).json()["invoice"]
        assert inv["base_amount"] == 70.0
        co = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"], "payment_method": "card",
                                                           "card_number": "4111111111111111"}).json()
        assert co["status"] == "PENDING"
        oid = co["order"]["order_id"]
        assert client.get(f"/api/v1/egress/status/{t['ticket_id']}").json()["barrier_action"] == "HOLD"
        paid = client.post(f"/api/v1/payments/{oid}/sandbox-pay", json={"success": True}).json()
        assert paid["status"] == "PAID" and paid["receipt_url"].endswith(".pdf")

    def test_webhook_endpoint_requires_signature(self, client):
        r = client.post("/api/v1/payments/webhook", content=b'{"event":"payment.captured","order_id":"x"}')
        assert r.status_code == 403 and r.json()["error"]["code"] == "BAD_WEBHOOK_SIGNATURE"

    def test_webhook_endpoint_signed(self, client, ctx, clock):
        t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA05MN4821", "vehicle_category": "2W"}).json()
        clock.advance(hours=1)
        oid = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"]}).json()["order"]["order_id"]
        body, sig = get_payments(ctx).sandbox_complete(oid)
        r = client.post("/api/v1/payments/webhook", content=body, headers={"X-VPS-Signature": sig})
        assert r.json()["status"] == "PAID"

    def test_cash_endpoint_and_sandbox_disabled_in_prod(self, client, ctx, clock, attendant_headers):
        t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA05MN4821", "vehicle_category": "4W"}).json()
        clock.advance(hours=1)
        assert client.post("/api/v1/egress/cash", json={"ticket_id": t["ticket_id"]}).status_code == 401
        assert client.post("/api/v1/egress/cash", json={"ticket_id": t["ticket_id"]},
                           headers=attendant_headers).json()["method"] == "cash"
        ctx.settings.env = "production"
        assert client.post("/api/v1/payments/order_x/sandbox-pay", json={}).status_code == 403
