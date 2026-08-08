"""Per-lineage Rt estimation orchestration: builds the weighted daily arrival
series, calls the renewal-equation estimator, applies the alert-gating rule,
and persists the result (FR-3.1, FR-3.3 to FR-3.6, Step 4.1/4.4).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from src.config import load_config
from src.db import repository as repo
from src.stage3_rt.renewal import estimate_rt
from src.stage3_rt.weighting import get_segment_weight
from src.trace import trace

STATUS_ESCALATING = "ESCALATING"
STATUS_STABLE = "STABLE"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def _parse_date(ts: str):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").date()


def build_daily_incidence(variant_id: str, as_of: datetime) -> np.ndarray:
    """Daily bins from the lineage's first report through `as_of`, weighted by
    dup_count and segment reporting-propensity weight (FR-1.6)."""
    reports = repo.get_lineage_member_reports(variant_id)
    if not reports:
        return np.array([])

    first_date = min(_parse_date(r["timestamp"]) for r in reports)
    as_of_date = as_of.date()
    n_days = (as_of_date - first_date).days + 1
    if n_days <= 0:
        return np.array([])

    incidence = np.zeros(n_days)
    for r in reports:
        day_idx = (_parse_date(r["timestamp"]) - first_date).days
        if 0 <= day_idx < n_days:
            weight = r["dup_count"] * get_segment_weight(r["segment_id"])
            incidence[day_idx] += weight
    return incidence


def estimate_lineage_rt(variant_id: str, as_of: datetime | None = None) -> dict:
    """Computes, persists, and returns the current Rt estimate for one
    lineage. Always writes a row to rt_estimates, even when INSUFFICIENT_DATA,
    so the frontend has a continuous series to render (FR-7.2)."""
    as_of = as_of or datetime.now(timezone.utc)
    cfg = load_config()["model"]["rt"]

    with trace("stage3_rt", variant_id) as rec:
        incidence = build_daily_incidence(variant_id, as_of)
        result = estimate_rt(
            incidence,
            window_days=cfg["window_days"],
            serial_interval_mean=cfg["serial_interval_mean"],
            serial_interval_sd=cfg["serial_interval_sd"],
            credible_interval=cfg["credible_interval"],
        )

        n_reports = result["n_reports"] if result else 0.0
        if result is None or n_reports < cfg["min_reports"]:
            status = STATUS_INSUFFICIENT_DATA
        elif result["rt_lower"] > 1.0:
            status = STATUS_ESCALATING
        else:
            status = STATUS_STABLE

        as_of_iso = as_of.strftime("%Y-%m-%dT%H:%M:%SZ")
        rt = result["rt"] if result else None
        rt_lower = result["rt_lower"] if result else None
        rt_upper = result["rt_upper"] if result else None

        repo.insert_rt_estimate(
            variant_id, as_of_iso, rt, rt_lower, rt_upper, status, int(round(n_reports))
        )

        rec["decision"] = status
        rec["score"] = rt_lower

    return {
        "variant_id": variant_id, "as_of": as_of_iso, "rt": rt, "rt_lower": rt_lower,
        "rt_upper": rt_upper, "status": status, "n_reports": n_reports,
    }


def estimate_all_lineages(as_of: datetime | None = None) -> list[dict]:
    lineages = repo.list_lineages()
    return [estimate_lineage_rt(l["variant_id"], as_of=as_of) for l in lineages]
