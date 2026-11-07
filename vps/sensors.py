"""Sensor Hub & Signage Service (VPS-F-006, VPS-F-007).

* Ultrasonic/magnetic slot sensors publish occupancy events (MQTT in production;
  HTTP in this build). Each event updates the slot status and its overhead LED
  within the same call (target <= 2 s).
* Entrance and per-floor Variable Message Signs (VMS) are re-rendered from the
  database on every change (target <= 1 s); ``version`` lets displays poll cheaply.
* Sensor events carry a monotonically increasing ``seq`` per sensor; replays of
  old sequence numbers are rejected (SRS security objective 3: sensor replay).
"""

from __future__ import annotations

import threading
import time

from vps.allocation import get_allocation
from vps.errors import Conflict

LED_FOR_STATUS = {"VACANT": "GREEN", "ALLOCATED": "RED", "OCCUPIED": "RED", "RESERVED": "BLUE", "DISABLED": "OFF"}


class SensorHub:
    def __init__(self, ctx):
        self.ctx = ctx
        self.alloc = get_allocation(ctx)
        self._last_seq: dict[str, int] = {}
        self._lock = threading.Lock()
        self.vms_updated_at = ctx.now_iso()
        self.last_event_latency_ms = 0.0
        self._boards_cache: tuple[int, dict] | None = None

    def handle_event(self, slot_id: str, occupied: bool, seq: int | None = None) -> dict:
        start = time.perf_counter()
        with self._lock:
            if seq is not None:
                last = self._last_seq.get(slot_id, -1)
                if seq <= last:
                    raise Conflict("Replayed or out-of-order sensor event rejected",
                                   code="SENSOR_REPLAY", details={"slot": slot_id, "seq": seq, "last_seq": last})
                self._last_seq[slot_id] = seq
        slot = self.alloc.get(slot_id)
        if occupied:
            new_status = "OCCUPIED"
        elif slot["status"] in ("OCCUPIED", "ALLOCATED"):
            new_status = "VACANT"
        else:  # a reserved/disabled bay reporting empty keeps its status
            new_status = slot["status"]
        if new_status != slot["status"]:
            self.alloc.set_status(slot_id, new_status)
        self.refresh_vms()
        self.last_event_latency_ms = (time.perf_counter() - start) * 1000
        return {
            "slot_id": slot_id,
            "status": new_status,
            "led": LED_FOR_STATUS[new_status],
            "latency_ms": round(self.last_event_latency_ms, 3),
        }

    def led_states(self) -> dict[str, str]:
        return {s["id"]: LED_FOR_STATUS[s["status"]] for s in self.alloc.list()}

    # ---- signage -----------------------------------------------------------
    @property
    def vms_version(self) -> int:
        return self.alloc.version

    def refresh_vms(self) -> None:
        """Called after any slot change; boards are re-rendered lazily on the next read."""
        self.vms_updated_at = self.ctx.now_iso()

    def vms_boards(self) -> dict:
        version = self.alloc.version
        cached = self._boards_cache
        if cached and cached[0] == version:
            return cached[1]
        summary = self.alloc.summary()
        level_boards = []
        entrance_total = 0
        for level in sorted(summary["levels"]):
            cats = summary["levels"][level]
            vacant = sum(c["vacant"] for c in cats.values())
            entrance_total += vacant
            line = "  ".join(f"{k}:{v['vacant']:>3}" for k, v in cats.items() if v["total"])
            level_boards.append({"board": f"LEVEL-{level}", "level": level, "vacant": vacant,
                           "by_category": {k: v["vacant"] for k, v in cats.items() if v["total"]},
                           "text": f"L{level}  {line}" if vacant else f"L{level}  FULL"})
        boards = {
            "version": version,
            "updated_at": self.vms_updated_at,
            "entrance": {"board": "ENTRANCE", "vacant": entrance_total,
                         "text": f"SPACES FREE: {entrance_total}" if entrance_total else "CAR PARK FULL"},
            "levels": level_boards,
        }
        self._boards_cache = (version, boards)
        return boards


def get_sensor_hub(ctx) -> SensorHub:
    return ctx.service("sensors", SensorHub)
