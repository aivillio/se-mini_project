"""Edge gate controller store-and-forward queue (VPS-NF-005, SAD 3.4/3.6).

Every lane transaction (ENTRY / EXIT / OVERRIDE) is first written to the edge
controller's local SQLite queue and then forwarded to the central server.
While the WAN link is down the lanes keep working and events accumulate
locally (designed for >= 72 hours). On reconnect the queue is flushed in order;
``event_id`` acts as an idempotency key so replays never double-count.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta

from vps.context import parse_ts


class EdgeController:
    def __init__(self, ctx):
        self.ctx = ctx
        self.local = ctx.edge_db
        self.central = ctx.db
        self.online = True
        self.last_sync: dict | None = None

    def record(self, lane_id: str, kind: str, payload: dict) -> str:
        event_id = str(uuid.uuid4())
        self.local.execute(
            "INSERT INTO edge_queue (event_id, lane_id, kind, payload, created_at) VALUES (?,?,?,?,?)",
            (event_id, lane_id, kind, json.dumps(payload, sort_keys=True), self.ctx.now_iso()),
        )
        if self.online:
            self.flush()
        return event_id

    def set_online(self, online: bool) -> dict:
        self.online = online
        result = self.flush() if online else {"synced": 0, "duration_ms": 0.0}
        return {**self.status(), "sync": result}

    def flush(self) -> dict:
        if not self.online:
            return {"synced": 0, "duration_ms": 0.0}
        start = time.perf_counter()
        pending = self.local.query("SELECT * FROM edge_queue WHERE synced_at IS NULL ORDER BY seq")
        now = self.ctx.now_iso()
        for ev in pending:
            self.central.execute(
                "INSERT OR IGNORE INTO central_events (event_id, lane_id, kind, payload, occurred_at, received_at)"
                " VALUES (?,?,?,?,?,?)",
                (ev["event_id"], ev["lane_id"], ev["kind"], ev["payload"], ev["created_at"], now),
            )
            self.local.execute("UPDATE edge_queue SET synced_at = ? WHERE seq = ?", (now, ev["seq"]))
        self.last_sync = {"synced": len(pending), "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                          "at": now}
        return self.last_sync

    def status(self) -> dict:
        pending = self.local.scalar("SELECT COUNT(*) FROM edge_queue WHERE synced_at IS NULL")
        oldest = self.local.scalar("SELECT MIN(created_at) FROM edge_queue WHERE synced_at IS NULL")
        age_h = 0.0
        if oldest:
            age_h = (self.ctx.now() - parse_ts(oldest)) / timedelta(hours=1)
        return {
            "online": self.online,
            "pending": pending,
            "oldest_pending_age_hours": round(age_h, 2),
            "within_offline_budget": age_h <= self.ctx.settings.edge_queue_max_hours,
            "central_events": self.central.scalar("SELECT COUNT(*) FROM central_events"),
            "last_sync": self.last_sync,
        }


def get_edge(ctx) -> EdgeController:
    return ctx.service("edge", EdgeController)
