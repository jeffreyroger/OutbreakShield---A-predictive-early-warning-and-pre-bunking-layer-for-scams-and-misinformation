"""Reporting-propensity weighting (FR-1.6): applied before Rt estimation, not
at ingestion, so the raw report count is always recoverable. Default 1.0 for
every segment unless overridden in config/segments.yaml — see docs.md §1 and
SRS Open Issue 2 (uniform-and-state-the-limitation vs. derive-and-cite).
"""
from __future__ import annotations

from src.config import load_config


def get_segment_weight(segment_id: str) -> float:
    cfg = load_config()["segments"]
    weights = cfg.get("weights") or {}
    return float(weights.get(segment_id, cfg["default_weight"]))
