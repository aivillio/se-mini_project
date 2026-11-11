"""Resilience & reliability validation (VPS-NF-005, VPS-NF-002). Owner: Himansh Ahuja (QA Lead)."""

import random

import pytest

from tests.conftest import _login

pytestmark = pytest.mark.system


@pytest.mark.tc("TC-Fault-01")
@pytest.mark.req("VPS-NF-005")
def test_lanes_keep_working_through_72h_wan_outage(client, ctx, clock, admin_headers):
    client.post("/api/v1/edge/network", json={"online": False}, headers=admin_headers)
    central_before = client.get("/api/v1/edge/status").json()["central_events"]
    tickets = []
    for i in range(30):                                     # traffic spread over ~72 h of outage
        tickets.append(client.post("/api/v1/ingress/ticket", json={"plate_number": f"KA01AB{5000 + i}",
                                                                   "vehicle_category": "4W"}).json())
        clock.advance(hours=1)
    for t in tickets[:20]:
        shift = _login(client, ctx, "attendant", ctx.settings.attendant_password)     # new shift, new session
        r = client.post("/api/v1/egress/cash", json={"ticket_id": t["ticket_id"]}, headers=shift)
        assert r.status_code == 200 and r.json()["barrier_action"] == "OPEN"
        clock.advance(hours=2)
    st = client.get("/api/v1/edge/status").json()
    assert st["online"] is False and st["pending"] == 50 and st["central_events"] == central_before
    assert 69 <= st["oldest_pending_age_hours"] <= 72 and st["within_offline_budget"] is True
    admin = _login(client, ctx, "admin", ctx.settings.admin_password, ctx.settings.admin_totp_secret)
    back = client.post("/api/v1/edge/network", json={"online": True}, headers=admin).json()
    assert back["pending"] == 0 and back["sync"]["synced"] == 50
    assert back["sync"]["duration_ms"] <= 5 * 60 * 1000               # auto-sync within 5 minutes
    assert back["central_events"] == central_before + 50


@pytest.mark.tc("TC-Fault-01")
def test_lane_controller_offline_returns_503_and_other_lanes_continue(client, admin_headers):
    client.post("/api/v1/lanes/ENTRY-1/controller", json={"online": False}, headers=admin_headers)
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "EDGE_CONTROLLER_OFFLINE"
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W",
                                                     "lane_id": "ENTRY-2"})
    assert r.status_code == 201


@pytest.mark.tc("TC-Fault-01")
def test_payment_gateway_outage_falls_back_to_cash(client, ctx, clock, attendant_headers):
    from vps.payment import get_payments
    t = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W"}).json()
    clock.advance(hours=1)
    get_payments(ctx).available = False
    r = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"], "payment_method": "upi"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "GATEWAY_UNAVAILABLE"
    assert client.post("/api/v1/egress/cash", json={"ticket_id": t["ticket_id"]},
                       headers=attendant_headers).json()["status"] == "PAID"


@pytest.mark.tc("TC-Rel-01")
@pytest.mark.req("VPS-NF-002")
def test_soak_no_server_errors(client, clock):
    """Reliability proxy: 600+ mixed operations, zero 5xx, health stays ok (full 99.9 % monthly uptime
    can only be measured in production monitoring - see System Validation Report)."""
    rnd = random.Random(42)
    active, codes, exits = [], [], 0
    for i in range(300):
        if active and rnd.random() < 0.45:
            t = active.pop(rnd.randrange(len(active)))
            clock.advance(minutes=rnd.randint(5, 240))
            co = client.post("/api/v1/egress/checkout", json={"ticket_id": t, "payment_method": "upi"})
            codes.append(co.status_code)
            if co.json().get("status") == "PENDING":
                pay = client.post(f"/api/v1/payments/{co.json()['order']['order_id']}/sandbox-pay", json={})
                codes.append(pay.status_code)
                exits += pay.json().get("status") == "PAID"
            else:
                exits += co.json().get("status") == "PAID"
        else:
            r = client.post("/api/v1/ingress/ticket", json={"plate_number": f"KA{rnd.randint(10, 99)}AB{1000 + i}",
                                                             "vehicle_category": rnd.choice(["2W", "4W", "EV"])})
            codes.append(r.status_code)
            if r.status_code == 201:
                active.append(r.json()["ticket_id"])
        codes.append(client.get("/api/v1/vms").status_code)
    assert len(codes) >= 600 and not [c for c in codes if c >= 500]
    assert exits >= 100
    assert client.get("/health").json()["status"] == "ok"
