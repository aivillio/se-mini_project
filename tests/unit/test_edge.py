"""Unit tests - edge store-and-forward queue (VPS-NF-005). Owner: Shweta Mailaragouda Patil."""

import pytest

from vps.edge_queue import get_edge


@pytest.mark.tc("TC-Fault-01")
@pytest.mark.req("VPS-NF-005")
class TestEdgeQueue:
    def test_online_forwards_immediately(self, ctx):
        edge = get_edge(ctx)
        edge.record("ENTRY-1", "ENTRY", {"t": 1})
        st = edge.status()
        assert st["pending"] == 0 and st["central_events"] == 1

    def test_offline_queues_then_syncs_in_order(self, ctx):
        edge = get_edge(ctx)
        edge.set_online(False)
        ids = [edge.record("ENTRY-1", "ENTRY", {"n": i}) for i in range(5)]
        assert edge.status()["pending"] == 5 and edge.status()["central_events"] == 0
        assert edge.flush() == {"synced": 0, "duration_ms": 0.0}        # no-op while offline
        out = edge.set_online(True)
        assert out["sync"]["synced"] == 5 and out["pending"] == 0 and out["central_events"] == 5
        received = [r["event_id"] for r in ctx.db.query("SELECT event_id FROM central_events ORDER BY occurred_at, rowid")]
        assert received == ids

    def test_replay_is_idempotent(self, ctx):
        edge = get_edge(ctx)
        edge.record("ENTRY-1", "ENTRY", {})
        ctx.edge_db.execute("UPDATE edge_queue SET synced_at = NULL")       # simulate lost ack
        edge.flush()
        assert ctx.db.scalar("SELECT COUNT(*) FROM central_events") == 1

    def test_offline_budget_72h(self, ctx, clock):
        edge = get_edge(ctx)
        edge.set_online(False)
        edge.record("ENTRY-1", "ENTRY", {})
        clock.advance(hours=71)
        assert edge.status()["within_offline_budget"] is True
        clock.advance(hours=2)
        st = edge.status()
        assert st["oldest_pending_age_hours"] == 73.0 and st["within_offline_budget"] is False
