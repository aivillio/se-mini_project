"""Application context: settings, database, clock and a lazy service registry.

Each module exposes ``get_<service>(ctx)`` which creates the service once per
context. This keeps modules decoupled (new modules plug in without editing a
central wiring file) and lets tests build an isolated context per test.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar
from zoneinfo import ZoneInfo

from vps.config import Settings
from vps.db import EDGE_SCHEMA, Database

T = TypeVar("T")


class Context:
    def __init__(self, settings: Settings | None = None, clock: Callable[[], datetime] | None = None):
        self.settings = settings or Settings.from_env()
        self.db = Database(self.settings.db_path)
        self.edge_db = Database(self.settings.edge_db_path, schema=EDGE_SCHEMA)
        self.tz = ZoneInfo(self.settings.timezone)
        self._clock = clock
        self._services: dict[str, Any] = {}
        self._lock = threading.RLock()

    # ---- time -------------------------------------------------------------
    def now(self) -> datetime:
        return self._clock() if self._clock else datetime.now(timezone.utc)

    def set_clock(self, clock: Callable[[], datetime] | None) -> None:
        self._clock = clock

    def now_iso(self) -> str:
        return self.now().isoformat()

    # ---- services ---------------------------------------------------------
    def service(self, name: str, factory: Callable[["Context"], T]) -> T:
        with self._lock:
            if name not in self._services:
                self._services[name] = factory(self)
            return self._services[name]

    def close(self) -> None:
        self.db.close()
        self.edge_db.close()


def parse_ts(value: str | datetime) -> datetime:
    """Parse an ISO-8601 timestamp; naive values are treated as UTC."""
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
