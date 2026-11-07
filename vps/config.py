"""Runtime configuration (12-factor style: everything can be overridden by env vars)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

_DEV_SECRET = "vps-dev-only-secret-change-in-production"


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _derive(label: str, secret: str) -> str:
    """Derive a 256-bit hex key from a master secret (dev convenience only)."""
    return hashlib.sha256(f"{label}:{secret}".encode()).hexdigest()


@dataclass
class Settings:
    env: str = "development"
    db_path: str = "vps.db"
    edge_db_path: str = "vps_edge.db"
    timezone: str = "Asia/Kolkata"

    # --- security (VPS-SR-001..005) ---
    ticket_hmac_key: str = field(default_factory=lambda: _derive("ticket", _DEV_SECRET))
    pii_aes_key: str = field(default_factory=lambda: _derive("pii", _DEV_SECRET))
    payment_webhook_secret: str = field(default_factory=lambda: _derive("webhook", _DEV_SECRET))
    require_tls: bool = False
    session_hours: int = 8
    max_failed_logins: int = 5

    # seeded accounts (dev defaults; override with env in any shared deployment)
    admin_password: str = "Admin@123"
    manager_password: str = "Manager@123"
    attendant_password: str = "Attendant@123"
    admin_totp_secret: str = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
    manager_totp_secret: str = "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU"

    # --- business rules from the SRS ---
    grace_minutes: int = 15                 # VPS-F-009
    reservation_window_hours: int = 48      # VPS-F-015
    no_show_minutes: int = 30               # VPS-F-016
    gst_rate_percent: float = 18.0          # VPS-F-014 (CGST 9% + SGST 9%)
    edge_queue_max_hours: int = 72          # VPS-NF-005
    max_entry_backdate_hours: int = 72      # edge controllers may replay up to 72h old events
    facility_name: str = "VPS Smart Parking - PES EC Campus"
    facility_gstin: str = "29AABCV1234F1Z5"
    scheduler_interval_seconds: int = 60
    lane_pairs: int = 2                     # ENTRY-n / EXIT-n gate lanes (NF-003 sizing: 25 pairs = 50 lanes)
    seed_default_layout: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        s.env = _env("VPS_ENV", s.env)
        s.db_path = _env("VPS_DB_PATH", s.db_path)
        s.edge_db_path = _env("VPS_EDGE_DB_PATH", s.edge_db_path)
        s.require_tls = _env("VPS_REQUIRE_TLS", "0") == "1"
        s.lane_pairs = int(_env("VPS_LANE_PAIRS", str(s.lane_pairs)))
        master = os.getenv("VPS_MASTER_SECRET")
        if master:
            s.ticket_hmac_key = _derive("ticket", master)
            s.pii_aes_key = _derive("pii", master)
            s.payment_webhook_secret = _derive("webhook", master)
        s.ticket_hmac_key = _env("VPS_TICKET_HMAC_KEY", s.ticket_hmac_key)
        s.pii_aes_key = _env("VPS_PII_AES_KEY", s.pii_aes_key)
        s.payment_webhook_secret = _env("VPS_WEBHOOK_SECRET", s.payment_webhook_secret)
        s.admin_password = _env("VPS_ADMIN_PASSWORD", s.admin_password)
        s.manager_password = _env("VPS_MANAGER_PASSWORD", s.manager_password)
        s.attendant_password = _env("VPS_ATTENDANT_PASSWORD", s.attendant_password)
        s.admin_totp_secret = _env("VPS_ADMIN_TOTP_SECRET", s.admin_totp_secret)
        s.manager_totp_secret = _env("VPS_MANAGER_TOTP_SECRET", s.manager_totp_secret)
        if s.env == "production" and not master:
            raise RuntimeError("VPS_MASTER_SECRET must be set when VPS_ENV=production")
        return s
