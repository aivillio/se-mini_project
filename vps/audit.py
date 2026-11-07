"""Immutable, hash-chained audit log (VPS-SR-005).

Two layers of protection:
1. SQLite triggers reject UPDATE/DELETE on ``audit_log`` (write-once).
2. Every entry stores ``hash = SHA256(prev_hash | ts | actor | action | details)``
   so any out-of-band modification of the file breaks the chain and is detected
   by :meth:`AuditLog.verify`.
Entries carry ``retain_until`` = ts + 3 years (retention requirement).
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

GENESIS = "0" * 64
RETENTION_DAYS = 3 * 365 + 1


def _entry_hash(prev_hash: str, ts: str, actor: str, action: str, details: str) -> str:
    return hashlib.sha256("|".join((prev_hash, ts, actor, action, details)).encode()).hexdigest()


class AuditLog:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db

    def record(self, actor: str, action: str, details: dict | None = None) -> dict:
        details_json = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))
        with self.db.transaction():
            last = self.db.query_one("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1")
            prev = last["hash"] if last else GENESIS
            now = self.ctx.now()
            ts = now.isoformat()
            retain = (now + timedelta(days=RETENTION_DAYS)).isoformat()
            digest = _entry_hash(prev, ts, actor, action, details_json)
            cur = self.db.execute(
                "INSERT INTO audit_log (ts, actor, action, details, retain_until, prev_hash, hash)"
                " VALUES (?,?,?,?,?,?,?)",
                (ts, actor, action, details_json, retain, prev, digest),
            )
        return self.db.query_one("SELECT * FROM audit_log WHERE id = ?", (cur.lastrowid,))

    def entries(self, limit: int = 100, action: str | None = None) -> list[dict]:
        if action:
            rows = self.db.query(
                "SELECT * FROM audit_log WHERE action = ? ORDER BY id DESC LIMIT ?", (action, limit)
            )
        else:
            rows = self.db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["details"] = json.loads(r["details"])
        return rows

    def verify(self) -> dict:
        prev = GENESIS
        count = 0
        for row in self.db.query("SELECT * FROM audit_log ORDER BY id"):
            count += 1
            expected = _entry_hash(prev, row["ts"], row["actor"], row["action"], row["details"])
            if row["prev_hash"] != prev or row["hash"] != expected:
                return {"valid": False, "entries": count, "broken_at": row["id"]}
            prev = row["hash"]
        return {"valid": True, "entries": count, "broken_at": None}


def get_audit(ctx) -> AuditLog:
    return ctx.service("audit", AuditLog)
