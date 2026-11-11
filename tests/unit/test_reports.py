"""Unit tests - analytics & exports (VPS-F-018). Owner: Himansh Ahuja."""

import csv
import io

import pytest

from vps.egress import get_egress
from vps.errors import ValidationError
from vps.ingress import get_ingress
from vps.reports import get_reports
from vps.tariff import get_tariff_engine


@pytest.fixture
def traffic(ctx, clock):
    """Three paid sessions on day 1 and one on day 2 (IST). Surge disabled to keep the arithmetic simple."""
    for rule in get_tariff_engine(ctx).surge_rules():
        get_tariff_engine(ctx).set_surge_active(rule["id"], False, "test")
    ing, eg = get_ingress(ctx), get_egress(ctx)
    for i, (cat, mins) in enumerate([("4W", 130), ("2W", 61), ("EV", 200)]):
        t = ing.process_entry("ENTRY-1", f"KA01AB{2000 + i}", cat)
        clock.advance(minutes=mins)
        eg.cash_payment(t["ticket_id"], "attendant")
    clock.advance(days=1)
    t = ing.process_entry("ENTRY-1", "KA01AB3000", "4W")
    clock.advance(minutes=45)
    eg.cash_payment(t["ticket_id"], "attendant")
    ing.process_entry("ENTRY-1", "KA01AB4000", "4W")            # still parked


@pytest.mark.tc("TC-ADM-02")
@pytest.mark.req("VPS-F-018")
class TestReports:
    def test_revenue_daily(self, ctx, traffic):
        r = get_reports(ctx).revenue("daily")
        assert [row["transactions"] for row in r["rows"]] == [3, 1]
        # 4W 3h=100, 2W 2h=30, EV 4h=115 -> 245 taxable; day 2: 4W 1h=40
        assert r["rows"][0]["taxable"] == 245.0 and r["rows"][1]["taxable"] == 40.0
        assert r["grand_total"] == round((245 + 40) * 1.18, 2)
        assert r["rows"][0]["cash"] == r["rows"][0]["total"]

    def test_revenue_monthly_and_range(self, ctx, traffic):
        assert len(get_reports(ctx).revenue("monthly")["rows"]) == 1
        assert get_reports(ctx).revenue("daily", "2026-10-21", "2026-10-21")["rows"][0]["transactions"] == 1

    def test_out_of_range_rows_excluded(self, ctx, traffic):
        assert get_reports(ctx).turnaround("daily", "2026-10-21", "2026-10-21")["rows"][0]["exits"] == 1
        assert sum(r["entries"] for r in get_reports(ctx).occupancy("daily", "2026-10-21", "2026-10-21")["rows"]) == 2

    def test_turnaround(self, ctx, traffic):
        rows = get_reports(ctx).turnaround("daily")["rows"]
        assert rows[0]["exits"] == 3 and rows[0]["max_minutes"] == 200.0 and rows[0]["min_minutes"] == 61.0

    def test_occupancy(self, ctx, traffic):
        o = get_reports(ctx).occupancy()
        assert sum(r["entries"] for r in o["rows"]) == 5
        assert o["overall_occupancy_pct"] == 1.0 and o["peak_hour"] is not None
        assert o["current"][0]["occupied"] == 1

    @pytest.mark.parametrize("fmt", ["csv", "pdf", "json"])
    @pytest.mark.parametrize("kind", ["revenue", "occupancy", "turnaround"])
    def test_export_under_5_seconds(self, ctx, traffic, kind, fmt):
        data, media, name, ms = get_reports(ctx).export(kind, "daily", fmt)
        assert ms <= 5000 and name.endswith("." + fmt) and data
        if fmt == "pdf":
            assert data.startswith(b"%PDF")
        if fmt == "csv":
            assert len(list(csv.DictReader(io.StringIO(data.decode())))) >= 1

    def test_empty_exports(self, ctx):
        assert get_reports(ctx).export("revenue", "daily", "csv")[0] == b"period\n"
        assert get_reports(ctx).export("turnaround", "daily", "pdf")[0].startswith(b"%PDF")
        assert get_reports(ctx).occupancy()["peak_hour"] is None

    @pytest.mark.parametrize("args", [("sales", "daily", "csv"), ("revenue", "weekly", "csv"), ("revenue", "daily", "xls")])
    def test_validation(self, ctx, args):
        with pytest.raises(ValidationError):
            get_reports(ctx).export(*args)

    def test_bad_dates(self, ctx):
        with pytest.raises(ValidationError):
            get_reports(ctx).revenue("daily", "20-10-2026")
        with pytest.raises(ValidationError):
            get_reports(ctx).revenue("daily", "2026-10-21", "2026-10-20")


def test_reports_api(client, ctx, clock, traffic, manager_headers, attendant_headers):
    assert client.get("/api/v1/reports/revenue", headers=attendant_headers).status_code == 403
    assert client.get("/api/v1/reports/revenue", headers=manager_headers).json()["kind"] == "revenue"
    r = client.get("/api/v1/reports/occupancy", params={"format": "csv"}, headers=manager_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert float(r.headers["x-export-time-ms"]) <= 5000 and "attachment" in r.headers["content-disposition"]
    assert client.get("/api/v1/reports/revenue", params={"format": "pdf", "period": "monthly"},
                      headers=manager_headers).content.startswith(b"%PDF")
    assert client.get("/api/v1/reports/unknown", headers=manager_headers).status_code == 400

