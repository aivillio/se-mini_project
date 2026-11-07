"""System validation - complete user journeys through the HTTP API (Test Plan 5.1 System Testing).
Owner: Himansh Ahuja (QA Lead)."""

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.system


def enter(client, plate, cat="4W", **kw):
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": plate, "vehicle_category": cat, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def park(client, ticket, seq=1):
    """Driver drives through, loop clears, car parks and the bay sensor reports occupied."""
    lane = "ENTRY-1"
    client.post(f"/api/v1/lanes/{lane}/loop", json={"occupied": True})
    assert client.post(f"/api/v1/lanes/{lane}/loop", json={"occupied": False}).json()["barrier"] == "DOWN"
    r = client.post(f"/api/v1/sensors/{ticket['allocated_slot']}/event", json={"occupied": True, "seq": seq}).json()
    assert r["led"] == "RED"


@pytest.mark.tc("TC-SYS-01")
@pytest.mark.req("VPS-F-001", "VPS-F-002", "VPS-F-003", "VPS-F-005", "VPS-F-006", "VPS-F-008", "VPS-F-011",
                 "VPS-F-012", "VPS-F-013", "VPS-F-014")
def test_walk_in_car_pays_by_upi(client, clock):
    free_before = client.get("/api/v1/vms").json()["entrance"]["vacant"]
    t = enter(client, "KA 05 MN 4821")
    park(client, t)
    assert client.get("/api/v1/vms").json()["entrance"]["vacant"] == free_before - 1
    clock.advance(hours=2, minutes=10)
    inv = client.post("/api/v1/egress/lookup", json={"qr_payload": t["qr_payload"]}).json()["invoice"]
    assert (inv["billable_hours"], inv["base_amount"], inv["total"]) == (3, 100.0, 118.0)
    co = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"], "payment_method": "upi"}).json()
    assert co["status"] == "PENDING" and co["order"]["upi_qr"].startswith("upi://")
    paid = client.post(f"/api/v1/payments/{co['order']['order_id']}/sandbox-pay", json={}).json()
    assert paid["status"] == "PAID" and paid["barrier_action"] == "OPEN"
    assert client.get(f"/api/v1/receipts/{t['ticket_id']}").json()["total"] == 118.0
    assert client.get("/api/v1/vms").json()["entrance"]["vacant"] == free_before


@pytest.mark.tc("TC-SYS-02")
@pytest.mark.req("VPS-F-015", "VPS-F-016", "VPS-F-009")
def test_reserved_ev_short_visit_in_grace(client, clock):
    start = (clock.now + timedelta(minutes=20)).isoformat()
    res = client.post("/api/v1/reservations", json={"plate_number": "MH12XY9090", "vehicle_category": "EV",
                                                     "start_time": start}).json()
    assert res["status"] == "BOOKED"
    slot = next(s for s in client.get("/api/v1/slots").json() if s["id"] == res["slot_id"])
    assert slot["led"] == "BLUE"
    clock.advance(minutes=25)
    t = enter(client, "MH12XY9090", "EV", reservation_code=res["code"])
    assert t["allocated_slot"] == res["slot_id"]
    clock.advance(minutes=14)                                     # dropped someone off
    out = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"]}).json()
    assert out["status"] == "PAID" and out["amount"] == 0.0


@pytest.mark.tc("TC-SYS-03")
@pytest.mark.req("VPS-F-010", "VPS-F-012")
def test_peak_hour_card_payment_with_coupon(client, clock):
    clock.set(datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc))      # 16:00 IST
    t = enter(client, "DL3CAF0001")
    clock.advance(hours=2, minutes=30)                                  # exit 18:30 IST -> surge
    body = {"ticket_id": t["ticket_id"], "payment_method": "card", "card_number": "5555 5555 5555 4444",
            "coupon_code": "FLAT50"}
    co = client.post("/api/v1/egress/checkout", json=body).json()
    inv = co["invoice"]
    assert inv["surge_multiplier"] == 1.25 and inv["base_amount"] == 100.0 and inv["surge_amount"] == 25.0
    assert inv["discount"] == 50.0 and inv["total"] == round(75 * 1.18, 2)
    paid = client.post(f"/api/v1/payments/{co['order']['order_id']}/sandbox-pay", json={}).json()
    assert paid["status"] == "PAID"


@pytest.mark.tc("TC-SYS-04")
@pytest.mark.req("VPS-F-001", "VPS-F-012")
def test_unreadable_plate_manual_entry_and_cash(client, clock, attendant_headers):
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "TN09BX7712", "vehicle_category": "4W",
                                                     "confidence": 0.42})
    assert r.status_code == 422 and r.json()["error"]["code"] == "PLATE_UNREADABLE"
    t = client.post("/api/v1/ingress/manual", json={"plate_number": "TN09BX7712", "vehicle_category": "4W"},
                    headers=attendant_headers).json()
    clock.advance(minutes=50)
    look = client.post("/api/v1/egress/lookup", json={"plate_number": "TN09BX7712"}).json()
    assert look["invoice"]["total"] == round(40 * 1.18, 2)
    cash = client.post("/api/v1/egress/cash", json={"ticket_id": t["ticket_id"]}, headers=attendant_headers).json()
    assert cash["status"] == "PAID" and cash["method"] == "cash"


@pytest.mark.tc("TC-SYS-05")
@pytest.mark.req("VPS-F-017", "VPS-F-018")
def test_admin_day(client, clock, admin_headers):
    t = enter(client, "KA01AB1234", "2W")
    assert client.put("/api/v1/admin/tariffs/2W", json={"first_hour": 25, "per_hour": 10, "daily_cap": 150},
                      headers=admin_headers).status_code == 200
    clock.advance(hours=1)
    client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"]})
    pending = client.post("/api/v1/egress/lookup", json={"qr_payload": t["qr_payload"]}).json()
    assert pending["invoice"]["base_amount"] == 25.0
    order = client.post("/api/v1/egress/checkout", json={"ticket_id": t["ticket_id"]}).json()["order"]["order_id"]
    client.post(f"/api/v1/payments/{order}/sandbox-pay", json={})
    rev = client.get("/api/v1/reports/revenue", headers=admin_headers).json()
    assert rev["grand_total"] == 29.5
    assert client.get("/api/v1/reports/revenue", params={"format": "csv"}, headers=admin_headers).status_code == 200
    audit = client.get("/api/v1/admin/audit", headers=admin_headers).json()
    assert any(a["action"] == "TARIFF_UPDATED" for a in audit)
    assert client.get("/api/v1/admin/audit/verify", headers=admin_headers).json()["valid"] is True


@pytest.mark.tc("TC-SLOT-04")
def test_full_category_rejected_cleanly(client):
    for i in range(4):
        enter(client, f"KA01HC{1000 + i}", "HANDICAP")
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01HC9999", "vehicle_category": "HANDICAP"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "LOT_FULL"
