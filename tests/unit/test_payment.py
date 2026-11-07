"""Unit tests - payment gateway adapter (VPS-F-012, VPS-NF-004). Owner: Akarsh Parashuram."""

import json

import pytest

from vps.errors import NotFound, PaymentError, SecurityViolation, ValidationError
from vps.payment import get_payments, luhn_ok

FARE = {"total": 47.2}


@pytest.fixture
def tid(ctx):
    from vps.ingress import get_ingress
    return get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W")["ticket_id"]


@pytest.mark.parametrize("num,ok", [("4111 1111 1111 1111", True), ("5555555555554444", True),
                                    ("4111111111111112", False), ("4111-1111-1111-1111", False), ("1234", False)])
def test_luhn(num, ok):
    assert luhn_ok(num) is ok


@pytest.mark.tc("TC-PAY-02")
@pytest.mark.req("VPS-F-012")
def test_upi_order_has_dynamic_qr(ctx, tid):
    o = get_payments(ctx).create_order(tid, 47.2, "upi", FARE)
    assert o["status"] == "CREATED" and o["upi_qr"].startswith("upi://pay?pa=")
    assert "am=47.20" in o["upi_qr"] and o["order_id"] in o["upi_qr"]


@pytest.mark.tc("TC-SEC-06")
@pytest.mark.req("VPS-NF-004")
def test_card_pan_never_stored(ctx, tid):
    pay = get_payments(ctx)
    o = pay.create_order(tid, 47.2, "card", FARE, card_number="4111 1111 1111 1111")
    row = pay.get(o["order_id"])
    assert row["card_last4"] == "1111"
    dump = "\n".join(ctx.db._conn.iterdump())
    assert "4111111111111111" not in dump and "4111 1111 1111 1111" not in dump


def test_order_validation(ctx, tid):
    pay = get_payments(ctx)
    with pytest.raises(ValidationError):
        pay.create_order(tid, 10, "bitcoin", FARE)
    with pytest.raises(ValidationError):
        pay.create_order(tid, -1, "upi", FARE)
    with pytest.raises(ValidationError):
        pay.create_order(tid, 10, "card", FARE, card_number="4111111111111112")
    with pytest.raises(ValidationError):
        pay.create_order(tid, 10, "none", FARE)
    assert pay.create_order(tid, 0, "none", FARE)["status"] == "CREATED"
    with pytest.raises(NotFound):
        pay.get("order_missing")


def test_gateway_outage_allows_cash_only(ctx, tid):
    pay = get_payments(ctx)
    pay.available = False
    with pytest.raises(PaymentError):
        pay.create_order(tid, 10, "upi", FARE)
    assert pay.create_order(tid, 10, "cash", FARE)["method"] == "cash"


@pytest.mark.tc("TC-PAY-05")
def test_webhook_signature(ctx, tid):
    pay = get_payments(ctx)
    o = pay.create_order(tid, 47.2, "upi", FARE)
    body, sig = pay.sandbox_complete(o["order_id"])
    assert pay.verify_webhook(body, sig)["event"] == "payment.captured"
    with pytest.raises(SecurityViolation):
        pay.verify_webhook(body, "0" * 64)
    with pytest.raises(SecurityViolation):
        pay.verify_webhook(body, None)
    forged = json.dumps({**json.loads(body), "amount": 1.0}, sort_keys=True).encode()
    with pytest.raises(SecurityViolation):
        pay.verify_webhook(forged, sig)
    fail_body, _ = pay.sandbox_complete(o["order_id"], success=False)
    assert json.loads(fail_body)["event"] == "payment.failed"
