"""Unit tests - tariff engine (VPS-F-008, F-009, F-010, F-017). Owner: Akarsh Parashuram."""

from datetime import datetime, timedelta, timezone

import pytest

from vps.errors import NotFound, ValidationError
from vps.tariff import get_tariff_engine

T = datetime(2026, 10, 20, 5, 0, tzinfo=timezone.utc)       # 10:30 IST, no surge


def fare(ctx, minutes, cat="4W", coupon=None, start=T):
    return get_tariff_engine(ctx).calculate(cat, start, start + timedelta(minutes=minutes), coupon)


@pytest.mark.tc("TC-BILL-02")
@pytest.mark.req("VPS-F-009")
@pytest.mark.parametrize("minutes,expected", [(0, 0.0), (1, 0.0), (15, 0.0), (16, 47.2)])
def test_grace_period_boundary(ctx, minutes, expected):
    f = fare(ctx, minutes)
    assert f.total == expected
    assert f.grace_applied is (minutes <= 15)


@pytest.mark.tc("TC-BILL-01")
@pytest.mark.req("VPS-F-008")
@pytest.mark.parametrize("cat,minutes,base", [
    ("4W", 60, 40.0), ("4W", 61, 70.0), ("4W", 180, 100.0), ("4W", 24 * 60, 400.0),   # capped at daily max
    ("2W", 120, 30.0), ("EV", 150, 90.0), ("HANDICAP", 600, 110.0), ("HANDICAP", 900, 120.0),
    ("4W", 26 * 60, 470.0),                                                             # 1 day + 2 h
])
def test_tiered_rates_and_daily_cap(ctx, cat, minutes, base):
    f = fare(ctx, minutes, cat)
    assert f.base_amount == base
    assert f.cgst == f.sgst == round(base * 0.09, 2)
    assert f.total == round(base * 1.18, 2)


@pytest.mark.tc("TC-BILL-01")
def test_exit_before_entry(ctx):
    with pytest.raises(ValidationError):
        get_tariff_engine(ctx).calculate("4W", T, T - timedelta(minutes=1))


@pytest.mark.tc("TC-BILL-03")
@pytest.mark.req("VPS-F-010")
class TestSurgeAndCoupons:
    def test_surge_in_peak_window(self, ctx):
        peak_exit = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)          # 18:00 IST
        f = get_tariff_engine(ctx).calculate("4W", peak_exit - timedelta(hours=2), peak_exit)
        assert f.surge_rule == "Evening peak" and f.surge_multiplier == 1.25
        assert f.base_amount == 70.0 and f.surge_amount == 17.5 and f.taxable_amount == 87.5

    def test_no_surge_outside_window(self, ctx):
        assert fare(ctx, 120).surge_amount == 0.0

    def test_percent_coupon(self, ctx):
        f = fare(ctx, 180, coupon="welcome10")
        assert f.coupon_code == "WELCOME10" and f.discount == 10.0 and f.taxable_amount == 90.0

    def test_flat_coupon_never_negative(self, ctx):
        assert fare(ctx, 60, cat="2W", coupon="FLAT50").taxable_amount == 0.0

    def test_invalid_expired_exhausted(self, ctx):
        eng = get_tariff_engine(ctx)
        with pytest.raises(ValidationError):
            fare(ctx, 60, coupon="NOPE")
        eng.create_coupon("OLD5", "FLAT", 5, "admin", expires_at=(T - timedelta(days=1)).isoformat())
        with pytest.raises(ValidationError, match="expired"):
            fare(ctx, 60, coupon="OLD5")
        eng.create_coupon("ONCE", "PERCENT", 50, "admin", max_uses=1)
        eng.redeem_coupon("ONCE")
        with pytest.raises(ValidationError, match="limit"):
            fare(ctx, 60, coupon="ONCE")

    def test_coupon_creation_rules(self, ctx):
        eng = get_tariff_engine(ctx)
        assert eng.create_coupon("diwali20", "PERCENT", 20, "admin")["code"] == "DIWALI20"
        for bad in [("BAD CODE", "FLAT", 5), ("X1", "PERCENT", 150), ("X2", "BOGO", 1), ("X3", "FLAT", 0)]:
            with pytest.raises(ValidationError):
                eng.create_coupon(*bad, actor="admin")
        with pytest.raises(ValidationError):
            eng.create_coupon("DIWALI20", "FLAT", 5, "admin")
        assert {c["code"] for c in eng.coupons()} >= {"WELCOME10", "FLAT50", "DIWALI20"}

    def test_surge_rule_management(self, ctx):
        eng = get_tariff_engine(ctx)
        rule = eng.add_surge_rule("Morning", 4, 6, 1.5, "admin")                   # 04-06 IST
        early = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)                  # 04:30 IST
        assert eng.calculate("4W", early - timedelta(hours=1), early).surge_multiplier == 1.5
        eng.set_surge_active(rule["id"], False, "admin")
        assert eng.calculate("4W", early - timedelta(hours=1), early).surge_multiplier == 1.0
        with pytest.raises(NotFound):
            eng.set_surge_active(999, True, "admin")
        with pytest.raises(ValidationError):
            eng.add_surge_rule("bad", 10, 9, 1.2, "admin")
        with pytest.raises(ValidationError):
            eng.add_surge_rule("bad", 1, 2, 5.0, "admin")


@pytest.mark.tc("TC-ADM-01")
@pytest.mark.req("VPS-F-017")
def test_tariff_update_takes_effect_without_restart(ctx):
    eng = get_tariff_engine(ctx)
    assert fare(ctx, 60).base_amount == 40.0
    eng.update_tariff("4W", 50, 30, 400, "admin")
    assert fare(ctx, 60).base_amount == 50.0
    entry = ctx.db.query_one("SELECT * FROM audit_log WHERE action = 'TARIFF_UPDATED'")
    assert entry["actor"] == "admin" and '"first_hour":40.0' in entry["details"]
    with pytest.raises(ValidationError):
        eng.update_tariff("4W", -1, 30, 400, "admin")
    with pytest.raises(ValidationError):
        eng.update_tariff("4W", 100, 30, 50, "admin")
    assert len(eng.get_tariffs()) == 4


def test_seed_runs_once(ctx):
    from vps.tariff import TariffEngine
    get_tariff_engine(ctx)
    TariffEngine(ctx)
    assert ctx.db.scalar("SELECT COUNT(*) FROM surge_rules") == 1
