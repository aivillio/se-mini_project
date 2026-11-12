"""Analytics & exportable reports (VPS-F-018): revenue, occupancy, turnaround.

Exports are generated as CSV or PDF; AC-VPS-F-018 requires <= 5 s per export,
the measured time is returned with every export.
"""

from __future__ import annotations

import csv
import io
import json
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from vps.allocation import get_allocation
from vps.context import parse_ts
from vps.errors import ValidationError

KINDS = ("revenue", "occupancy", "turnaround")
PERIODS = ("daily", "monthly")
FORMATS = ("json", "csv", "pdf")


class ReportService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.alloc = get_allocation(ctx)

    def _bucket(self, iso: str, period: str) -> str:
        local = parse_ts(iso).astimezone(self.ctx.tz)
        return local.strftime("%Y-%m-%d" if period == "daily" else "%Y-%m")

    def _range(self, from_date: str | None, to_date: str | None) -> tuple[datetime, datetime]:
        today = self.ctx.now().astimezone(self.ctx.tz).date()
        try:
            d_to = date.fromisoformat(to_date) if to_date else today
            d_from = date.fromisoformat(from_date) if from_date else d_to - timedelta(days=29)
        except ValueError:
            raise ValidationError("dates must be YYYY-MM-DD") from None
        if d_from > d_to:
            raise ValidationError("from_date must be on or before to_date")
        start = datetime.combine(d_from, datetime.min.time(), self.ctx.tz)
        end = datetime.combine(d_to + timedelta(days=1), datetime.min.time(), self.ctx.tz)
        return start, end

    # ------------------------------------------------------------------ reports
    def revenue(self, period: str = "daily", from_date: str | None = None, to_date: str | None = None) -> dict:
        start, end = self._range(from_date, to_date)
        rows = self.db.query("SELECT p.*, COALESCE(p.updated_at, p.created_at) AS paid_at FROM payments p "
                             "WHERE p.status = 'CAPTURED'")
        agg: dict[str, dict] = defaultdict(lambda: {"transactions": 0, "taxable": 0.0, "gst": 0.0, "total": 0.0,
                                                    "upi": 0.0, "card": 0.0, "wallet": 0.0, "netbanking": 0.0,
                                                    "cash": 0.0, "none": 0.0})
        for r in rows:
            paid = parse_ts(r["paid_at"])
            if not (start <= paid < end):
                continue
            fare = json.loads(r["fare_json"])
            b = agg[self._bucket(r["paid_at"], period)]
            b["transactions"] += 1
            b["taxable"] += fare["taxable_amount"]
            b["gst"] += fare["cgst"] + fare["sgst"]
            b["total"] += r["amount"]
            b[r["method"]] += r["amount"]
        out = [{"period": k, **{f: round(v, 2) if isinstance(v, float) else v for f, v in d.items()}}
               for k, d in sorted(agg.items())]
        return {"kind": "revenue", "period": period, "rows": out,
                "grand_total": round(sum(r["total"] for r in out), 2)}

    def turnaround(self, period: str = "daily", from_date: str | None = None, to_date: str | None = None) -> dict:
        start, end = self._range(from_date, to_date)
        rows = self.db.query("SELECT entry_time, exit_time, category FROM tickets WHERE exit_time IS NOT NULL")
        agg: dict[str, list] = defaultdict(list)
        for r in rows:
            out_t = parse_ts(r["exit_time"])
            if start <= out_t < end:
                agg[self._bucket(r["exit_time"], period)].append((out_t - parse_ts(r["entry_time"])).total_seconds() / 60)
        out = [{"period": k, "exits": len(v), "avg_minutes": round(sum(v) / len(v), 1),
                "max_minutes": round(max(v), 1), "min_minutes": round(min(v), 1)} for k, v in sorted(agg.items())]
        return {"kind": "turnaround", "period": period, "rows": out}

    def occupancy(self, period: str = "daily", from_date: str | None = None, to_date: str | None = None) -> dict:
        start, end = self._range(from_date, to_date)
        summary = self.alloc.summary()
        cap = summary["capacity"] or 1
        current = []
        for level, cats in sorted(summary["levels"].items()):
            total = sum(c["total"] for c in cats.values())
            vacant = sum(c["vacant"] for c in cats.values())
            current.append({"level": level, "capacity": total, "occupied": total - vacant,
                            "occupancy_pct": round(100 * (total - vacant) / total, 1) if total else 0.0})
        entries = self.db.query("SELECT entry_time FROM tickets")
        by_period: dict[str, int] = defaultdict(int)
        by_hour: dict[int, int] = defaultdict(int)
        for e in entries:
            t = parse_ts(e["entry_time"])
            if start <= t < end:
                by_period[self._bucket(e["entry_time"], period)] += 1
                by_hour[t.astimezone(self.ctx.tz).hour] += 1
        peak = max(by_hour.items(), key=lambda kv: kv[1]) if by_hour else (None, 0)
        rows = [{"period": k, "entries": v} for k, v in sorted(by_period.items())]
        in_use = sum(c["occupied"] for c in current)
        return {"kind": "occupancy", "period": period, "rows": rows, "current": current,
                "overall_occupancy_pct": round(100 * in_use / cap, 1),
                "peak_hour": peak[0], "peak_hour_entries": peak[1]}

    # ------------------------------------------------------------------ export
    def build(self, kind: str, period: str = "daily", from_date: str | None = None, to_date: str | None = None) -> dict:
        if kind not in KINDS:
            raise ValidationError(f"kind must be one of {KINDS}")
        if period not in PERIODS:
            raise ValidationError(f"period must be one of {PERIODS}")
        return getattr(self, kind)(period, from_date, to_date)

    def export(self, kind: str, period: str = "daily", fmt: str = "csv", from_date: str | None = None,
               to_date: str | None = None) -> tuple[bytes, str, str, float]:
        if fmt not in FORMATS:
            raise ValidationError(f"format must be one of {FORMATS}")
        t0 = time.perf_counter()
        report = self.build(kind, period, from_date, to_date)
        stamp = self.ctx.now().astimezone(self.ctx.tz).strftime("%Y%m%d-%H%M")
        name = f"vps-{kind}-{period}-{stamp}.{fmt}"
        if fmt == "csv":
            data, media = self._csv(report), "text/csv"
        elif fmt == "pdf":
            data, media = self._pdf(report), "application/pdf"
        else:
            data, media = json.dumps(report, indent=2).encode(), "application/json"
        return data, media, name, round((time.perf_counter() - t0) * 1000, 2)

    @staticmethod
    def _csv(report: dict) -> bytes:
        buf = io.StringIO()
        rows = report["rows"]
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        else:
            buf.write("period\n")
        return buf.getvalue().encode()

    def _pdf(self, report: dict) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title=f"VPS {report['kind']} report")
        styles = getSampleStyleSheet()
        story = [Paragraph(f"Vehicle Parking System - {report['kind'].title()} Report ({report['period']})",
                           styles["Title"]),
                 Paragraph(f"{self.ctx.settings.facility_name} &middot; generated "
                           f"{self.ctx.now().astimezone(self.ctx.tz):%d %b %Y %H:%M}", styles["Normal"]),
                 Spacer(1, 12)]
        rows = report["rows"]
        if rows:
            head = list(rows[0].keys())
            data = [head] + [[str(r[h]) for h in head] for r in rows]
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("No data for the selected range.", styles["Normal"]))
        if report["kind"] == "revenue":
            story += [Spacer(1, 10), Paragraph(f"<b>Grand total: Rs {report['grand_total']:.2f}</b>", styles["Normal"])]
        if report["kind"] == "occupancy":
            story += [Spacer(1, 10), Paragraph(
                f"Current occupancy {report['overall_occupancy_pct']}% &middot; peak hour "
                f"{report['peak_hour']}:00 ({report['peak_hour_entries']} entries)", styles["Normal"])]
        doc.build(story)
        return buf.getvalue()


def get_reports(ctx) -> ReportService:
    return ctx.service("reports", ReportService)
