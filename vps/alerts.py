"""Operational alerts routed to the attendant fast-POS screen (SAD 4.4)."""

from __future__ import annotations

from vps.errors import NotFound, ValidationError

SEVERITIES = ("INFO", "WARNING", "CRITICAL")


class AlertService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db

    def raise_alert(self, kind: str, message: str, severity: str = "WARNING", lane_id: str | None = None) -> dict:
        if severity not in SEVERITIES:
            raise ValidationError(f"severity must be one of {SEVERITIES}")
        cur = self.db.execute(
            "INSERT INTO alerts (ts, kind, severity, lane_id, message) VALUES (?,?,?,?,?)",
            (self.ctx.now_iso(), kind, severity, lane_id, message),
        )
        return self.db.query_one("SELECT * FROM alerts WHERE id = ?", (cur.lastrowid,))

    def list(self, open_only: bool = True, limit: int = 50) -> list[dict]:
        where = "WHERE acked_at IS NULL" if open_only else ""
        return self.db.query(f"SELECT * FROM alerts {where} ORDER BY id DESC LIMIT ?", (limit,))

    def acknowledge(self, alert_id: int, username: str) -> dict:
        cur = self.db.execute(
            "UPDATE alerts SET acked_by = ?, acked_at = ? WHERE id = ? AND acked_at IS NULL",
            (username, self.ctx.now_iso(), alert_id),
        )
        if cur.rowcount == 0:
            raise NotFound(f"Open alert {alert_id} not found")
        return self.db.query_one("SELECT * FROM alerts WHERE id = ?", (alert_id,))


def get_alerts(ctx) -> AlertService:
    return ctx.service("alerts", AlertService)
