"""Lineage ranking by Rt lower bound, and target-segment selection for
escalating lineages (FR-3.7, FR-3.8).
"""
from __future__ import annotations

from collections import Counter

from src.db import repository as repo
from src.stage3_rt.estimation import STATUS_ESCALATING


def rank_lineages() -> list[dict]:
    """All lineages with their latest Rt estimate, ranked by rt_lower desc
    (lineages with no estimate yet sort last)."""
    lineages = repo.list_lineages()
    latest = repo.get_latest_rt_for_all_lineages()

    ranked = []
    for lineage in lineages:
        rt_row = latest.get(lineage["variant_id"])
        ranked.append({
            "variant_id": lineage["variant_id"],
            "label": lineage["label"],
            "report_count": lineage["report_count"],
            "rt": rt_row["rt"] if rt_row else None,
            "rt_lower": rt_row["rt_lower"] if rt_row else None,
            "rt_upper": rt_row["rt_upper"] if rt_row else None,
            "status": rt_row["status"] if rt_row else "INSUFFICIENT_DATA",
        })

    ranked.sort(key=lambda r: (r["rt_lower"] is None, -(r["rt_lower"] or 0)))
    return ranked


def get_escalating_lineages() -> list[dict]:
    return [r for r in rank_lineages() if r["status"] == STATUS_ESCALATING]


def select_target_segment(variant_id: str) -> str | None:
    """Segment with highest recent report growth in this lineage that has not
    already received an inoculation for it (FR-3.8). Returns None if every
    segment with reports has already been targeted."""
    reports = repo.get_lineage_member_reports(variant_id)
    if not reports:
        return None

    counts = Counter(r["segment_id"] for r in reports)
    for segment_id, _ in counts.most_common():
        if not repo.segment_already_has_post_for_variant(segment_id, variant_id):
            return segment_id
    return None
