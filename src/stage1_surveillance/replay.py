"""Replay harness (FR-1.7 to FR-1.9): walks ingested reports in timestamp order
on a compressed timeline. Pause/resume/seek supported. A single process-wide
clock — the publisher loop and the `/replay/*` API endpoints share it.

FR-1.8 is non-negotiable: the compression ratio and simulated current date must
be visible on screen at all times during replay (docs.md §5). `get_status()`
below is the source of truth the API/frontend read from.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from src.config import load_config
from src.db.connection import get_connection


def _parse_iso(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ReplayClock:
    def __init__(self, compression_ratio: int | None = None):
        self._lock = threading.RLock()
        self._compression_ratio = compression_ratio or load_config()["runtime"]["replay"][
            "compression_ratio"
        ]
        self._reports: list[dict] | None = None
        self._cursor = 0
        self._sim_start: datetime | None = None
        self._sim_elapsed_seconds = 0.0
        self._real_checkpoint = time.monotonic()
        self._paused = True  # replay does not advance until explicitly started

    def _ensure_loaded(self) -> None:
        if self._reports is not None:
            return
        with self._lock:
            if self._reports is not None:
                return
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM reports ORDER BY timestamp ASC"
                ).fetchall()
                self._reports = [dict(r) for r in rows]
            finally:
                conn.close()
            self._sim_start = (
                _parse_iso(self._reports[0]["timestamp"]) if self._reports else None
            )
            self._real_checkpoint = time.monotonic()

    def start(self) -> None:
        self._ensure_loaded()
        with self._lock:
            self._real_checkpoint = time.monotonic()
            self._paused = False

    def pause(self) -> None:
        with self._lock:
            self._checkpoint_locked()
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._real_checkpoint = time.monotonic()
            self._paused = False

    def seek(self, target: datetime) -> None:
        self._ensure_loaded()
        with self._lock:
            if self._sim_start is None:
                return
            self._sim_elapsed_seconds = (target - self._sim_start).total_seconds()
            self._real_checkpoint = time.monotonic()
            # Recompute cursor: due reports are those <= target.
            self._cursor = 0
            for i, r in enumerate(self._reports):
                if _parse_iso(r["timestamp"]) <= target:
                    self._cursor = i + 1
                else:
                    break

    def _checkpoint_locked(self) -> None:
        if not self._paused:
            elapsed_real = time.monotonic() - self._real_checkpoint
            self._sim_elapsed_seconds += elapsed_real * self._compression_ratio
            self._real_checkpoint = time.monotonic()

    def simulated_now(self) -> datetime | None:
        self._ensure_loaded()
        with self._lock:
            if self._sim_start is None:
                return None
            self._checkpoint_locked()
            return self._sim_start + timedelta(seconds=self._sim_elapsed_seconds)

    def get_due_reports(self) -> list[dict]:
        """Returns newly-due reports since the last call and advances the cursor."""
        self._ensure_loaded()
        with self._lock:
            now = self.simulated_now()
            if now is None or self._reports is None:
                return []
            due = []
            while self._cursor < len(self._reports) and _parse_iso(
                self._reports[self._cursor]["timestamp"]
            ) <= now:
                due.append(self._reports[self._cursor])
                self._cursor += 1
            return due

    def is_finished(self) -> bool:
        self._ensure_loaded()
        with self._lock:
            return self._reports is not None and self._cursor >= len(self._reports)

    def get_status(self) -> dict:
        self._ensure_loaded()
        with self._lock:
            now = self.simulated_now()
            return {
                "simulated_now": _fmt_iso(now) if now else None,
                "compression_ratio": self._compression_ratio,
                "paused": self._paused,
                "total_reports": len(self._reports) if self._reports else 0,
                "reports_replayed": self._cursor,
                "finished": self.is_finished(),
            }

    def reload(self) -> None:
        """Forces reload from DB (e.g. after a fresh ingest)."""
        with self._lock:
            self._reports = None
            self._cursor = 0
            self._sim_elapsed_seconds = 0.0


_clock: ReplayClock | None = None
_clock_lock = threading.Lock()


def get_clock() -> ReplayClock:
    global _clock
    with _clock_lock:
        if _clock is None:
            _clock = ReplayClock()
        return _clock
