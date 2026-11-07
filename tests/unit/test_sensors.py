"""Unit tests - sensor hub, LEDs, VMS signage, alerts (VPS-F-006, F-007). Owner: Shweta Mailaragouda Patil."""

import pytest

from vps.alerts import get_alerts
from vps.allocation import get_allocation
from vps.errors import Conflict, NotFound, ValidationError
from vps.sensors import get_sensor_hub


@pytest.mark.tc("TC-SLOT-02")
@pytest.mark.req("VPS-F-006")
def test_occupied_event_sets_red_led_within_2s(ctx):
    r = get_sensor_hub(ctx).handle_event("L1-C001", True)
    assert r == {"slot_id": "L1-C001", "status": "OCCUPIED", "led": "RED", "latency_ms": r["latency_ms"]}
    assert r["latency_ms"] <= 2000
    assert get_allocation(ctx).get("L1-C001")["status"] == "OCCUPIED"
    assert get_sensor_hub(ctx).led_states()["L1-C001"] == "RED"


@pytest.mark.tc("TC-SLOT-02")
def test_clear_event_sets_green(ctx):
    hub = get_sensor_hub(ctx)
    hub.handle_event("L1-C001", True)
    assert hub.handle_event("L1-C001", False)["led"] == "GREEN"


def test_reserved_bay_stays_reserved_when_empty(ctx):
    slot = get_allocation(ctx).reserve_slot("4W")
    assert get_sensor_hub(ctx).handle_event(slot["id"], False)["led"] == "BLUE"


def test_sensor_replay_rejected(ctx):
    hub = get_sensor_hub(ctx)
    hub.handle_event("L1-C001", True, seq=10)
    with pytest.raises(Conflict) as e:
        hub.handle_event("L1-C001", False, seq=10)
    assert e.value.code == "SENSOR_REPLAY"
    assert hub.handle_event("L1-C001", False, seq=11)["status"] == "VACANT"


def test_unknown_slot(ctx):
    with pytest.raises(NotFound):
        get_sensor_hub(ctx).handle_event("L9-X001", True)


@pytest.mark.tc("TC-SLOT-03")
@pytest.mark.req("VPS-F-007")
def test_vms_counts_match_database(ctx):
    hub = get_sensor_hub(ctx)
    v0 = hub.vms_boards()
    for sid in ("L1-C001", "L1-C002", "L2-C001"):
        hub.handle_event(sid, True)
    v1 = hub.vms_boards()
    db_vacant = ctx.db.scalar("SELECT COUNT(*) FROM slots WHERE status = 'VACANT'")
    assert v1["entrance"]["vacant"] == db_vacant == v0["entrance"]["vacant"] - 3
    assert v1["version"] == v0["version"] + 3
    lvl1 = next(b for b in v1["levels"] if b["level"] == 1)
    assert lvl1["by_category"]["4W"] == 18 and lvl1["text"].startswith("L1")
    assert "2W" not in next(b for b in v1["levels"] if b["level"] == 3)["by_category"]


@pytest.mark.tc("TC-SLOT-03")
def test_vms_full_text(ctx):
    eng = get_allocation(ctx)
    for s in eng.list():
        eng.set_status(s["id"], "OCCUPIED")
    v = get_sensor_hub(ctx).vms_boards()
    assert v["entrance"]["text"] == "CAR PARK FULL" and all(b["text"].endswith("FULL") for b in v["levels"])


def test_sensor_and_vms_api(client):
    r = client.post("/api/v1/sensors/L1-B001/event", json={"occupied": True, "seq": 1}).json()
    assert r["led"] == "RED"
    assert client.post("/api/v1/sensors/L1-B001/event", json={"occupied": False, "seq": 1}).status_code == 409
    assert client.get("/api/v1/vms").json()["entrance"]["vacant"] == 99


class TestAlerts:
    def test_raise_list_ack(self, ctx):
        svc = get_alerts(ctx)
        a = svc.raise_alert("PRINTER_FAULT", "out of paper", "WARNING", "ENTRY-1")
        assert svc.list()[0]["id"] == a["id"]
        assert svc.acknowledge(a["id"], "attendant")["acked_by"] == "attendant"
        assert svc.list() == [] and len(svc.list(open_only=False)) == 1
        with pytest.raises(NotFound):
            svc.acknowledge(a["id"], "attendant")
        with pytest.raises(ValidationError):
            svc.raise_alert("X", "y", "PANIC")

    def test_alerts_api(self, client, ctx, attendant_headers):
        get_alerts(ctx).raise_alert("PAYMENT_FAILED", "order x", "WARNING", "EXIT-1")
        assert client.get("/api/v1/alerts").status_code == 401
        items = client.get("/api/v1/alerts", headers=attendant_headers).json()
        assert items[0]["kind"] == "PAYMENT_FAILED"
        assert client.post(f"/api/v1/alerts/{items[0]['id']}/ack", headers=attendant_headers).status_code == 200


def test_vms_version_tracks_slot_changes(ctx):
    hub = get_sensor_hub(ctx)
    v = hub.vms_version
    get_allocation(ctx).allocate("2W")
    assert hub.vms_version == v + 1
    assert hub.vms_boards()["version"] == hub.vms_version
