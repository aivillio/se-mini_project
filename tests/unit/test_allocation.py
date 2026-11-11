"""Unit tests - slot allocation engine (VPS-F-005). Owner: Shweta Mailaragouda Patil."""

import threading

import pytest

from tests.conftest import make_settings
from vps.allocation import DEFAULT_LAYOUT, AllocationEngine, get_allocation
from vps.errors import Conflict, InvalidPlate, LotFull, NotFound, ValidationError


def test_default_layout_seeded(ctx):
    s = get_allocation(ctx).summary()
    assert s["capacity"] == sum(n for groups in DEFAULT_LAYOUT.values() for _, n in groups) == 100
    assert s["totals"]["VACANT"] == 100
    assert s["levels"][1]["HANDICAP"]["total"] == 4


def test_no_seed_when_disabled(clock):
    from vps.context import Context
    c = Context(make_settings(seed_default_layout=False), clock=clock)
    assert AllocationEngine(c).summary()["capacity"] == 0


@pytest.mark.tc("TC-SLOT-01")
@pytest.mark.req("VPS-F-005")
@pytest.mark.parametrize("cat", ["2W", "4W", "EV", "HANDICAP"])
def test_nearest_slot_matches_category(ctx, cat):
    eng = get_allocation(ctx)
    slot = eng.allocate(cat)
    assert slot["category"] == cat and slot["status"] == "ALLOCATED"
    others = [s for s in eng.list() if s["category"] == cat and s["id"] != slot["id"]]
    assert all((slot["level"], slot["distance"]) <= (o["level"], o["distance"]) for o in others)


@pytest.mark.tc("TC-SLOT-01")
def test_allocation_moves_to_next_nearest(ctx):
    eng = get_allocation(ctx)
    a, b = eng.allocate("4W"), eng.allocate("4W")
    assert a["id"] == "L1-C001" and b["id"] == "L1-C002"
    eng.release(a["id"])
    assert eng.allocate("4W")["id"] == "L1-C001"


@pytest.mark.tc("TC-SLOT-01")
def test_spills_to_next_level(ctx):
    eng = get_allocation(ctx)
    for _ in range(4):
        eng.allocate("EV")
    assert eng.allocate("EV")["level"] == 2


@pytest.mark.tc("TC-SLOT-04")
def test_lot_full(ctx):
    eng = get_allocation(ctx)
    for _ in range(4):
        eng.allocate("HANDICAP")
    with pytest.raises(LotFull):
        eng.allocate("HANDICAP")
    with pytest.raises(LotFull):
        for _ in range(10):
            eng.reserve_slot("HANDICAP")


@pytest.mark.tc("TC-SLOT-04")
def test_concurrent_allocation_never_double_books(ctx):
    eng = get_allocation(ctx)
    got, errors = [], []

    def worker():
        try:
            got.append(eng.allocate("4W")["id"])
        except LotFull as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(90)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(got) == 68 and len(set(got)) == 68 and len(errors) == 22    # 20 + 24 + 24 4W bays


def test_reserve_and_claim(ctx):
    eng = get_allocation(ctx)
    r = eng.reserve_slot("EV")
    assert r["status"] == "RESERVED"
    assert eng.find_nearest_vacant("EV")["id"] != r["id"]
    assert eng.claim_reserved(r["id"])["status"] == "ALLOCATED"
    with pytest.raises(Conflict):
        eng.claim_reserved(r["id"])


def test_add_slots_and_validation(ctx):
    eng = get_allocation(ctx)
    ids = eng.add_slots(1, "4W", 3)
    assert ids == ["L1-C021", "L1-C022", "L1-C023"]
    assert eng.get("L1-C023")["distance"] > eng.get("L1-C020")["distance"]
    with pytest.raises(ValidationError):
        eng.add_slots(1, "4W", 0)
    with pytest.raises(InvalidPlate):
        eng.add_slots(1, "TRUCK", 1)


def test_status_and_lookup_errors(ctx):
    eng = get_allocation(ctx)
    assert eng.set_status("L3-C001", "DISABLED")["status"] == "DISABLED"
    with pytest.raises(ValidationError):
        eng.set_status("L3-C001", "BROKEN")
    with pytest.raises(NotFound):
        eng.get("L9-Z999")
    with pytest.raises(NotFound):
        eng.release("L9-Z999")
    assert len(eng.list(level=3)) == 24


def test_slots_api(client):
    slots = client.get("/api/v1/slots").json()
    assert len(slots) == 100 and slots[0]["led"] == "GREEN"
    assert len(client.get("/api/v1/slots", params={"level": 2}).json()) == 36
    assert client.get("/api/v1/slots/summary").json()["capacity"] == 100
    assert client.get("/api/v1/slots/nearest/EV").json()["slot"]["id"] == "L1-E001"
