"""Slot, sensor, signage and alert endpoints (VPS-F-005..007)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vps.alerts import get_alerts
from vps.allocation import get_allocation
from vps.api.deps import get_ctx, require
from vps.sensors import get_sensor_hub

router = APIRouter(prefix="/api/v1", tags=["slots & sensors"])


class SensorEvent(BaseModel):
    occupied: bool
    seq: int | None = None


@router.get("/slots")
def list_slots(level: int | None = None, ctx=Depends(get_ctx)):
    hub = get_sensor_hub(ctx)
    leds = hub.led_states()
    return [{**s, "led": leds[s["id"]]} for s in get_allocation(ctx).list(level)]


@router.get("/slots/summary")
def summary(ctx=Depends(get_ctx)):
    return get_allocation(ctx).summary()


@router.get("/slots/nearest/{category}")
def nearest(category: str, ctx=Depends(get_ctx)):
    return {"slot": get_allocation(ctx).find_nearest_vacant(category)}


@router.post("/sensors/{slot_id}/event")
def sensor_event(slot_id: str, body: SensorEvent, ctx=Depends(get_ctx)):
    return get_sensor_hub(ctx).handle_event(slot_id, body.occupied, body.seq)


@router.get("/vms")
def vms(ctx=Depends(get_ctx)):
    return get_sensor_hub(ctx).vms_boards()


# ------------------------------------------------------------------ alerts (attendant screen)
@router.get("/alerts")
def alerts(open_only: bool = True, ctx=Depends(get_ctx), user=Depends(require("ATTENDANT", "ADMIN", "MANAGER"))):
    return get_alerts(ctx).list(open_only)


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: int, ctx=Depends(get_ctx), user=Depends(require("ATTENDANT", "ADMIN"))):
    return get_alerts(ctx).acknowledge(alert_id, user["username"])
