"""Report endpoints (VPS-F-018): JSON for dashboards, CSV/PDF for export."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from vps.api.deps import get_ctx, require
from vps.reports import get_reports

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{kind}")
def report(kind: str, period: str = "daily", format: str = "json", from_date: str | None = None,
           to_date: str | None = None, ctx=Depends(get_ctx), user=Depends(require("ADMIN", "MANAGER"))):
    svc = get_reports(ctx)
    if format == "json":
        return svc.build(kind, period, from_date, to_date)
    data, media, name, elapsed = svc.export(kind, period, format, from_date, to_date)
    return Response(data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{name}"', "X-Export-Time-ms": str(elapsed)})
