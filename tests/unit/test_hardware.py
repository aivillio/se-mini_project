"""Unit tests - plates + hardware simulators (VPS-F-001, F-003, F-004). Owner: Shweta Mailaragouda Patil."""

import pytest

from vps.errors import EdgeOffline, HardwareFault, InvalidPlate, NotFound, PlateUnreadable, ValidationError
from vps.hardware import ANPRCamera, BoomBarrier, GroundLoop, HardwareRegistry, Lane, ThermalPrinter
from vps.plates import is_valid_plate, mask_plate, normalize_plate, validate_category, validate_plate


@pytest.mark.tc("TC-ENT-01")
@pytest.mark.parametrize("raw,expected", [("ka 01 ab 1234", "KA01AB1234"), ("DL-3C-AF-0001", "DL3CAF0001"),
                                          ("22 BH 1234 AA", "22BH1234AA"), ("MH12.XY.9999", "MH12XY9999")])
def test_plate_normalisation(raw, expected):
    assert validate_plate(raw) == expected


@pytest.mark.parametrize("bad", ["", "ABC", "KA01AB12", "1234", "KAA1AB1234"])
def test_invalid_plates(bad):
    assert not is_valid_plate(normalize_plate(bad))
    with pytest.raises(InvalidPlate):
        validate_plate(bad)


def test_category_and_mask():
    assert validate_category("ev") == "EV"
    with pytest.raises(InvalidPlate):
        validate_category("BUS")
    assert mask_plate("KA01AB1234") == "KA01****34"
    assert mask_plate("ABC") == "ABC"


@pytest.mark.tc("TC-ENT-01")
@pytest.mark.req("VPS-F-001")
class TestCamera:
    def test_capture_ok(self):
        r = ANPRCamera("ENTRY-1").capture("ka01ab1234", 0.96)
        assert r.plate == "KA01AB1234" and r.latency_ms <= 1500

    def test_low_confidence(self):
        with pytest.raises(PlateUnreadable):
            ANPRCamera("ENTRY-1").capture("KA01AB1234", 0.79)

    def test_confidence_range(self):
        with pytest.raises(ValidationError):
            ANPRCamera("ENTRY-1").capture("KA01AB1234", 1.5)

    def test_offline(self):
        cam = ANPRCamera("ENTRY-1")
        cam.online = False
        with pytest.raises(HardwareFault):
            cam.capture("KA01AB1234")


@pytest.mark.tc("TC-ENT-03", "TC-ENT-04")
@pytest.mark.req("VPS-F-003", "VPS-F-004")
class TestBarrier:
    def test_raise_and_lower(self):
        b = BoomBarrier("L", GroundLoop())
        r = b.raise_barrier()
        assert r["state"] == "UP" and r["latency_ms"] <= 500 and b.cycles == 1
        assert b.lower_barrier() == {"state": "DOWN", "halted": False}

    def test_halt_on_loop(self):
        loop = GroundLoop()
        b = BoomBarrier("L", loop)
        b.raise_barrier()
        loop.occupied = True
        assert b.lower_barrier()["halted"] is True and b.state == "UP"

    def test_relay_fault(self):
        b = BoomBarrier("L", GroundLoop())
        b.faulted = True
        with pytest.raises(HardwareFault):
            b.raise_barrier()

    def test_lane_auto_lower_after_vehicle_clears(self):
        lane = Lane("ENTRY-1", "ENTRY")
        lane.barrier.raise_barrier()
        assert lane.vehicle_on_loop(True)["halted"] is True
        assert lane.vehicle_on_loop(False)["state"] == "DOWN"
        assert lane.vehicle_on_loop(False) == {"state": "DOWN", "halted": False}


def test_printer_out_of_paper():
    p = ThermalPrinter()
    p.print_ticket({"x": 1})
    p.paper_ok = False
    with pytest.raises(HardwareFault):
        p.print_ticket({"x": 2})
    assert len(p.printed) == 1


def test_registry():
    reg = HardwareRegistry()
    assert {lane["lane_id"] for lane in reg.snapshot()} == {"ENTRY-1", "ENTRY-2", "EXIT-1", "EXIT-2"}
    reg.add_lane("ENTRY-9", "ENTRY")
    assert reg.get("ENTRY-9", "ENTRY").direction == "ENTRY"
    with pytest.raises(ValidationError):
        reg.add_lane("X", "SIDEWAYS")
    with pytest.raises(ValidationError):
        reg.get("EXIT-1", "ENTRY")
    with pytest.raises(NotFound):
        reg.get("NOPE")
    reg.lanes["EXIT-2"].controller_online = False
    with pytest.raises(EdgeOffline):
        reg.get("EXIT-2")
