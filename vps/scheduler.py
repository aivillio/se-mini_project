"""Background scheduler: periodic no-show release (VPS-F-016)."""

from __future__ import annotations

import logging
import threading

from vps.reservation import get_reservations

log = logging.getLogger("vps.scheduler")


class Scheduler:
    def __init__(self, ctx, interval_seconds: float | None = None):
        self.ctx = ctx
        self.interval = interval_seconds or ctx.settings.scheduler_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.runs = 0

    def tick(self) -> list[str]:
        released = get_reservations(self.ctx).release_no_shows()
        self.runs += 1
        if released:
            log.info("released %d no-show reservations: %s", len(released), released)
        return released

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception:  # pragma: no cover - keep the scheduler alive
                log.exception("scheduler tick failed")

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="vps-scheduler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
