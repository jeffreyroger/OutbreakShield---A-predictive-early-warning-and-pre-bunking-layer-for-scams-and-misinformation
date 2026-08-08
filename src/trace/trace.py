"""Structured decision tracing (FR-6.1). One row per agent decision, local-only."""
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from src.db.connection import get_connection


@contextmanager
def trace(stage: str, input_summary: str):
    """Wrap an agent decision. Fill rec['decision'/'score'/'tokens'] inside the block.

    Usage:
        with trace("stage2_lineage", report_id) as rec:
            rec["decision"] = "member"
            rec["score"] = 0.91
    """
    t0 = time.perf_counter()
    rec = {"decision": None, "score": None, "tokens": None}
    try:
        yield rec
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO traces (ts, stage, input_summary, decision, score, "
                "latency_ms, tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    stage,
                    input_summary,
                    rec.get("decision"),
                    rec.get("score"),
                    latency_ms,
                    rec.get("tokens"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
