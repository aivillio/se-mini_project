"""Tariff Engine (VPS-F-008, VPS-F-009, VPS-F-010, VPS-F-017).

Fare rules (all tariffs GST-exclusive, INR):
* duration <= grace period (15 min)            -> Rs 0 (transit drop-off)
* otherwise billable hours = ceil(minutes / 60)
* each full 24 h block is charged the category's daily cap
* the remaining hours: first_hour + (h - 1) * per_hour, capped at daily_cap
* surge: if the exit time (local) falls in an active peak window the base
  amount is multiplied by the rule's multiplier
* coupon: PERCENT or FLAT discount on (base + surge), never below zero
* GST 18% = CGST 9% + SGST 9% on the taxable amount
Tariffs are read from the database on every calculation, so admin edits take
effect immediately without a restart (AC-VPS-F-017).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from vps.audit import get_audit
from vps.context import parse_ts
from vps.errors import NotFound, ValidationError
from vps.plates import CATEGORIES, validate_category

DEFAULT_TARIFFS = {
    "2W": (20.0, 10.0, 150.0),
    "4W": (40.0, 30.0, 400.0),
    "EV": (40.0, 25.0, 350.0),
    "HANDICAP": (20.0, 10.0, 120.0),
}
DEFAULT_SURGE = [("Evening peak", 17, 20, 1.25)]
DEFAULT_COUPONS = [("WELCOME10", "PERCENT", 10.0, None), ("FLAT50", "FLAT", 50.0, None)]


def _money(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class FareBreakdown:
    category: str
    entry_time: str
    exit_time: str
    duration_minutes: int
    billable_hours: int
    grace_applied: bool
    base_amount: float
    surge_rule: str | None
    surge_multiplier: float
    surge_amount: float
    coupon_code: str | None
    discount: float
    taxable_amount: float
    cgst: float
    sgst: float
    total: float

    def to_dict(self) -> dict:
        return asdict(self)


class TariffEngine:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.audit = get_audit(ctx)
        self._seed()

    def _seed(self) -> None:
        if not self.db.scalar("SELECT COUNT(*) FROM tariffs"):
            for cat, (f, p, c) in DEFAULT_TARIFFS.items():
                self.db.execute("INSERT INTO tariffs VALUES (?,?,?,?,?)", (cat, f, p, c, self.ctx.now_iso()))
            for name, s, e, m in DEFAULT_SURGE:
                self.db.execute("INSERT INTO surge_rules (name, start_hour, end_hour, multiplier) VALUES (?,?,?,?)",
                                (name, s, e, m))
            for code, kind, value, exp in DEFAULT_COUPONS:
                self.db.execute("INSERT INTO coupons (code, kind, value, expires_at) VALUES (?,?,?,?)",
                                (code, kind, value, exp))

    # ---------------------------------------------------------------- tariffs
    def get_tariffs(self) -> list[dict]:
        return self.db.query("SELECT * FROM tariffs ORDER BY category")

    def get_tariff(self, category: str) -> dict:
        t = self.db.query_one("SELECT * FROM tariffs WHERE category = ?", (validate_category(category),))
        if not t:  # pragma: no cover - seeded for every category
            raise NotFound(f"No tariff for {category}")
        return t

    def update_tariff(self, category: str, first_hour: float, per_hour: float, daily_cap: float, actor: str) -> dict:
        category = validate_category(category)
        if min(first_hour, per_hour, daily_cap) < 0:
            raise ValidationError("tariff amounts cannot be negative")
        if daily_cap < first_hour:
            raise ValidationError("daily cap must be >= first-hour rate")
        old = self.get_tariff(category)
        self.db.execute("UPDATE tariffs SET first_hour=?, per_hour=?, daily_cap=?, updated_at=? WHERE category=?",
                        (first_hour, per_hour, daily_cap, self.ctx.now_iso(), category))
        new = self.get_tariff(category)
        self.audit.record(actor, "TARIFF_UPDATED", {"category": category,
                                                    "old": {k: old[k] for k in ("first_hour", "per_hour", "daily_cap")},
                                                    "new": {k: new[k] for k in ("first_hour", "per_hour", "daily_cap")}})
        return new

    # ---------------------------------------------------------------- surge
    def surge_rules(self) -> list[dict]:
        return self.db.query("SELECT * FROM surge_rules ORDER BY start_hour")

    def add_surge_rule(self, name: str, start_hour: int, end_hour: int, multiplier: float, actor: str) -> dict:
        if not (0 <= start_hour < end_hour <= 24):
            raise ValidationError("require 0 <= start_hour < end_hour <= 24")
        if not (1.0 <= multiplier <= 3.0):
            raise ValidationError("multiplier must be between 1.0 and 3.0")
        cur = self.db.execute("INSERT INTO surge_rules (name, start_hour, end_hour, multiplier) VALUES (?,?,?,?)",
                              (name, start_hour, end_hour, multiplier))
        self.audit.record(actor, "SURGE_RULE_ADDED", {"id": cur.lastrowid, "name": name, "window": [start_hour, end_hour],
                                                      "multiplier": multiplier})
        return self.db.query_one("SELECT * FROM surge_rules WHERE id = ?", (cur.lastrowid,))

    def set_surge_active(self, rule_id: int, active: bool, actor: str) -> dict:
        cur = self.db.execute("UPDATE surge_rules SET active = ? WHERE id = ?", (1 if active else 0, rule_id))
        if cur.rowcount == 0:
            raise NotFound(f"Surge rule {rule_id} not found")
        self.audit.record(actor, "SURGE_RULE_TOGGLED", {"id": rule_id, "active": active})
        return self.db.query_one("SELECT * FROM surge_rules WHERE id = ?", (rule_id,))

    def active_surge(self, at: datetime) -> dict | None:
        hour = at.astimezone(self.ctx.tz).hour
        return self.db.query_one(
            "SELECT * FROM surge_rules WHERE active = 1 AND start_hour <= ? AND ? < end_hour "
            "ORDER BY multiplier DESC LIMIT 1", (hour, hour))

    # ---------------------------------------------------------------- coupons
    def coupons(self) -> list[dict]:
        return self.db.query("SELECT * FROM coupons ORDER BY code")

    def create_coupon(self, code: str, kind: str, value: float, actor: str, *, max_uses: int | None = None,
                      expires_at: str | None = None) -> dict:
        code = (code or "").strip().upper()
        if not code.isalnum() or len(code) > 20:
            raise ValidationError("coupon code must be 1-20 alphanumeric characters")
        if kind not in ("PERCENT", "FLAT") or value <= 0 or (kind == "PERCENT" and value > 100):
            raise ValidationError("invalid coupon kind/value")
        if self.db.query_one("SELECT 1 FROM coupons WHERE code = ?", (code,)):
            raise ValidationError(f"coupon {code} already exists")
        self.db.execute("INSERT INTO coupons (code, kind, value, max_uses, expires_at) VALUES (?,?,?,?,?)",
                        (code, kind, value, max_uses, expires_at))
        self.audit.record(actor, "COUPON_CREATED", {"code": code, "kind": kind, "value": value})
        return self.db.query_one("SELECT * FROM coupons WHERE code = ?", (code,))

    def validate_coupon(self, code: str, at: datetime) -> dict:
        c = self.db.query_one("SELECT * FROM coupons WHERE code = ?", ((code or "").strip().upper(),))
        if not c or not c["active"]:
            raise ValidationError(f"Coupon '{code}' is not valid", code="INVALID_COUPON")
        if c["expires_at"] and parse_ts(c["expires_at"]) < at:
            raise ValidationError(f"Coupon '{code}' has expired", code="INVALID_COUPON")
        if c["max_uses"] is not None and c["used_count"] >= c["max_uses"]:
            raise ValidationError(f"Coupon '{code}' usage limit reached", code="INVALID_COUPON")
        return c

    def redeem_coupon(self, code: str) -> None:
        self.db.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = ?", (code.upper(),))

    # ---------------------------------------------------------------- fare
    def calculate(self, category: str, entry_time, exit_time, coupon_code: str | None = None) -> FareBreakdown:
        category = validate_category(category)
        entry, exit_ = parse_ts(entry_time), parse_ts(exit_time)
        if exit_ < entry:
            raise ValidationError("exit time is before entry time")
        minutes = math.ceil((exit_ - entry).total_seconds() / 60)
        zero = dict(surge_rule=None, surge_multiplier=1.0, surge_amount=0.0, discount=0.0,
                    taxable_amount=0.0, cgst=0.0, sgst=0.0, total=0.0)
        if minutes <= self.ctx.settings.grace_minutes:
            return FareBreakdown(category, entry.isoformat(), exit_.isoformat(), minutes, 0, True, 0.0,
                                 coupon_code=None, **zero)
        t = self.get_tariff(category)
        hours = math.ceil(minutes / 60)
        days, rem = divmod(hours, 24)
        base = Decimal(str(t["daily_cap"])) * days
        if rem:
            base += min(Decimal(str(t["first_hour"])) + Decimal(str(t["per_hour"])) * (rem - 1),
                        Decimal(str(t["daily_cap"])))
        rule = self.active_surge(exit_)
        mult = Decimal(str(rule["multiplier"])) if rule else Decimal("1")
        surge = base * (mult - 1)
        gross = base + surge
        discount = Decimal("0")
        coupon = None
        if coupon_code:
            c = self.validate_coupon(coupon_code, exit_)
            coupon = c["code"]
            discount = gross * Decimal(str(c["value"])) / 100 if c["kind"] == "PERCENT" else Decimal(str(c["value"]))
            discount = min(discount, gross)
        taxable = Decimal(str(_money(gross - discount)))
        half_rate = Decimal(str(self.ctx.settings.gst_rate_percent)) / 200
        cgst = Decimal(str(_money(taxable * half_rate)))
        sgst = cgst
        return FareBreakdown(
            category=category, entry_time=entry.isoformat(), exit_time=exit_.isoformat(),
            duration_minutes=minutes, billable_hours=hours, grace_applied=False,
            base_amount=_money(base), surge_rule=rule["name"] if rule else None, surge_multiplier=float(mult),
            surge_amount=_money(surge), coupon_code=coupon, discount=_money(discount),
            taxable_amount=float(taxable), cgst=float(cgst), sgst=float(sgst), total=_money(taxable + cgst + sgst),
        )


def get_tariff_engine(ctx) -> TariffEngine:
    return ctx.service("tariff", TariffEngine)


__all__ = ["TariffEngine", "FareBreakdown", "get_tariff_engine", "CATEGORIES"]
