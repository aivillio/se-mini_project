"""Admin console endpoints (VPS-F-017, VPS-SR-005).

Tariffs, surge rules, coupons, zone/slot layout, manual barrier overrides and the
audit trail. Every mutating call is RBAC-guarded and written to the audit log.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from vps.allocation import get_allocation
from vps.api.deps import get_ctx, require
from vps.audit import get_audit
from vps.errors import ValidationError
from vps.hardware import get_hardware
from vps.sensors import get_sensor_hub
from vps.tariff import get_tariff_engine

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ADMIN = require("ADMIN")
STAFF = require("ADMIN", "MANAGER")


class TariffIn(BaseModel):
    first_hour: float = Field(..., ge=0)
    per_hour: float = Field(..., ge=0)
    daily_cap: float = Field(..., ge=0)


class SurgeIn(BaseModel):
    name: str
    start_hour: int
    end_hour: int
    multiplier: float


class ActiveIn(BaseModel):
    active: bool


class CouponIn(BaseModel):
    code: str
    kind: str = "PERCENT"
    value: float
    max_uses: int | None = None
    expires_at: str | None = None


class SlotsIn(BaseModel):
    level: int
    category: str
    count: int


class SlotStatusIn(BaseModel):
    status: str


class OverrideIn(BaseModel):
    lane_id: str
    action: str = "RAISE"
    reason: str = Field(..., min_length=5)


# ------------------------------------------------------------------ tariffs
@router.get("/tariffs")
def tariffs(ctx=Depends(get_ctx), user=Depends(STAFF)):
    return get_tariff_engine(ctx).get_tariffs()


@router.put("/tariffs/{category}")
def update_tariff(category: str, body: TariffIn, ctx=Depends(get_ctx), user=Depends(ADMIN)):
    return get_tariff_engine(ctx).update_tariff(category, body.first_hour, body.per_hour, body.daily_cap,
                                                user["username"])


@router.get("/surge")
def surge(ctx=Depends(get_ctx), user=Depends(STAFF)):
    return get_tariff_engine(ctx).surge_rules()


@router.post("/surge", status_code=201)
def add_surge(body: SurgeIn, ctx=Depends(get_ctx), user=Depends(ADMIN)):
    return get_tariff_engine(ctx).add_surge_rule(body.name, body.start_hour, body.end_hour, body.multiplier,
                                                 user["username"])


@router.patch("/surge/{rule_id}")
def toggle_surge(rule_id: int, body: ActiveIn, ctx=Depends(get_ctx), user=Depends(ADMIN)):
    return get_tariff_engine(ctx).set_surge_active(rule_id, body.active, user["username"])


@router.get("/coupons")
def coupons(ctx=Depends(get_ctx), user=Depends(STAFF)):
    return get_tariff_engine(ctx).coupons()


@router.post("/coupons", status_code=201)
def add_coupon(body: CouponIn, ctx=Depends(get_ctx), user=Depends(ADMIN)):
    return get_tariff_engine(ctx).create_coupon(body.code, body.kind, body.value, user["username"],
                                                max_uses=body.max_uses, expires_at=body.expires_at)


# ------------------------------------------------------------------ layout
@router.post("/slots", status_code=201)
def add_slots(body: SlotsIn, ctx=Depends(get_ctx), user=Depends(ADMIN)):
    ids = get_allocation(ctx).add_slots(body.level, body.category, body.count)
    get_sensor_hub(ctx).refresh_vms()
    get_audit(ctx).record(user["username"], "SLOTS_ADDED", {"level": body.level, "category": body.category,
                                                            "count": body.count})
    return {"created": ids}


@router.patch("/slots/{slot_id}")
def set_slot_status(slot_id: str, body: SlotStatusIn, ctx=Depends(get_ctx), user=Depends(ADMIN)):
    if body.status not in ("VACANT", "DISABLED"):
        raise ValidationError("admins may only set VACANT or DISABLED")
    slot = get_allocation(ctx).set_status(slot_id, body.status)
    get_sensor_hub(ctx).refresh_vms()
    get_audit(ctx).record(user["username"], "SLOT_STATUS_SET", {"slot": slot_id, "status": body.status})
    return slot


# ------------------------------------------------------------------ manual override (audited)
@router.post("/barrier-override")
def barrier_override(body: OverrideIn, ctx=Depends(get_ctx), user=Depends(require("ATTENDANT", "ADMIN"))):
    lane = get_hardware(ctx).get(body.lane_id)
    action = body.action.upper()
    if action == "RAISE":
        result = lane.barrier.raise_barrier()
    elif action == "LOWER":
        result = lane.barrier.lower_barrier()
    else:
        raise ValidationError("action must be RAISE or LOWER")
    entry = get_audit(ctx).record(user["username"], "BARRIER_OVERRIDE",
                                  {"lane": body.lane_id, "action": action, "reason": body.reason})
    return {**lane.snapshot(), **result, "audit_id": entry["id"]}


# ------------------------------------------------------------------ audit trail
@router.get("/audit")
def audit(limit: int = 100, action: str | None = None, ctx=Depends(get_ctx), user=Depends(STAFF)):
    return get_audit(ctx).entries(min(limit, 1000), action)


@router.get("/audit/verify")
def audit_verify(ctx=Depends(get_ctx), user=Depends(STAFF)):
    return get_audit(ctx).verify()
