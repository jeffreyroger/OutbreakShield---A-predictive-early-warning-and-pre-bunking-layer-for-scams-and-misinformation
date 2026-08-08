"""Lineage forest export (FR-2.6) for GET /lineages."""
from __future__ import annotations

from src.db import repository as repo


def _rt_status_for(variant_id: str, latest_rt: dict) -> str:
    row = latest_rt.get(variant_id)
    return row["status"] if row else "INSUFFICIENT_DATA"


def build_forest() -> list[dict]:
    """Returns a list of root nodes, each with nested `children`. No orphan
    parent_id references (Step 3.7 verify)."""
    lineages = repo.list_lineages()
    latest_rt = repo.get_latest_rt_for_all_lineages()

    nodes: dict[str, dict] = {}
    for lineage in lineages:
        rt_row = latest_rt.get(lineage["variant_id"])
        nodes[lineage["variant_id"]] = {
            "variant_id": lineage["variant_id"],
            "parent_id": lineage["parent_id"],
            "label": lineage["label"],
            "first_seen": lineage["first_seen"],
            "last_seen": lineage["last_seen"],
            "report_count": lineage["report_count"],
            "languages": lineage["languages"],
            "regions": lineage["regions"],
            "rt": rt_row["rt"] if rt_row else None,
            "rt_lower": rt_row["rt_lower"] if rt_row else None,
            "rt_upper": rt_row["rt_upper"] if rt_row else None,
            "rt_status": _rt_status_for(lineage["variant_id"], latest_rt),
            "children": [],
        }

    roots = []
    for node in nodes.values():
        parent_id = node["parent_id"]
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots
