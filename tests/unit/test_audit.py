"""Unit tests - immutable hash-chained audit log (VPS-SR-005). Owner: Angelo Arakal."""

import sqlite3

import pytest

from vps.audit import GENESIS, get_audit
from vps.context import parse_ts


@pytest.mark.tc("TC-SEC-05")
@pytest.mark.req("VPS-SR-005")
class TestAuditLog:
    def test_hash_chain(self, ctx):
        log = get_audit(ctx)
        a = log.record("admin", "TARIFF_UPDATED", {"category": "4W"})
        b = log.record("attendant", "BARRIER_OVERRIDE", {"lane": "EXIT-1"})
        assert a["prev_hash"] == GENESIS and b["prev_hash"] == a["hash"]
        assert log.verify() == {"valid": True, "entries": 2, "broken_at": None}

    def test_update_and_delete_refused_by_database(self, ctx):
        e = get_audit(ctx).record("admin", "X", {})
        with pytest.raises(sqlite3.IntegrityError, match="write-once"):
            ctx.db.execute("UPDATE audit_log SET actor = 'mallory' WHERE id = ?", (e["id"],))
        with pytest.raises(sqlite3.IntegrityError, match="write-once"):
            ctx.db.execute("DELETE FROM audit_log")

    def test_out_of_band_tampering_detected(self, ctx):
        log = get_audit(ctx)
        for i in range(3):
            log.record("admin", "TARIFF_UPDATED", {"i": i})
        ctx.db.execute("DROP TRIGGER audit_no_update")                     # attacker with raw DB access
        ctx.db.execute("UPDATE audit_log SET details = '{\"i\":99}' WHERE id = 2")
        assert log.verify() == {"valid": False, "entries": 2, "broken_at": 2}

    def test_retention_three_years(self, ctx):
        e = get_audit(ctx).record("admin", "X", {})
        assert (parse_ts(e["retain_until"]) - parse_ts(e["ts"])).days >= 3 * 365

    def test_entries_filter(self, ctx):
        log = get_audit(ctx)
        log.record("a", "ONE", {"k": 1})
        log.record("a", "TWO", {})
        assert [e["action"] for e in log.entries()] == ["TWO", "ONE"]
        assert log.entries(action="ONE")[0]["details"] == {"k": 1}
