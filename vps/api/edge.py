"""Edge gate-controller endpoints (VPS-NF-005): queue status, WAN simulation, manual sync."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vps.api.deps import get_ctx, require
from vps.edge_queue import get_edge

router = APIRouter(prefix="/api/v1", tags=["edge controller"])


class NetworkIn(BaseModel):
    online: bool


@router.get("/edge/status")
def edge_status(ctx=Depends(get_ctx)):
    return get_edge(ctx).status()


@router.post("/edge/network")
def edge_network(body: NetworkIn, ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    """Simulate WAN loss / restoration for resilience testing."""
    return get_edge(ctx).set_online(body.online)


@router.post("/edge/sync")
def edge_sync(ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    return get_edge(ctx).flush()
