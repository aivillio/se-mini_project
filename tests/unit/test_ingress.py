"""Unit tests - vps.ingress + ingress API (VPS-F-001..004, VPS-NF-001). Owner: Angelo Arakal."""

from datetime import timedelta

import pytest

from tests.conftest import issue
from vps.errors import Conflict, EdgeOffline, InvalidPlate, LotFull, PlateUnreadable, ValidationError
from vps.hardware import get_hardware
from vps.ingress import get_ingress
from vps.security import get_signer


@pytest.mark.tc("TC-ENT-01")
@pytest.mark.req("VPS-F-001")
def test_plate_capture_normalised_and_fast(ctx):
    r = get_ingress(ctx).process_entry("ENTRY-1", "ka-01 ab 1234", "4W")
    assert r["plate_masked"] == "KA01****34"
    assert r["entry_mode"] == "ANPR"
    assert r["timings_ms"]["plate_capture"] <= 1500


@pytest.mark.tc("TC-ENT-06")
@pytest.mark.req("VPS-F-001")
def test_low_confidence_routes_to_attendant(ctx):
    with pytest.raises(PlateUnreadable):
        get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W", confidence=0.5)
    # attendant types it in -> MANUAL entry, audited
    r = get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W", attendant="attendant")
    assert r["entry_mode"] == "MANUAL"
    assert ctx.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'MANUAL_ENTRY'") == 1


@pytest.mark.tc("TC-ENT-06")
@pytest.mark.parametrize("plate", ["", "HELLO", "1234KA01", "KA01AB12345"])
def test_invalid_plate(ctx, plate):
    with pytest.raises(InvalidPlate):
        get_ingress(ctx).process_entry("ENTRY-1", plate, "4W")


def test_invalid_category(ctx):
    with pytest.raises(InvalidPlate) as e:
        get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "TRUCK")
    assert e.value.code == "INVALID_CATEGORY"


@pytest.mark.tc("TC-ENT-02")
@pytest.mark.req("VPS-F-002", "VPS-SR-004")
def test_ticket_has_signed_qr_and_encrypted_plate(ctx):
    r = get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W")
    claims = get_signer(ctx).verify(r["qr_payload"])
    assert claims["tid"] == r["ticket_id"] and claims["slot"] == r["allocated_slot"] and claims["ts"] == r["entry_time"]
    row = ctx.db.query_one("SELECT * FROM tickets WHERE id = ?", (r["ticket_id"],))
    assert "KA01AB1234" not in row["plate_enc"]
    assert r["timings_ms"]["ticket_issue"] <= 2000
    assert get_hardware(ctx).get("ENTRY-1").printer.printed[-1]["ticket_id"] == r["ticket_id"]


@pytest.mark.tc("TC-ENT-02")
def test_ticket_ids_unique(ctx):
    ids = {get_ingress(ctx).process_entry("ENTRY-1", f"KA01AB{1000 + i}", "4W")["ticket_id"] for i in range(10)}
    assert len(ids) == 10


@pytest.mark.tc("TC-ENT-03")
@pytest.mark.req("VPS-F-003")
def test_barrier_raised_within_500ms(ctx):
    r = get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W")
    assert r["barrier"] == "UP" and r["timings_ms"]["barrier_raise"] <= 500
    assert r["timings_ms"]["total"] <= 3000          # VPS-NF-001 budget


@pytest.mark.tc("TC-ENT-05")
def test_anti_passback(ctx):
    get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W")
    with pytest.raises(Conflict) as e:
        get_ingress(ctx).process_entry("ENTRY-2", "KA01AB1234", "4W")
    assert e.value.code == "VEHICLE_ALREADY_INSIDE"


def test_wrong_lane_direction_and_offline_controller(ctx):
    with pytest.raises(ValidationError):
        get_ingress(ctx).process_entry("EXIT-1", "KA01AB1234", "4W")
    get_hardware(ctx).get("ENTRY-2").controller_online = False
    with pytest.raises(EdgeOffline):
        get_ingress(ctx).process_entry("ENTRY-2", "KA01AB1234", "4W")


def test_printer_fault_falls_back_to_digital_ticket(ctx):
    get_hardware(ctx).get("ENTRY-1").printer.paper_ok = False
    r = get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W")
    assert r["ticket_delivery"] == "DIGITAL_ONLY"
    assert ctx.db.query_one("SELECT kind FROM alerts")["kind"] == "PRINTER_FAULT"


def test_timestamp_rules(ctx, clock):
    svc = get_ingress(ctx)
    past = (clock.now - timedelta(hours=2)).isoformat()
    assert svc.process_entry("ENTRY-1", "KA01AB1001", "4W", timestamp=past)["entry_time"] == past
    with pytest.raises(ValidationError):
        svc.process_entry("ENTRY-1", "KA01AB1002", "4W", timestamp=(clock.now + timedelta(minutes=5)).isoformat())
    with pytest.raises(ValidationError):
        svc.process_entry("ENTRY-1", "KA01AB1003", "4W", timestamp=(clock.now - timedelta(hours=80)).isoformat())
    with pytest.raises(ValidationError):
        svc.process_entry("ENTRY-1", "KA01AB1004", "4W", timestamp="yesterday")


@pytest.mark.tc("TC-SLOT-04")
def test_lot_full(ctx):
    svc = get_ingress(ctx)
    for i in range(4):
        svc.process_entry("ENTRY-1", f"KA01HC{1000 + i}", "HANDICAP")
    with pytest.raises(LotFull):
        svc.process_entry("ENTRY-1", "KA01HC2000", "HANDICAP")


# ------------------------------------------------------------------ API layer
@pytest.mark.tc("TC-ENT-02")
def test_api_matches_sad_contract(client):
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W",
                                                     "timestamp": None})
    assert r.status_code == 201
    body = r.json()
    assert {"ticket_id", "qr_payload", "allocated_slot"} <= body.keys()


def test_api_errors(client):
    assert client.post("/api/v1/ingress/ticket", json={"plate_number": "??", "vehicle_category": "4W"}).json()[
        "error"]["code"] == "INVALID_PLATE"
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W",
                                                     "lane_id": "NOPE"})
    assert r.status_code == 404


def test_api_ticket_views(client):
    t = issue(client)
    view = client.get(f"/api/v1/tickets/{t['ticket_id']}").json()
    assert view["plate_masked"] == "KA01****34" and "plate_enc" not in view
    svg = client.get(f"/api/v1/tickets/{t['ticket_id']}/qr.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert client.get("/api/v1/qr.svg", params={"data": "upi://pay"}).status_code == 200
    assert client.get("/api/v1/tickets/does-not-exist").status_code == 404


def test_api_manual_entry_requires_staff(client, attendant_headers):
    body = {"plate_number": "TN09BX7712", "vehicle_category": "4W"}
    assert client.post("/api/v1/ingress/manual", json=body).status_code == 401
    r = client.post("/api/v1/ingress/manual", json=body, headers=attendant_headers)
    assert r.status_code == 201 and r.json()["entry_mode"] == "MANUAL"


@pytest.mark.tc("TC-ENT-04")
@pytest.mark.req("VPS-F-004")
def test_api_loop_safety(client):
    issue(client)                                                  # barrier UP on ENTRY-1
    on = client.post("/api/v1/lanes/ENTRY-1/loop", json={"occupied": True}).json()
    assert on["loop_occupied"] and on["halted"]
    lower = client.post("/api/v1/lanes/ENTRY-1/barrier/lower").json()
    assert lower["halted"] and lower["reason"] == "VEHICLE_ON_LOOP" and lower["barrier"] == "UP"
    off = client.post("/api/v1/lanes/ENTRY-1/loop", json={"occupied": False}).json()
    assert off["state"] == "DOWN" and off["barrier"] == "DOWN"          # auto-lowered once clear
    assert client.post("/api/v1/lanes/ENTRY-1/barrier/lower").json()["halted"] is False
    assert len(client.get("/api/v1/lanes").json()) == 4


def test_api_lane_controller_toggle(client, admin_headers):
    r = client.post("/api/v1/lanes/ENTRY-2/controller", json={"online": False}, headers=admin_headers)
    assert r.json()["controller_online"] is False
    r = client.post("/api/v1/ingress/ticket", json={"plate_number": "KA01AB1234", "vehicle_category": "4W",
                                                     "lane_id": "ENTRY-2"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "EDGE_CONTROLLER_OFFLINE"
    assert client.post("/api/v1/lanes/NOPE/controller", json={"online": True}, headers=admin_headers).status_code == 404


def test_root_redirects_to_ui(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/ui/index.html"
    assert client.get("/ui/index.html").status_code == 200
