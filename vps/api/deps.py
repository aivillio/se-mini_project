"""Shared FastAPI dependencies: context access, authentication and RBAC guards."""

from __future__ import annotations

from fastapi import Depends, Request

from vps.auth import AuthService, get_auth
from vps.context import Context


def get_ctx(request: Request) -> Context:
    return request.app.state.ctx


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def current_user(request: Request, ctx: Context = Depends(get_ctx)) -> dict:
    return get_auth(ctx).authenticate(bearer_token(request))


def require(*roles: str):
    """Dependency factory: ``Depends(require("ADMIN"))`` -> 401 if anonymous, 403 if wrong role."""

    def _guard(user: dict = Depends(current_user)) -> dict:
        return AuthService.authorize(user, *roles)

    return _guard
