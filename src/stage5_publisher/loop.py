"""Autonomous publish loop (FR-5.1 to FR-5.10, DR-7). Runs as a daemon thread
inside the API process. Idempotent: a second `start()` while already running
is a no-op (FR-5.2). Any single-stage failure is logged and the tick is
abandoned; the next tick still runs (FR-5.10) — see `_run_tick` below.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone

from src.config import load_config
from src.db import repository as repo
from src.stage1_surveillance.replay import get_clock
from src.stage2_lineage.cluster import process_reports
from src.stage3_rt.estimation import estimate_all_lineages
from src.stage3_rt.ranking import get_escalating_lineages, select_target_segment
from src.stage4_content.generate import (
    check_provenance, check_rate_limit, generate_content_for_lineage,
)
from src.trace import trace

TICK_INTERVAL_SECONDS = 1.0


class PublisherLoop:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._auto_publish = True
        self._tick_count = 0
        self._last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, auto_publish: bool | None = None) -> dict:
        """Idempotent (FR-5.2): returns {'started': False, ...} if a loop is
        already running in this process instead of spawning a duplicate."""
        with self._lock:
            if self.running:
                return {"started": False, "already_running": True}

            self._auto_publish = (
                auto_publish if auto_publish is not None
                else load_config()["runtime"]["auto_publish"]
            )
            repo.set_state("auto_publish", "true" if self._auto_publish else "false")
            repo.set_state("loop_running", "true")

            self._stop_event.clear()
            get_clock().start()
            self._thread = threading.Thread(target=self._run, daemon=True, name="publisher-loop")
            self._thread.start()
            return {"started": True, "already_running": False}

    def stop(self) -> None:
        self._stop_event.set()
        repo.set_state("loop_running", "false")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_tick()
            except Exception as exc:  # noqa: BLE001 - FR-5.10: log, abandon tick, continue
                self._last_error = str(exc)
                with trace("stage5_publisher", "tick_error") as rec:
                    rec["decision"] = "tick_failed"
            self._tick_count += 1
            time.sleep(TICK_INTERVAL_SECONDS)

    def _run_tick(self) -> None:
        clock = get_clock()
        simulated_now = clock.simulated_now()
        if simulated_now is None:
            return  # no corpus ingested yet

        due_reports = clock.get_due_reports()
        if due_reports:
            process_reports(due_reports)

        estimate_all_lineages(as_of=simulated_now)

        for lineage in get_escalating_lineages():
            variant_id = lineage["variant_id"]
            if not check_provenance(variant_id):
                continue
            target_segment = select_target_segment(variant_id)
            if target_segment is None:
                continue
            if not check_rate_limit(target_segment, variant_id, as_of=simulated_now):
                continue
            self._publish_or_queue(variant_id, target_segment, lineage, simulated_now)

    def _publish_or_queue(
        self, variant_id: str, target_segment: str, lineage_rank_row: dict, simulated_now: datetime,
    ) -> None:
        with trace("stage5_publisher", f"generate:{variant_id}:{target_segment}") as rec:
            result = generate_content_for_lineage(variant_id, target_segment)
            if not result.ok:
                rec["decision"] = f"dropped:{result.reason}"
                return

            lineage = repo.get_lineage(variant_id)
            post = {
                "id": str(uuid.uuid4()),
                "created_at": simulated_now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "title": result.content["title"],
                "technique_layer": result.content["technique_layer"],
                "variant_layer": result.content["variant_layer"],
                "action_steps": result.content["action_steps"],
                "language": target_segment.split(":", 1)[-1],
                "target_segment": target_segment,
                "variant_id": variant_id,
                "supporting_report_count": lineage["report_count"] if lineage else 0,
                "rt_at_publish": lineage_rank_row.get("rt"),
                "rt_lower_bound": lineage_rank_row.get("rt_lower"),
                "template_assisted": result.template_assisted,
                "state": "published" if self._auto_publish else "queued",
            }
            repo.insert_post(post)
            rec["decision"] = post["state"]

    def status(self) -> dict:
        clock_status = get_clock().get_status()
        return {
            "loop_running": self.running,
            "auto_publish": self._auto_publish,
            "tick_count": self._tick_count,
            "last_error": self._last_error,
            "simulated_now": clock_status["simulated_now"],
            "compression_ratio": clock_status["compression_ratio"],
            "replay_paused": clock_status["paused"],
            "total_reports": clock_status["total_reports"],
            "reports_replayed": clock_status["reports_replayed"],
            "posts_published": repo.count_published_posts(),
        }


_loop: PublisherLoop | None = None
_loop_lock = threading.Lock()


def get_loop() -> PublisherLoop:
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = PublisherLoop()
        return _loop
