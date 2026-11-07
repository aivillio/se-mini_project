"""Authentication & RBAC (VPS-SR-003, VPS-SR-002).

* Roles: ADMIN (configuration), MANAGER (reports/audit), ATTENDANT (lane ops).
* ADMIN and MANAGER are administrative accounts -> password + TOTP required.
* Passwords are Argon2id hashes; TOTP secrets are AES-256-GCM encrypted at rest.
* Accounts lock after ``max_failed_logins`` consecutive failures.
* Session tokens are random 256-bit values; only their SHA-256 is stored.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from vps.audit import get_audit
from vps.context import parse_ts
from vps.errors import AuthError, Conflict, Forbidden, NotFound, ValidationError
from vps.security import get_vault, hash_password, new_totp_secret, token_hash, verify_password, verify_totp

ROLES = ("ADMIN", "MANAGER", "ATTENDANT")
MFA_ROLES = ("ADMIN", "MANAGER")


class AuthService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.vault = get_vault(ctx)
        self.audit = get_audit(ctx)
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        s = self.ctx.settings
        if self.db.scalar("SELECT COUNT(*) FROM users"):
            return
        self.create_user("admin", s.admin_password, "ADMIN", totp_secret=s.admin_totp_secret, actor="system")
        self.create_user("manager", s.manager_password, "MANAGER", totp_secret=s.manager_totp_secret, actor="system")
        self.create_user("attendant", s.attendant_password, "ATTENDANT", actor="system")

    # ---------------------------------------------------------------- users
    def create_user(self, username: str, password: str, role: str, *, totp_secret: str | None = None,
                    actor: str = "system") -> dict:
        if role not in ROLES:
            raise ValidationError(f"role must be one of {ROLES}")
        if not username or not username.isalnum():
            raise ValidationError("username must be alphanumeric")
        if self.db.query_one("SELECT 1 FROM users WHERE username = ?", (username,)):
            raise Conflict(f"User {username} already exists")
        try:
            pw_hash = hash_password(password)
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
        secret = totp_secret or (new_totp_secret() if role in MFA_ROLES else None)
        self.db.execute(
            "INSERT INTO users (username, pw_hash, role, totp_secret_enc, created_at) VALUES (?,?,?,?,?)",
            (username, pw_hash, role, self.vault.encrypt(secret) if secret else None, self.ctx.now_iso()),
        )
        self.audit.record(actor, "USER_CREATED", {"username": username, "role": role})
        out = {"username": username, "role": role, "mfa_required": role in MFA_ROLES}
        if secret and not totp_secret:
            out["totp_secret"] = secret   # shown once for enrolment in an authenticator app
        return out

    def set_active(self, username: str, active: bool, actor: str) -> dict:
        cur = self.db.execute("UPDATE users SET active = ?, failed_logins = 0 WHERE username = ?",
                              (1 if active else 0, username))
        if cur.rowcount == 0:
            raise NotFound(f"User {username} not found")
        if not active:
            self.db.execute("DELETE FROM sessions WHERE username = ?", (username,))
        self.audit.record(actor, "USER_ENABLED" if active else "USER_DISABLED", {"username": username})
        return self.get_user(username)

    def get_user(self, username: str) -> dict:
        u = self.db.query_one("SELECT username, role, active, failed_logins, created_at FROM users WHERE username = ?",
                              (username,))
        if not u:
            raise NotFound(f"User {username} not found")
        return u

    def list_users(self) -> list[dict]:
        return self.db.query("SELECT username, role, active, failed_logins, created_at FROM users ORDER BY username")

    # ---------------------------------------------------------------- sessions
    def login(self, username: str, password: str, totp_code: str | None = None) -> dict:
        user = self.db.query_one("SELECT * FROM users WHERE username = ?", (username,))
        generic = AuthError("Invalid credentials")
        if not user:
            raise generic
        if not user["active"]:
            raise AuthError("Account disabled", code="ACCOUNT_DISABLED")
        if user["failed_logins"] >= self.ctx.settings.max_failed_logins:
            raise AuthError("Account locked after repeated failures", code="ACCOUNT_LOCKED")
        ok = verify_password(user["pw_hash"], password)
        if ok and user["role"] in MFA_ROLES:
            if not totp_code:
                raise AuthError("TOTP code required for administrative accounts", code="MFA_REQUIRED")
            secret = self.vault.decrypt(user["totp_secret_enc"])
            ok = verify_totp(secret, totp_code, at=self.ctx.now().timestamp())
        if not ok:
            self.db.execute("UPDATE users SET failed_logins = failed_logins + 1 WHERE username = ?", (username,))
            self.audit.record(username, "LOGIN_FAILED", {})
            raise generic
        self.db.execute("UPDATE users SET failed_logins = 0 WHERE username = ?", (username,))
        token = secrets.token_urlsafe(32)
        now = self.ctx.now()
        expires = now + timedelta(hours=self.ctx.settings.session_hours)
        self.db.execute("INSERT INTO sessions (token_hash, username, role, created_at, expires_at) VALUES (?,?,?,?,?)",
                        (token_hash(token), username, user["role"], now.isoformat(), expires.isoformat()))
        self.audit.record(username, "LOGIN", {"role": user["role"]})
        return {"token": token, "username": username, "role": user["role"], "expires_at": expires.isoformat()}

    def authenticate(self, token: str | None) -> dict:
        if not token:
            raise AuthError("Missing bearer token")
        s = self.db.query_one("SELECT * FROM sessions WHERE token_hash = ?", (token_hash(token),))
        if not s or parse_ts(s["expires_at"]) <= self.ctx.now():
            raise AuthError("Session invalid or expired", code="SESSION_EXPIRED")
        return {"username": s["username"], "role": s["role"]}

    def logout(self, token: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))

    @staticmethod
    def authorize(user: dict, *roles: str) -> dict:
        if roles and user["role"] not in roles:
            raise Forbidden(f"Role {user['role']} is not permitted for this action", details={"allowed": roles})
        return user


def get_auth(ctx) -> AuthService:
    return ctx.service("auth", AuthService)
