"""Offline backtest (FR-3.10, FR-3.11): alert timestamp vs. "widely reported"
reference timestamp, per wave, plus aggregate coverage and false-alarm count.

"Widely reported" reference-timestamp definition (SRS Open Issue 4, resolved
in IMPLEMENTATION_PLAN.md Step 1.4): the first day a lineage's raw report
volume exceeds 3x its trailing 14-day median. This is computed automatically
from `reports`/`lineage_members` so the harness is fully functional with no
hand-labelled data. If `data/labels/backtest.csv` exists (columns:
variant_id,wave_name,reference_timestamp), its hand-labelled reference
timestamps are used instead for the waves it covers — hand-labelled ground
truth takes priority over the auto-computed proxy.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.db import repository as repo

LABELS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labels" / "backtest.csv"
TRAILING_WINDOW_DAYS = 14
TRIGGER_MULTIPLE = 3.0


def _parse_date(ts: str):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").date()


def _daily_raw_counts(variant_id: str) -> tuple[list, list[float]]:
    reports = repo.get_lineage_member_reports(variant_id)
    if not reports:
        return [], []
    first_date = min(_parse_date(r["timestamp"]) for r in reports)
    last_date = max(_parse_date(r["timestamp"]) for r in reports)
    n_days = (last_date - first_date).days + 1
    counts = [0.0] * n_days
    for r in reports:
        idx = (_parse_date(r["timestamp"]) - first_date).days
        counts[idx] += r["dup_count"]
    dates = [first_date + timedelta(days=i) for i in range(n_days)]
    return dates, counts


def compute_wide_report_timestamp(variant_id: str) -> str | None:
    """Auto-computed 'widely reported' proxy per the definition above."""
    dates, counts = _daily_raw_counts(variant_id)
    if len(dates) <= TRAILING_WINDOW_DAYS:
        return None
    for i in range(TRAILING_WINDOW_DAYS, len(dates)):
        window = counts[i - TRAILING_WINDOW_DAYS:i]
        median = sorted(window)[len(window) // 2]
        threshold = TRIGGER_MULTIPLE * median
        if counts[i] > 0 and (median == 0 or counts[i] > threshold):
            dt = datetime(dates[i].year, dates[i].month, dates[i].day, tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def _load_hand_labelled_waves() -> dict[str, dict]:
    if not LABELS_PATH.exists():
        return {}
    waves = {}
    with open(LABELS_PATH, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            waves[row["variant_id"]] = {
                "wave_name": row.get("wave_name", row["variant_id"]),
                "reference_timestamp": row["reference_timestamp"],
            }
    return waves


def run_backtest() -> dict:
    """Reproducible from a fixed corpus snapshot (NFR-4.3) — this function is
    purely a deterministic read over persisted state, no randomness involved.
    """
    lineages = repo.list_lineages()
    hand_labelled = _load_hand_labelled_waves()

    waves = []
    for lineage in lineages:
        variant_id = lineage["variant_id"]
        label_info = hand_labelled.get(variant_id)
        reference_ts = (
            label_info["reference_timestamp"] if label_info
            else compute_wide_report_timestamp(variant_id)
        )
        if reference_ts is None:
            continue  # never became a "major wave" by this definition

        first_escalation = repo.get_first_escalating_estimate(variant_id)
        alert_ts = first_escalation["as_of"] if first_escalation else None

        lead_time_seconds = None
        if alert_ts is not None:
            ref_dt = datetime.strptime(reference_ts, "%Y-%m-%dT%H:%M:%SZ")
            alert_dt = datetime.strptime(alert_ts, "%Y-%m-%dT%H:%M:%SZ")
            lead_time_seconds = (ref_dt - alert_dt).total_seconds()

        waves.append({
            "variant_id": variant_id,
            "wave_name": label_info["wave_name"] if label_info else lineage["label"],
            "reference_timestamp": reference_ts,
            "alert_timestamp": alert_ts,
            "lead_time_seconds": lead_time_seconds,
            "flagged_in_advance": lead_time_seconds is not None and lead_time_seconds >= 0,
        })

    n_waves = len(waves)
    n_flagged = sum(1 for w in waves if w["flagged_in_advance"])
    coverage = (n_flagged / n_waves) if n_waves else None

    # False alarms: lineages that ever hit ESCALATING but never became a major
    # wave by the reference-timestamp definition above.
    major_wave_ids = {w["variant_id"] for w in waves}
    false_alarms = 0
    for lineage in lineages:
        if lineage["variant_id"] in major_wave_ids:
            continue
        if repo.get_first_escalating_estimate(lineage["variant_id"]) is not None:
            false_alarms += 1

    return {
        "waves": waves,
        "coverage": coverage,
        "n_waves": n_waves,
        "n_flagged_in_advance": n_flagged,
        "false_alarm_count": false_alarms,
        "reference_definition": (
            f"First day raw report volume exceeds {TRIGGER_MULTIPLE}x its trailing "
            f"{TRAILING_WINDOW_DAYS}-day median (auto-computed unless overridden by "
            "data/labels/backtest.csv)."
        ),
    }
