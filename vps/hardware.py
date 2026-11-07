"""Simulated gate-lane hardware (Test Plan risk mitigation: hardware stubs).

Each lane has an ANPR camera, a ground (inductive) loop, a motorised boom
barrier driven through a relay, and a thermal ticket printer. The simulators
behave like the real devices at the interface level so the business logic and
the tests are identical to a deployment with real hardware drivers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from vps.errors import EdgeOffline, HardwareFault, NotFound, PlateUnreadable, ValidationError
from vps.plates import validate_plate


@dataclass
class PlateRead:
    plate: str
    confidence: float
    latency_ms: float


class ANPRCamera:
    """VPS-F-001: capture plate within 1.5 s with >= 95% accuracy."""

    MIN_CONFIDENCE = 0.80   # below this the read is routed to the attendant

    def __init__(self, lane_id: str):
        self.lane_id = lane_id
        self.online = True
        self.reads = 0

    def capture(self, raw_plate: str, confidence: float = 0.97) -> PlateRead:
        start = time.perf_counter()
        if not self.online:
            raise HardwareFault(f"ANPR camera on {self.lane_id} is offline", details={"lane": self.lane_id})
        if not 0.0 <= confidence <= 1.0:
            raise ValidationError("confidence must be between 0 and 1")
        if confidence < self.MIN_CONFIDENCE:
            raise PlateUnreadable(
                "Plate could not be read reliably - attendant assistance required",
                details={"lane": self.lane_id, "confidence": confidence},
            )
        plate = validate_plate(raw_plate)
        self.reads += 1
        return PlateRead(plate, confidence, (time.perf_counter() - start) * 1000)


class GroundLoop:
    def __init__(self):
        self.occupied = False


class BoomBarrier:
    """VPS-F-003 (raise <= 500 ms) and VPS-F-004 (no descent while loop occupied)."""

    def __init__(self, lane_id: str, loop: GroundLoop):
        self.lane_id = lane_id
        self.loop = loop
        self.state = "DOWN"
        self.faulted = False
        self.cycles = 0

    def raise_barrier(self) -> dict:
        start = time.perf_counter()
        if self.faulted:
            raise HardwareFault(f"Barrier relay fault on {self.lane_id}", details={"lane": self.lane_id})
        self.state = "UP"
        self.cycles += 1
        return {"state": self.state, "latency_ms": round((time.perf_counter() - start) * 1000, 3)}

    def lower_barrier(self) -> dict:
        if self.loop.occupied:
            return {"state": self.state, "halted": True, "reason": "VEHICLE_ON_LOOP"}
        self.state = "DOWN"
        return {"state": self.state, "halted": False}


class ThermalPrinter:
    def __init__(self):
        self.paper_ok = True
        self.printed: list[dict] = []

    def print_ticket(self, content: dict) -> None:
        if not self.paper_ok:
            raise HardwareFault("Ticket printer out of paper")
        self.printed.append(content)


@dataclass
class Lane:
    lane_id: str
    direction: str                     # ENTRY | EXIT
    camera: ANPRCamera = field(init=False)
    loop: GroundLoop = field(init=False)
    barrier: BoomBarrier = field(init=False)
    printer: ThermalPrinter = field(init=False)
    controller_online: bool = True

    def __post_init__(self):
        self.camera = ANPRCamera(self.lane_id)
        self.loop = GroundLoop()
        self.barrier = BoomBarrier(self.lane_id, self.loop)
        self.printer = ThermalPrinter()

    def vehicle_on_loop(self, occupied: bool) -> dict:
        """Loop transitions. When the vehicle clears the loop the barrier auto-lowers."""
        self.loop.occupied = occupied
        if not occupied and self.barrier.state == "UP":
            return self.barrier.lower_barrier()
        return {"state": self.barrier.state, "halted": occupied and self.barrier.state == "UP"}

    def snapshot(self) -> dict:
        return {
            "lane_id": self.lane_id,
            "direction": self.direction,
            "barrier": self.barrier.state,
            "loop_occupied": self.loop.occupied,
            "camera_online": self.camera.online,
            "printer_paper_ok": self.printer.paper_ok,
            "controller_online": self.controller_online,
        }


class HardwareRegistry:
    DEFAULT_LANES = (("ENTRY-1", "ENTRY"), ("ENTRY-2", "ENTRY"), ("EXIT-1", "EXIT"), ("EXIT-2", "EXIT"))

    @classmethod
    def with_pairs(cls, pairs: int) -> "HardwareRegistry":
        lanes = [(f"ENTRY-{i}", "ENTRY") for i in range(1, pairs + 1)] + [(f"EXIT-{i}", "EXIT") for i in range(1, pairs + 1)]
        return cls(tuple(lanes))

    def __init__(self, lanes=DEFAULT_LANES):
        self.lanes: dict[str, Lane] = {lid: Lane(lid, d) for lid, d in lanes}

    def add_lane(self, lane_id: str, direction: str) -> Lane:
        if direction not in ("ENTRY", "EXIT"):
            raise ValidationError("direction must be ENTRY or EXIT")
        self.lanes[lane_id] = Lane(lane_id, direction)
        return self.lanes[lane_id]

    def get(self, lane_id: str, direction: str | None = None) -> Lane:
        lane = self.lanes.get(lane_id)
        if lane is None:
            raise NotFound(f"Unknown lane '{lane_id}'")
        if direction and lane.direction != direction:
            raise ValidationError(f"Lane {lane_id} is an {lane.direction} lane")
        if not lane.controller_online:
            raise EdgeOffline(f"Edge controller for {lane_id} is offline", details={"lane": lane_id})
        return lane

    def snapshot(self) -> list[dict]:
        return [lane.snapshot() for lane in self.lanes.values()]


def get_hardware(ctx) -> HardwareRegistry:
    return ctx.service("hardware", lambda c: HardwareRegistry.with_pairs(c.settings.lane_pairs))
