"""Persistence layer.

The SAD specifies PostgreSQL centrally and SQLite on the edge controllers. For the
mini-project build we run SQLite for both (see docs/Deviations.md, DEV-01); all SQL
is plain ANSI so it ports to PostgreSQL with minimal changes.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS slots (
    id          TEXT PRIMARY KEY,
    level       INTEGER NOT NULL,
    zone        TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN ('2W','4W','EV','HANDICAP')),
    distance    INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'VACANT'
                CHECK (status IN ('VACANT','ALLOCATED','OCCUPIED','RESERVED','DISABLED')),
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_slots_alloc ON slots (category, status, level, distance);

CREATE TABLE IF NOT EXISTS tickets (
    id              TEXT PRIMARY KEY,
    plate_enc       TEXT NOT NULL,           -- AES-256-GCM ciphertext (VPS-SR-002)
    plate_fp        TEXT NOT NULL,           -- keyed fingerprint for lookups
    category        TEXT NOT NULL,
    slot_id         TEXT NOT NULL REFERENCES slots(id),
    entry_lane      TEXT NOT NULL,
    entry_time      TEXT NOT NULL,
    exit_time       TEXT,
    exit_lane       TEXT,
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','PAID','CLOSED')),
    qr_payload      TEXT NOT NULL,
    reservation_id  TEXT,
    amount          REAL,
    entry_mode      TEXT NOT NULL DEFAULT 'ANPR',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tickets_plate ON tickets (plate_fp, status);

CREATE TABLE IF NOT EXISTS payments (
    id           TEXT PRIMARY KEY,
    ticket_id    TEXT NOT NULL REFERENCES tickets(id),
    amount       REAL NOT NULL,
    method       TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('CREATED','CAPTURED','FAILED')),
    gateway_ref  TEXT,
    card_last4   TEXT,                       -- never the PAN (VPS-NF-004)
    coupon_code  TEXT,
    fare_json    TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_payments_ticket ON payments (ticket_id);

CREATE TABLE IF NOT EXISTS tariffs (
    category    TEXT PRIMARY KEY,
    first_hour  REAL NOT NULL,
    per_hour    REAL NOT NULL,
    daily_cap   REAL NOT NULL,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS surge_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    start_hour  INTEGER NOT NULL CHECK (start_hour BETWEEN 0 AND 23),
    end_hour    INTEGER NOT NULL CHECK (end_hour BETWEEN 1 AND 24),
    multiplier  REAL NOT NULL CHECK (multiplier >= 1.0),
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS coupons (
    code        TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('PERCENT','FLAT')),
    value       REAL NOT NULL CHECK (value > 0),
    max_uses    INTEGER,
    used_count  INTEGER NOT NULL DEFAULT 0,
    expires_at  TEXT,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reservations (
    id          TEXT PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    plate_enc   TEXT NOT NULL,
    plate_fp    TEXT NOT NULL,
    category    TEXT NOT NULL,
    slot_id     TEXT NOT NULL REFERENCES slots(id),
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('BOOKED','CHECKED_IN','CANCELLED','EXPIRED')),
    contact_enc TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_res_status ON reservations (status, start_time);

CREATE TABLE IF NOT EXISTS users (
    username        TEXT PRIMARY KEY,
    pw_hash         TEXT NOT NULL,           -- Argon2id (VPS-SR-002)
    role            TEXT NOT NULL CHECK (role IN ('ADMIN','MANAGER','ATTENDANT')),
    totp_secret_enc TEXT,                    -- encrypted at rest
    active          INTEGER NOT NULL DEFAULT 1,
    failed_logins   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES users(username),
    role        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    details     TEXT NOT NULL,
    retain_until TEXT NOT NULL,
    prev_hash   TEXT NOT NULL,
    hash        TEXT NOT NULL
);
-- write-once audit log (VPS-SR-005): the database itself refuses edits/deletes
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is write-once'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is write-once'); END;

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    kind        TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','CRITICAL')),
    lane_id     TEXT,
    message     TEXT NOT NULL,
    acked_by    TEXT,
    acked_at    TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    channel     TEXT NOT NULL CHECK (channel IN ('SMS','EMAIL','PRINT')),
    recipient   TEXT,
    body        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS central_events (
    event_id    TEXT PRIMARY KEY,            -- idempotency key from the edge queue
    lane_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL
);
"""

EDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS edge_queue (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL UNIQUE,
    lane_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    synced_at   TEXT
);
"""


class Database:
    """Thread-safe thin wrapper over sqlite3 (autocommit + explicit transactions)."""

    def __init__(self, path: str = ":memory:", schema: str = SCHEMA):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            # WAL + synchronous=NORMAL: crash-safe, one fsync per checkpoint instead of per commit
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(schema)

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, rows: list) -> None:
        with self._lock:
            self._conn.executemany(sql, rows)

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def scalar(self, sql: str, params: tuple | dict = ()) -> Any:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return row[0] if row else None

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        """Serialised read-modify-write block (used for slot locking)."""
        with self._lock:
            if self._conn.in_transaction:      # nested: join the outer transaction
                yield self
                return
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            self._conn.close()
