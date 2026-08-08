"""Typed read/write helpers over the SQLite schema (src/db/schema.sql).

Every stage goes through this module rather than writing raw SQL inline, so the
on-disk representation (JSON-encoded lists, BLOB-encoded vectors) is centralised
in one place per docs.md §6 ("thresholds/weights/priors live in config, never in
code" — the analogous rule for storage is: one encoding, one place).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np

from src.db.connection import get_connection


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vec_to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float64).tobytes()


def _blob_to_vec(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float64)


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def insert_report(report: dict) -> bool:
    """Inserts a normalised report. Returns False (no-op) if text_hash already
    exists — caller is responsible for incrementing dup_count in that case
    (FR-1.3: duplicates are signal, never silently dropped and never discarded).
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, dup_count FROM reports WHERE text_hash = ?",
            (report["text_hash"],),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE reports SET dup_count = ? WHERE id = ?",
                (existing["dup_count"] + 1, existing["id"]),
            )
            conn.commit()
            return False
        conn.execute(
            "INSERT INTO reports (id, text, text_hash, timestamp, language, region, "
            "region_tier, segment_id, source, source_url, dup_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                report["id"], report["text"], report["text_hash"], report["timestamp"],
                report["language"], report["region"], report["region_tier"],
                report["segment_id"], report["source"], report.get("source_url"),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def count_reports() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]
    finally:
        conn.close()


def get_unclustered_reports(limit: int | None = None) -> list[dict]:
    """Reports with no lineage_members row yet."""
    conn = get_connection()
    try:
        sql = (
            "SELECT r.* FROM reports r "
            "LEFT JOIN lineage_members m ON m.report_id = r.id "
            "WHERE m.report_id IS NULL ORDER BY r.timestamp ASC"
        )
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        return [dict(row) for row in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def get_reports_by_ids(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM reports WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# embeddings
# ---------------------------------------------------------------------------

def upsert_embedding(report_id: str, vector: np.ndarray) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO embeddings (report_id, vector) VALUES (?, ?) "
            "ON CONFLICT(report_id) DO UPDATE SET vector = excluded.vector",
            (report_id, _vec_to_blob(vector)),
        )
        conn.commit()
    finally:
        conn.close()


def get_embedding(report_id: str) -> np.ndarray | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT vector FROM embeddings WHERE report_id = ?", (report_id,)
        ).fetchone()
        return _blob_to_vec(row["vector"]) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# lineages
# ---------------------------------------------------------------------------

def create_lineage(
    variant_id: str, parent_id: str | None, label: str, first_seen: str,
    languages: Iterable[str], regions: Iterable[str], centroid: np.ndarray,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO lineages (variant_id, parent_id, label, first_seen, last_seen, "
            "report_count, languages, regions, centroid) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
            (
                variant_id, parent_id, label, first_seen, first_seen,
                json.dumps(sorted(set(languages))), json.dumps(sorted(set(regions))),
                _vec_to_blob(centroid),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_lineage(variant_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lineages WHERE variant_id = ?", (variant_id,)
        ).fetchone()
        return _lineage_row_to_dict(row) if row else None
    finally:
        conn.close()


def list_lineages() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM lineages ORDER BY first_seen ASC").fetchall()
        return [_lineage_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def _lineage_row_to_dict(row) -> dict:
    d = dict(row)
    d["languages"] = json.loads(d["languages"]) if d["languages"] else []
    d["regions"] = json.loads(d["regions"]) if d["regions"] else []
    d["centroid"] = _blob_to_vec(d["centroid"]) if d["centroid"] else None
    return d


def get_all_centroids() -> list[tuple[str, np.ndarray]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT variant_id, centroid FROM lineages").fetchall()
        return [(row["variant_id"], _blob_to_vec(row["centroid"])) for row in rows]
    finally:
        conn.close()


def update_lineage_after_member_add(
    variant_id: str, new_centroid: np.ndarray, report_language: str,
    report_region: str, report_timestamp: str,
) -> None:
    """Incremental update (FR-2.7): running-mean centroid, language/region set,
    last_seen, report_count += 1. Never a full recomputation over all members.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT languages, regions, last_seen, report_count FROM lineages "
            "WHERE variant_id = ?", (variant_id,),
        ).fetchone()
        languages = set(json.loads(row["languages"]) if row["languages"] else [])
        regions = set(json.loads(row["regions"]) if row["regions"] else [])
        languages.add(report_language)
        regions.add(report_region)
        last_seen = max(row["last_seen"], report_timestamp) if row["last_seen"] else report_timestamp
        conn.execute(
            "UPDATE lineages SET centroid = ?, languages = ?, regions = ?, "
            "last_seen = ?, report_count = report_count + 1 WHERE variant_id = ?",
            (
                _vec_to_blob(new_centroid), json.dumps(sorted(languages)),
                json.dumps(sorted(regions)), last_seen, variant_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def add_lineage_member(report_id: str, variant_id: str, assigned_at: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO lineage_members (report_id, variant_id, assigned_at) VALUES (?, ?, ?)",
            (report_id, variant_id, assigned_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_lineage_member_reports(variant_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.* FROM reports r JOIN lineage_members m ON m.report_id = r.id "
            "WHERE m.variant_id = ? ORDER BY r.timestamp ASC",
            (variant_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def filter_already_clustered(report_ids: list[str]) -> set[str]:
    """Returns the subset of report_ids that already have a lineage_members
    row. Used to keep clustering idempotent across restarts/replays (FR-5.5,
    NFR-2.2) — a report must never be assigned to a lineage twice."""
    if not report_ids:
        return set()
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in report_ids)
        rows = conn.execute(
            f"SELECT DISTINCT report_id FROM lineage_members WHERE report_id IN ({placeholders})",
            report_ids,
        ).fetchall()
        return {row["report_id"] for row in rows}
    finally:
        conn.close()


def get_children(parent_id: str) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT variant_id FROM lineages WHERE parent_id = ?", (parent_id,)
        ).fetchall()
        return [row["variant_id"] for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# rt_estimates
# ---------------------------------------------------------------------------

def insert_rt_estimate(
    variant_id: str, as_of: str, rt: float | None, rt_lower: float | None,
    rt_upper: float | None, status: str, n_reports: int,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO rt_estimates (variant_id, as_of, rt, rt_lower, rt_upper, "
            "status, n_reports) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (variant_id, as_of, rt, rt_lower, rt_upper, status, n_reports),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_rt(variant_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM rt_estimates WHERE variant_id = ? ORDER BY as_of DESC LIMIT 1",
            (variant_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_rt_series(variant_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM rt_estimates WHERE variant_id = ? ORDER BY as_of ASC",
            (variant_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_first_escalating_estimate(variant_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM rt_estimates WHERE variant_id = ? AND status = 'ESCALATING' "
            "ORDER BY as_of ASC LIMIT 1",
            (variant_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_latest_rt_for_all_lineages() -> dict[str, dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r1.* FROM rt_estimates r1 "
            "INNER JOIN (SELECT variant_id, MAX(as_of) AS max_as_of FROM rt_estimates "
            "GROUP BY variant_id) r2 "
            "ON r1.variant_id = r2.variant_id AND r1.as_of = r2.max_as_of"
        ).fetchall()
        return {row["variant_id"]: dict(row) for row in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# posts
# ---------------------------------------------------------------------------

def insert_post(post: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO posts (id, created_at, title, technique_layer, variant_layer, "
            "action_steps, language, target_segment, variant_id, supporting_report_count, "
            "rt_at_publish, rt_lower_bound, template_assisted, state, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                post["id"], post["created_at"], post["title"], post["technique_layer"],
                post["variant_layer"], json.dumps(post["action_steps"]), post["language"],
                post["target_segment"], post["variant_id"], post["supporting_report_count"],
                post["rt_at_publish"], post["rt_lower_bound"],
                1 if post["template_assisted"] else 0, post["state"], post.get("approved_by"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _post_row_to_dict(row) -> dict:
    d = dict(row)
    d["action_steps"] = json.loads(d["action_steps"]) if d["action_steps"] else []
    d["template_assisted"] = bool(d["template_assisted"])
    return d


def get_feed(limit: int | None = None, since: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM posts WHERE state = 'published'"
        params: list[Any] = []
        if since:
            sql += " AND created_at > ?"
            params.append(since)
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = conn.execute(sql, params).fetchall()
        return [_post_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_review_queue() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM posts WHERE state = 'queued' ORDER BY created_at ASC"
        ).fetchall()
        return [_post_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_post(post_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return _post_row_to_dict(row) if row else None
    finally:
        conn.close()


def set_post_state(post_id: str, state: str, approved_by: str | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE posts SET state = ?, approved_by = ? WHERE id = ?",
            (state, approved_by, post_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_posts_for_segment_in_window(segment_id: str, since_iso: str) -> int:
    """Used for FR-4.10 rate limiting: posts for this segment since `since_iso`."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE target_segment = ? "
            "AND state IN ('queued', 'published') AND created_at >= ?",
            (segment_id, since_iso),
        ).fetchone()
        return row["n"]
    finally:
        conn.close()


def segment_already_has_post_for_variant(segment_id: str, variant_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE target_segment = ? AND variant_id = ? "
            "AND state IN ('queued', 'published')",
            (segment_id, variant_id),
        ).fetchone()
        return row["n"] > 0
    finally:
        conn.close()


def count_published_posts() -> int:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE state = 'published'"
        ).fetchone()["n"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# traces
# ---------------------------------------------------------------------------

def get_recent_traces(limit: int = 100) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM traces ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# loop_state
# ---------------------------------------------------------------------------

def get_state(key: str, default: str | None = None) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM loop_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_state(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO loop_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
