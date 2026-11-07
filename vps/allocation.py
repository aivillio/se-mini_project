"""Slot Allocation Engine (VPS-F-005).

Allocates the nearest vacant slot for the vehicle category. "Nearest" is the
lowest (level, distance-from-entrance) pair, i.e. the shortest drive route.
The select-and-lock runs inside a serialised transaction so two gates can never
receive the same slot.
"""

from __future__ import annotations

import copy
import threading

from vps.errors import Conflict, LotFull, NotFound, ValidationError
from vps.plates import CATEGORIES, validate_category

ZONE_FOR = {"2W": "B", "4W": "C", "EV": "E", "HANDICAP": "H"}
STATUSES = ("VACANT", "ALLOCATED", "OCCUPIED", "RESERVED", "DISABLED")

# level -> list of (category, count). Handicap and EV bays sit closest to the lifts.
DEFAULT_LAYOUT = {
    1: [("HANDICAP", 4), ("EV", 4), ("2W", 12), ("4W", 20)],
    2: [("EV", 2), ("2W", 10), ("4W", 24)],
    3: [("4W", 24)],
}


class AllocationEngine:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.version = 0                    # bumped on every slot change; lets signage/summary cache safely
        self._vlock = threading.Lock()
        self._summary_cache: tuple[int, dict] | None = None
        if ctx.settings.seed_default_layout and not self.db.scalar("SELECT COUNT(*) FROM slots"):
            self.seed_layout(DEFAULT_LAYOUT)

    # ---- layout configuration (also used by the admin console, VPS-F-017) ----
    def seed_layout(self, layout: dict[int, list[tuple[str, int]]]) -> int:
        total = 0
        for level, groups in layout.items():
            for category, count in groups:
                total += len(self.add_slots(level, category, count))
        return total

    def add_slots(self, level: int, category: str, count: int) -> list[str]:
        category = validate_category(category)
        if level < 0 or count <= 0 or count > 5000:
            raise ValidationError("level must be >= 0 and 0 < count <= 5000")
        zone = ZONE_FOR[category]
        prefix = f"L{level}-{zone}"
        with self.db.transaction():
            existing = self.db.scalar("SELECT COUNT(*) FROM slots WHERE id LIKE ?", (prefix + "%",))
            max_dist = self.db.scalar("SELECT COALESCE(MAX(distance), 0) FROM slots WHERE level = ?", (level,))
            ids = [f"{prefix}{existing + i + 1:03d}" for i in range(count)]
            self.db.executemany(
                "INSERT INTO slots (id, level, zone, category, distance, status, updated_at)"
                " VALUES (?,?,?,?,?,'VACANT',?)",
                [(sid, level, zone, category, max_dist + i + 1, self.ctx.now_iso()) for i, sid in enumerate(ids)],
            )
        self._bump()
        return ids

    # ---- queries -------------------------------------------------------------
    def get(self, slot_id: str) -> dict:
        slot = self.db.query_one("SELECT * FROM slots WHERE id = ?", (slot_id,))
        if not slot:
            raise NotFound(f"Slot {slot_id} not found")
        return slot

    def list(self, level: int | None = None) -> list[dict]:
        if level is None:
            return self.db.query("SELECT * FROM slots ORDER BY level, distance")
        return self.db.query("SELECT * FROM slots WHERE level = ? ORDER BY distance", (level,))

    def find_nearest_vacant(self, category: str) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM slots WHERE category = ? AND status = 'VACANT' ORDER BY level, distance, id LIMIT 1",
            (validate_category(category),),
        )

    def summary(self) -> dict:
        cached = self._summary_cache
        if cached and cached[0] == self.version:
            return copy.deepcopy(cached[1])
        version = self.version
        rows = self.db.query("SELECT level, category, status, COUNT(*) AS n FROM slots GROUP BY 1, 2, 3")
        levels: dict[int, dict] = {}
        totals = {s: 0 for s in STATUSES}
        for r in rows:
            lvl = levels.setdefault(r["level"], {c: {"vacant": 0, "total": 0} for c in CATEGORIES})
            lvl[r["category"]]["total"] += r["n"]
            if r["status"] == "VACANT":
                lvl[r["category"]]["vacant"] += r["n"]
            totals[r["status"]] += r["n"]
        result = {"levels": levels, "totals": totals, "capacity": sum(totals.values())}
        self._summary_cache = (version, result)
        return copy.deepcopy(result)

    # ---- state changes -------------------------------------------------------
    def allocate(self, category: str) -> dict:
        category = validate_category(category)
        with self.db.transaction():
            slot = self.find_nearest_vacant(category)
            if slot is None:
                raise LotFull(f"No vacant {category} slot available", details={"category": category})
            self._set(slot["id"], "ALLOCATED")
        slot["status"] = "ALLOCATED"
        return slot

    def reserve_slot(self, category: str) -> dict:
        category = validate_category(category)
        with self.db.transaction():
            slot = self.find_nearest_vacant(category)
            if slot is None:
                raise LotFull(f"No {category} slot available to reserve", details={"category": category})
            self._set(slot["id"], "RESERVED")
        slot["status"] = "RESERVED"
        return slot

    def claim_reserved(self, slot_id: str) -> dict:
        with self.db.transaction():
            slot = self.get(slot_id)
            if slot["status"] != "RESERVED":
                raise Conflict(f"Slot {slot_id} is not reserved (status {slot['status']})")
            self._set(slot_id, "ALLOCATED")
        return self.get(slot_id)

    def release(self, slot_id: str) -> dict:
        self.get(slot_id)
        self._set(slot_id, "VACANT")
        return self.get(slot_id)

    def set_status(self, slot_id: str, status: str) -> dict:
        if status not in STATUSES:
            raise ValidationError(f"status must be one of {STATUSES}")
        self.get(slot_id)
        self._set(slot_id, status)
        return self.get(slot_id)

    def _set(self, slot_id: str, status: str) -> None:
        self.db.execute("UPDATE slots SET status = ?, updated_at = ? WHERE id = ?", (status, self.ctx.now_iso(), slot_id))
        self._bump()

    def _bump(self) -> None:
        with self._vlock:
            self.version += 1


def get_allocation(ctx) -> AllocationEngine:
    return ctx.service("allocation", AllocationEngine)
