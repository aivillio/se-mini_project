"""FastAPI application factory.

Routers are discovered from ``vps/api``: any module exposing ``router`` is
mounted, and optional ``on_startup(app)`` / ``on_shutdown(app)`` hooks are run.
This lets each team member ship a feature as a self-contained module.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import vps.api
from vps import __version__
from vps.config import Settings
from vps.context import Context
from vps.errors import VPSError

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
log = logging.getLogger("vps")

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                               "frame-ancestors 'none'",
}


class SecurityMiddleware:
    """Pure-ASGI middleware (cheaper than BaseHTTPMiddleware on the hot path).

    * VPS-SR-001: refuses plain HTTP with 426 when TLS is mandatory (direct TLS or a TLS-terminating
      proxy that sets X-Forwarded-Proto: https). /health stays reachable for load-balancer probes.
    * Adds security headers and X-Response-Time-ms to every response.
    """

    def __init__(self, app, require_tls):
        self.app = app
        self.require_tls = require_tls
        self._headers = [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.require_tls() and scope.get("scheme") != "https" and scope["path"] != "/health":
            forwarded = dict(scope.get("headers") or []).get(b"x-forwarded-proto")
            if forwarded != b"https":
                resp = JSONResponse(status_code=426, headers={"Upgrade": "TLS/1.3"}, content={"error": {
                    "code": "TLS_REQUIRED", "message": "HTTPS (TLS 1.3) is required", "details": {}}})
                await resp(scope, receive, send)
                return
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k for k, _ in headers}
                headers += [(k, v) for k, v in self._headers if k not in present]
                headers.append((b"x-response-time-ms", f"{(time.perf_counter() - start) * 1000:.2f}".encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def discover_api_modules() -> list:
    modules = []
    for info in sorted(pkgutil.iter_modules(vps.api.__path__), key=lambda m: m.name):
        if info.name.startswith("_") or info.name == "deps":
            continue
        mod = importlib.import_module(f"vps.api.{info.name}")
        if hasattr(mod, "router"):
            modules.append(mod)
    return modules


def create_app(settings: Settings | None = None, ctx: Context | None = None) -> FastAPI:
    ctx = ctx or Context(settings)
    modules = discover_api_modules()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for mod in modules:
            if hasattr(mod, "on_startup"):
                mod.on_startup(app)
        yield
        for mod in modules:
            if hasattr(mod, "on_shutdown"):
                mod.on_shutdown(app)

    app = FastAPI(title="Vehicle Parking System API", version=__version__, lifespan=lifespan,
                  description="SE Mini Project - Group 6. Implements SRS v1.0 / SAD v1.0.")
    app.state.ctx = ctx

    @app.exception_handler(VPSError)
    async def _vps_error(request: Request, exc: VPSError):
        if exc.status >= 500:
            log.warning("%s %s -> %s %s", request.method, request.url.path, exc.code, exc.message)
        return JSONResponse(status_code=exc.status, content=exc.to_dict())

    app.add_middleware(SecurityMiddleware, require_tls=lambda: ctx.settings.require_tls)

    @app.get("/health", tags=["system"])
    def health():
        ok = ctx.db.scalar("SELECT 1") == 1
        return {"status": "ok" if ok else "degraded", "version": __version__,
                "modules": [m.__name__.rsplit(".", 1)[-1] for m in modules]}

    for mod in modules:
        app.include_router(mod.router)

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/ui/index.html")

    if WEB_DIR.exists():
        app.mount("/ui", StaticFiles(directory=WEB_DIR, html=True), name="ui")
    return app
