"""Stage 2 clustering (FR-2.1 to FR-2.8): embed, assign to lineage (member /
mutation / new root), maintain incremental centroids, label new lineages.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np

from src.config import load_config
from src.db import repository as repo
from src.interfaces.factory import get_embedder
from src.stage2_lineage.labeling import generate_label
from src.stage2_lineage.similarity import best_match
from src.trace import trace


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assign_report(report: dict, embedding: np.ndarray) -> dict:
    """Pure decision function (FR-2.3), no DB writes. Returns:
    {"decision": "member"|"mutation"|"new_root", "target_id": str|None, "similarity": float}
    """
    cfg = load_config()["model"]["clustering"]
    lang = report.get("language")
    
    # Check for per-language overrides (DR-4)
    by_lang = cfg.get("by_language", {})
    if lang in by_lang:
        thresh_member = by_lang[lang]["thresh_member"]
        thresh_mutation = by_lang[lang]["thresh_mutation"]
    else:
        thresh_member = cfg["thresh_member"]
        thresh_mutation = cfg["thresh_mutation"]

    centroids = repo.get_all_centroids()
    if not centroids:
        return {"decision": "new_root", "target_id": None, "similarity": 0.0}

    ids = [c[0] for c in centroids]
    matrix = np.stack([c[1] for c in centroids])
    best_id, best_sim = best_match(embedding, ids, matrix)

    if best_sim >= thresh_member:
        return {"decision": "member", "target_id": best_id, "similarity": best_sim}
    if best_sim >= thresh_mutation:
        return {"decision": "mutation", "target_id": best_id, "similarity": best_sim}
    return {"decision": "new_root", "target_id": None, "similarity": best_sim}


def _apply_decision(report: dict, embedding: np.ndarray, decision: dict) -> str:
    """Writes the decision to the DB. Returns the variant_id the report joined."""
    now = _now_iso()

    if decision["decision"] == "member":
        variant_id = decision["target_id"]
        lineage = repo.get_lineage(variant_id)
        n = lineage["report_count"]
        # Running mean centroid update (FR-2.7) — never a full recompute.
        new_centroid = (lineage["centroid"] * n + embedding) / (n + 1)
        repo.update_lineage_after_member_add(
            variant_id, new_centroid, report["language"], report["region"], report["timestamp"]
        )
    else:
        variant_id = str(uuid.uuid4())
        parent_id = decision["target_id"] if decision["decision"] == "mutation" else None
        label, used_fallback = generate_label(variant_id, report["text"])
        repo.create_lineage(
            variant_id=variant_id,
            parent_id=parent_id,
            label=label,
            first_seen=report["timestamp"],
            languages=[report["language"]],
            regions=[report["region"]],
            centroid=embedding,
        )
        repo.update_lineage_after_member_add(
            variant_id, embedding, report["language"], report["region"], report["timestamp"]
        )

    repo.add_lineage_member(report["id"], variant_id, now)
    return variant_id


def process_reports(reports: list[dict]) -> dict:
    """Embeds and assigns a specific list of reports. Returns a summary dict.
    (FR-2.1 to FR-2.3, Step 3.1-3.3). Used directly by the publisher loop so
    only reports the replay clock has actually released are clustered; ad hoc
    CLI/batch use goes through `process_pending` below instead.
    """
    if not reports:
        return {"processed": 0, "members": 0, "mutations": 0, "new_roots": 0}

    already_clustered = repo.filter_already_clustered([r["id"] for r in reports])
    reports = [r for r in reports if r["id"] not in already_clustered]
    if not reports:
        return {"processed": 0, "members": 0, "mutations": 0, "new_roots": 0}

    embedder = get_embedder()
    texts = [r["text"] for r in reports]
    vectors = embedder.embed(texts)

    counts = {"members": 0, "mutations": 0, "new_roots": 0}
    for report, vector in zip(reports, vectors):
        with trace("stage2_lineage", report["id"]) as rec:
            repo.upsert_embedding(report["id"], vector)
            decision = assign_report(report, vector)
            _apply_decision(report, vector, decision)
            rec["decision"] = decision["decision"]
            rec["score"] = decision["similarity"]
            key = {"member": "members", "mutation": "mutations", "new_root": "new_roots"}[
                decision["decision"]
            ]
            counts[key] += 1

    return {"processed": len(reports), **counts}


def process_pending(limit: int | None = None) -> dict:
    """Embeds and assigns all unclustered reports (ad hoc / CLI use)."""
    reports = repo.get_unclustered_reports(limit=limit)
    return process_reports(reports)
