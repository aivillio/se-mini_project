"""Auth & user-management endpoints (VPS-SR-003, VPS-F-017 attendant credentials)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from vps.api.deps import bearer_token, current_user, get_ctx, require
from vps.auth import get_auth

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str
    totp: str | None = Field(default=None, description="6-digit code; required for ADMIN/MANAGER")


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "ATTENDANT"


class ActiveIn(BaseModel):
    active: bool


@router.post("/login")
def login(body: LoginIn, ctx=Depends(get_ctx)):
    return get_auth(ctx).login(body.username, body.password, body.totp)


@router.post("/logout")
def logout(request: Request, ctx=Depends(get_ctx), user=Depends(current_user)):
    get_auth(ctx).logout(bearer_token(request))
    return {"status": "logged_out"}


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.get("/users")
def list_users(ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    return get_auth(ctx).list_users()


@router.post("/users", status_code=201)
def create_user(body: UserIn, ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    return get_auth(ctx).create_user(body.username, body.password, body.role, actor=user["username"])


@router.patch("/users/{username}")
def set_active(username: str, body: ActiveIn, ctx=Depends(get_ctx), user=Depends(require("ADMIN"))):
    return get_auth(ctx).set_active(username, body.active, actor=user["username"])
