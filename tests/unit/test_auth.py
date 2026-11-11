"""Unit tests - vps.auth (VPS-SR-003 RBAC + MFA). Owner: Angelo Arakal."""

import pytest

from vps.auth import AuthService, get_auth
from vps.errors import AuthError, Conflict, Forbidden, NotFound, ValidationError
from vps.security import totp

pytestmark = [pytest.mark.tc("TC-SEC-03"), pytest.mark.req("VPS-SR-003")]


def code(ctx, secret):
    return totp(secret, at=ctx.now().timestamp())


def test_default_accounts_seeded(ctx):
    users = {u["username"]: u["role"] for u in get_auth(ctx).list_users()}
    assert users == {"admin": "ADMIN", "manager": "MANAGER", "attendant": "ATTENDANT"}


def test_admin_requires_totp(ctx):
    with pytest.raises(AuthError) as e:
        get_auth(ctx).login("admin", ctx.settings.admin_password)
    assert e.value.code == "MFA_REQUIRED"


def test_admin_login_with_totp(ctx):
    s = ctx.settings
    out = get_auth(ctx).login("admin", s.admin_password, code(ctx, s.admin_totp_secret))
    assert out["role"] == "ADMIN" and len(out["token"]) > 30


def test_wrong_totp_rejected(ctx):
    with pytest.raises(AuthError):
        get_auth(ctx).login("admin", ctx.settings.admin_password, "000000")


def test_attendant_password_only(ctx):
    assert get_auth(ctx).login("attendant", ctx.settings.attendant_password)["role"] == "ATTENDANT"


def test_wrong_password_and_lockout(ctx):
    auth = get_auth(ctx)
    for _ in range(ctx.settings.max_failed_logins):
        with pytest.raises(AuthError):
            auth.login("attendant", "bad-password")
    with pytest.raises(AuthError) as e:
        auth.login("attendant", ctx.settings.attendant_password)
    assert e.value.code == "ACCOUNT_LOCKED"


def test_unknown_user(ctx):
    with pytest.raises(AuthError):
        get_auth(ctx).login("ghost", "whatever123")


def test_disabled_account(ctx):
    auth = get_auth(ctx)
    tok = auth.login("attendant", ctx.settings.attendant_password)["token"]
    auth.set_active("attendant", False, "admin")
    with pytest.raises(AuthError):
        auth.authenticate(tok)                      # sessions revoked
    with pytest.raises(AuthError) as e:
        auth.login("attendant", ctx.settings.attendant_password)
    assert e.value.code == "ACCOUNT_DISABLED"
    assert auth.set_active("attendant", True, "admin")["active"] == 1


def test_set_active_unknown(ctx):
    with pytest.raises(NotFound):
        get_auth(ctx).set_active("nobody", True, "admin")


def test_session_expiry(ctx, clock):
    auth = get_auth(ctx)
    tok = auth.login("attendant", ctx.settings.attendant_password)["token"]
    assert auth.authenticate(tok)["username"] == "attendant"
    clock.advance(hours=ctx.settings.session_hours, seconds=1)
    with pytest.raises(AuthError) as e:
        auth.authenticate(tok)
    assert e.value.code == "SESSION_EXPIRED"


def test_logout_and_missing_token(ctx):
    auth = get_auth(ctx)
    tok = auth.login("attendant", ctx.settings.attendant_password)["token"]
    auth.logout(tok)
    with pytest.raises(AuthError):
        auth.authenticate(tok)
    with pytest.raises(AuthError):
        auth.authenticate(None)


def test_create_user_rules(ctx):
    auth = get_auth(ctx)
    out = auth.create_user("ops1", "LongEnough#1", "ATTENDANT", actor="admin")
    assert out == {"username": "ops1", "role": "ATTENDANT", "mfa_required": False}
    admin2 = auth.create_user("boss2", "LongEnough#1", "ADMIN", actor="admin")
    assert admin2["mfa_required"] and len(admin2["totp_secret"]) >= 16   # shown once for enrolment
    with pytest.raises(Conflict):
        auth.create_user("ops1", "LongEnough#1", "ATTENDANT")
    with pytest.raises(ValidationError):
        auth.create_user("ops2", "LongEnough#1", "ROOT")
    with pytest.raises(ValidationError):
        auth.create_user("bad name", "LongEnough#1", "ATTENDANT")
    with pytest.raises(ValidationError):
        auth.create_user("ops3", "short", "ATTENDANT")
    with pytest.raises(NotFound):
        auth.get_user("ghost")


def test_authorize():
    assert AuthService.authorize({"role": "ADMIN"}, "ADMIN")
    with pytest.raises(Forbidden):
        AuthService.authorize({"role": "ATTENDANT"}, "ADMIN", "MANAGER")


@pytest.mark.tc("TC-SEC-02")
def test_secrets_not_stored_in_plaintext(ctx):
    get_auth(ctx)
    row = ctx.db.query_one("SELECT * FROM users WHERE username = 'admin'")
    assert row["pw_hash"].startswith("$argon2id$")
    assert ctx.settings.admin_totp_secret not in row["totp_secret_enc"]
    sess = ctx.db.query("SELECT token_hash FROM sessions")
    tok = get_auth(ctx).login("attendant", ctx.settings.attendant_password)["token"]
    assert tok not in [s["token_hash"] for s in sess + ctx.db.query("SELECT token_hash FROM sessions")]


def test_seed_runs_once(ctx):
    get_auth(ctx)
    AuthService(ctx)                       # second instance on the same DB must not re-seed
    assert ctx.db.scalar("SELECT COUNT(*) FROM users") == 3
