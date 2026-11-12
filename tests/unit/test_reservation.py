"""Unit tests - reservations + no-show scheduler (VPS-F-015, F-016). Owner: Himansh Ahuja."""

from datetime import timedelta

import pytest

from vps.allocation import get_allocation
from vps.errors import Conflict, NotFound, SecurityViolation, ValidationError
from vps.ingress import get_ingress
from vps.reservation import CODE_ALPHABET, get_reservations
from vps.scheduler import Scheduler


def book(ctx, clock, hours_ahead=2, plate="MH12XY9090", cat="4W", **kw):
    return get_reservations(ctx).create(plate, cat, (clock.now + timedelta(hours=hours_ahead)).isoformat(), **kw)


@pytest.mark.tc("TC-RES-01")
@pytest.mark.req("VPS-F-015")
class TestBooking:
    def test_reserve_locks_slot_and_issues_code(self, ctx, clock):
        r = book(ctx, clock, contact="9876543210")
        assert r["status"] == "BOOKED" and len(r["code"]) == 8 and set(r["code"]) <= set(CODE_ALPHABET)
        assert get_allocation(ctx).get(r["slot_id"])["status"] == "RESERVED"
        assert r["plate_masked"] == "MH12****90"
        row = ctx.db.query_one("SELECT * FROM reservations")
        assert "9876543210" not in row["contact_enc"] and "MH12XY9090" not in row["plate_enc"]

    def test_48_hour_window(self, ctx, clock):
        assert book(ctx, clock, hours_ahead=47.9)["status"] == "BOOKED"
        with pytest.raises(ValidationError, match="48 hours"):
            book(ctx, clock, hours_ahead=48.1, plate="KA01AB0001")
        with pytest.raises(ValidationError, match="past"):
            book(ctx, clock, hours_ahead=-1, plate="KA01AB0002")

    def test_input_validation(self, ctx, clock):
        svc = get_reservations(ctx)
        with pytest.raises(ValidationError):
            svc.create("KA01AB0001", "4W", "tomorrow-ish")
        with pytest.raises(ValidationError):
            book(ctx, clock, plate="KA01AB0003", duration_hours=30)

    def test_one_active_booking_per_vehicle(self, ctx, clock):
        book(ctx, clock)
        with pytest.raises(Conflict):
            book(ctx, clock, hours_ahead=5)

    def test_lookup_list_cancel(self, ctx, clock):
        svc = get_reservations(ctx)
        r = book(ctx, clock)
        assert svc.get(r["code"].lower())["reservation_id"] == r["reservation_id"]
        assert len(svc.list("BOOKED")) == 1 and len(svc.list()) == 1
        with pytest.raises(SecurityViolation):
            svc.cancel(r["code"], "KA01AB0000")
        assert svc.cancel(r["code"], "MH12XY9090")["status"] == "CANCELLED"
        assert get_allocation(ctx).get(r["slot_id"])["status"] == "VACANT"
        with pytest.raises(Conflict):
            svc.cancel(r["code"], "MH12XY9090")
        with pytest.raises(NotFound):
            svc.get("ZZZZZZZZ")


@pytest.mark.tc("TC-RES-03")
class TestCheckIn:
    def test_entry_with_code_uses_reserved_slot(self, ctx, clock):
        r = book(ctx, clock, hours_ahead=0.5)
        t = get_ingress(ctx).process_entry("ENTRY-1", "MH12XY9090", "4W", reservation_code=r["code"])
        assert t["allocated_slot"] == r["slot_id"] and t["reservation_id"] == r["reservation_id"]
        assert get_reservations(ctx).get(r["code"])["status"] == "CHECKED_IN"
        assert get_allocation(ctx).get(r["slot_id"])["status"] == "ALLOCATED"

    def test_plate_and_category_must_match(self, ctx, clock):
        r = book(ctx, clock, hours_ahead=0.5)
        with pytest.raises(SecurityViolation):
            get_ingress(ctx).process_entry("ENTRY-1", "KA01AB1234", "4W", reservation_code=r["code"])
        with pytest.raises(ValidationError):
            get_ingress(ctx).process_entry("ENTRY-1", "MH12XY9090", "2W", reservation_code=r["code"])

    def test_too_early(self, ctx, clock):
        r = book(ctx, clock, hours_ahead=3)
        with pytest.raises(Conflict) as e:
            get_ingress(ctx).process_entry("ENTRY-1", "MH12XY9090", "4W", reservation_code=r["code"])
        assert e.value.code == "RESERVATION_TOO_EARLY"

    def test_late_arrival_expires(self, ctx, clock):
        r = book(ctx, clock, hours_ahead=1)
        clock.advance(hours=1, minutes=31)
        with pytest.raises(Conflict) as e:
            get_ingress(ctx).process_entry("ENTRY-1", "MH12XY9090", "4W", reservation_code=r["code"])
        assert e.value.code == "RESERVATION_EXPIRED"
        assert get_reservations(ctx).get(r["code"])["status"] == "EXPIRED"
        with pytest.raises(Conflict):
            get_reservations(ctx).check_in(r["code"], "MH12XY9090", "4W")


@pytest.mark.tc("TC-RES-02")
@pytest.mark.req("VPS-F-016")
class TestNoShow:
    def test_release_after_30_minutes(self, ctx, clock):
        svc = get_reservations(ctx)
        r = book(ctx, clock, hours_ahead=1)
        clock.advance(hours=1, minutes=29)
        assert svc.release_no_shows() == []
        clock.advance(minutes=2)
        assert svc.release_no_shows() == [r["code"]]
        assert svc.get(r["code"])["status"] == "EXPIRED"
        assert get_allocation(ctx).get(r["slot_id"])["status"] == "VACANT"
        assert ctx.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'NO_SHOW_RELEASED'") == 1

    def test_scheduler_tick_and_thread(self, ctx, clock):
        r = book(ctx, clock, hours_ahead=0.1)
        clock.advance(hours=1)
        sch = Scheduler(ctx, interval_seconds=0.05)
        assert sch.tick() == [r["code"]] and sch.runs == 1
        sch.start()
        sch.start()                     # idempotent
        import time
        time.sleep(0.2)
        sch.stop()
        assert sch.runs >= 2


def test_reservation_api(client, ctx, clock, admin_headers):
    start = (clock.now + timedelta(hours=1)).isoformat()
    r = client.post("/api/v1/reservations", json={"plate_number": "MH12XY9090", "vehicle_category": "EV",
                                                   "start_time": start})
    assert r.status_code == 201
    code = r.json()["code"]
    assert client.get(f"/api/v1/reservations/{code}").json()["status"] == "BOOKED"
    assert client.get("/api/v1/reservations").status_code == 401
    assert len(client.get("/api/v1/reservations", headers=admin_headers).json()) == 1
    bad = client.post("/api/v1/reservations", json={"plate_number": "MH12XY9091", "vehicle_category": "EV",
                                                     "start_time": (clock.now + timedelta(hours=72)).isoformat()})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_WINDOW"
    clock.advance(hours=2)
    assert client.post("/api/v1/reservations/release-no-shows", headers=admin_headers).json()["released"] == [code]
    assert client.post(f"/api/v1/reservations/{code}/cancel", json={"plate_number": "MH12XY9090"}).status_code == 409


def test_cancel_keeps_admin_disabled_bay(ctx, clock):
    r = book(ctx, clock)
    get_allocation(ctx).set_status(r["slot_id"], "DISABLED")
    get_reservations(ctx).cancel(r["code"], "MH12XY9090")
    assert get_allocation(ctx).get(r["slot_id"])["status"] == "DISABLED"


def test_scheduler_stop_without_start(ctx):
    Scheduler(ctx).stop()
