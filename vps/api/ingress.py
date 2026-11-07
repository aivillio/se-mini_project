"""Ingress & lane endpoints (SAD 4.3: POST /api/v1/ingress/ticket)."""

from __future__ import annotations

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from vps.api.deps import get_ctx, require
from vps.audit import get_audit
from vps.errors import NotFound
from vps.hardware import get_hardware
from vps.ingress import get_ingress

router = APIRouter(prefix="/api/v1", tags=["ingress"])


class TicketIn(BaseModel):
    plate_number: str = Field(..., examples=["KA01AB1234"])
    vehicle_category: str = Field(..., examples=["4W"])
    timestamp: str | None = Field(default=None, description="ISO-8601 event time from the edge controller")
    lane_id: str = "ENTRY-1"
    confidence: float = Field(default=0.97, ge=0, le=1, description="ANPR OCR confidence (simulation)")
    reservation_code: str | None = None


class ManualTicketIn(BaseModel):
    plate_number: str
    vehicle_category: str
    lane_id: str = "ENTRY-1"


class LoopIn(BaseModel):
    occupied: bool


class ControllerIn(BaseModel):
    online: bool


@router.post("/ingress/ticket", status_code=201)
def issue_ticket(body: TicketIn, ctx=Depends(get_ctx)):
    return get_ingress(ctx).process_entry(
        body.lane_id, body.plate_number, body.vehicle_category, confidence=body.confidence,
        timestamp=body.timestamp, reservation_code=body.reservation_code)


@router.post("/ingress/manual", status_code=201)
def manual_ticket(body: ManualTicketIn, ctx=Depends(get_ctx), user=Depends(require("ATTENDANT", "ADMIN"))):
    """Attendant path for unreadable plates (SRS 2.3)."""
    return get_ingress(ctx).process_entry(body.lane_id, body.plate_number, body.vehicle_category,
                                          attendant=user["username"])


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, ctx=Depends(get_ctx)):
    svc = get_ingress(ctx)
    return svc.public_view(svc.get_ticket(ticket_id))


@router.get("/tickets/{ticket_id}/qr.svg")
def ticket_qr(ticket_id: str, ctx=Depends(get_ctx)):
    ticket = get_ingress(ctx).get_ticket(ticket_id)
    return _svg(ticket["qr_payload"])


@router.get("/qr.svg")
def any_qr(data: str = Query(..., max_length=512)):
    return _svg(data)


def _svg(data: str) -> Response:
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    return Response(content=img.to_string(), media_type="image/svg+xml")


# ------------------------------------------------------------------ lanes (VPS-F-003/004)
@router.get("/lanes")
def lanes(ctx=Depends(get_ctx)):
    return get_hardware(ctx).snapshot()


@router.post("/lanes/{lane_id}/loop")
def loop_event(lane_id: str, body: LoopIn, ctx=Depends(get_ctx)):
    lane = get_hardware(ctx).get(lane_id)
    result = lane.vehicle_on_loop(body.occupied)
    return {**lane.snapshot(), **result}


@router.post("/lanes/{lane_id}/barrier/lower")
def lower_barrier(lane_id: str, ctx=Depends(get_ctx)):
    lane = get_hardware(ctx).get(lane_id)
    return {**lane.snapshot(), **lane.barrier.lower_barrier()}


@router.post("/lanes/{lane_id}/controller")
def set_controller(lane_id: str, body: ControllerIn, ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    """Maintenance: take a lane's edge controller offline/online."""
    lane = get_hardware(ctx).lanes.get(lane_id)
    if lane is None:
        raise NotFound(f"Unknown lane '{lane_id}'")
    lane.controller_online = body.online
    get_audit(ctx).record(user["username"], "LANE_CONTROLLER_SET", {"lane": lane_id, "online": body.online})
    return lane.snapshot()
