"""Reservation endpoints (VPS-F-015, VPS-F-016) + scheduler lifecycle hook."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from vps.api.deps import get_ctx, require
from vps.reservation import get_reservations
from vps.scheduler import Scheduler

router = APIRouter(prefix="/api/v1/reservations", tags=["reservations"])


class ReservationIn(BaseModel):
    plate_number: str
    vehicle_category: str
    start_time: str = Field(..., description="ISO-8601, within the next 48 hours")
    duration_hours: int = Field(default=2, ge=1, le=24)
    contact: str | None = None


class CancelIn(BaseModel):
    plate_number: str


@router.post("", status_code=201)
def create(body: ReservationIn, ctx=Depends(get_ctx)):
    return get_reservations(ctx).create(body.plate_number, body.vehicle_category, body.start_time,
                                        body.duration_hours, body.contact)


@router.get("")
def list_all(status: str | None = None, ctx=Depends(get_ctx), user=Depends(require("ADMIN", "MANAGER", "ATTENDANT"))):
    return get_reservations(ctx).list(status)


@router.post("/release-no-shows")
def release(ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    return {"released": get_reservations(ctx).release_no_shows()}


@router.get("/{code}")
def get_one(code: str, ctx=Depends(get_ctx)):
    return get_reservations(ctx).get(code)


@router.post("/{code}/cancel")
def cancel(code: str, body: CancelIn, ctx=Depends(get_ctx)):
    return get_reservations(ctx).cancel(code, body.plate_number)


def on_startup(app) -> None:
    app.state.scheduler = Scheduler(app.state.ctx)
    app.state.scheduler.start()


def on_shutdown(app) -> None:
    app.state.scheduler.stop()
