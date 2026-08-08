"""Derives Phase 1's two labelled subsets from data/corpus/gen_manifest.json
(written by scripts/generate_corpus.py). This is SYNTHETIC ground truth — the
generator's own knowledge of which report belongs to which scam family and
acceleration wave — not human hand-labelling. Treat it as a stand-in until a
real corpus is collected and genuinely hand-labelled; see tasks.md.

Produces:
  data/labels/clustering.csv       — report_id,family_id,language
      Stratified sample (>=200 rows) across every (family, language) bucket,
      for tuning THRESH_MEMBER/THRESH_MUTATION (FR-2.4) once a real embedding
      model exists (Phase 3.1).

  data/labels/wave_ground_truth.csv — wave_id,family_id,wave_name,
                                       true_acceleration_date,report_ids
      One row per synthetic wave (>=8), report_ids pipe-separated. This is
      Phase 1.4's backtest-set deliverable in spirit, but deliberately
      independent of any lineage `variant_id` — a `variant_id` only exists
      after Stage 2 clustering runs, and under MODEL_MODE=stub (the only mode
      implemented so far) clustering is not semantically meaningful, so a
      variant_id-keyed data/labels/backtest.csv cannot be produced honestly
      yet. See src/stage3_rt/backtest.py's docstring for the "widely
      reported" reference definition this eventually needs to be joined
      against. The follow-up script scripts/build_backtest_labels.py (named,
      not yet built) will do that join once Phase 3.1 lands a real local
      embedding model: for each wave here, find which variant_id captured
      most of its report_ids via lineage_members, and emit backtest.csv from
      that.

Run: python scripts/generate_labels.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus" / "gen_manifest.json"
LABELS_DIR = Path(__file__).resolve().parent.parent / "data" / "labels"
CLUSTERING_OUT = LABELS_DIR / "clustering.csv"
WAVE_GROUND_TRUTH_OUT = LABELS_DIR / "wave_ground_truth.csv"

MIN_CLUSTERING_ROWS = 200
PER_BUCKET_SAMPLE = 25  # sampled per (family, language) bucket where available


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"{MANIFEST_PATH} not found — run scripts/generate_corpus.py first."
        )
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_clustering_labels(manifest: dict) -> list[tuple[str, str, str]]:
    """Stratified sample across every (family, language) bucket, base records only
    (duplicate copies never get their own reports.id row, so they're excluded)."""
    buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for report_id, meta in manifest["reports"].items():
        if meta["kind"] != "base":
            continue
        buckets[(meta["family_id"], meta["language"])].append(report_id)

    rows: list[tuple[str, str, str]] = []
    for (family_id, language), ids in sorted(buckets.items()):
        for report_id in ids[:PER_BUCKET_SAMPLE]:
            rows.append((report_id, family_id, language))

    if len(rows) < MIN_CLUSTERING_ROWS:
        raise RuntimeError(
            f"Only {len(rows)} clustering-label rows produced, need >= {MIN_CLUSTERING_ROWS}. "
            "Increase PER_BUCKET_SAMPLE or check the manifest's family/language coverage."
        )
    return rows


def build_wave_ground_truth(manifest: dict) -> list[dict]:
    rows = []
    for wave in manifest["waves"]:
        base_report_ids = [
            rid for rid in wave["report_ids"]
            if manifest["reports"].get(rid, {}).get("kind") == "base"
        ]
        rows.append({
            "wave_id": wave["wave_id"],
            "family_id": wave["family_id"],
            "wave_name": wave["wave_name"],
            "true_acceleration_date": wave["true_acceleration_date"],
            "report_ids": "|".join(base_report_ids),
        })
    return rows


def main() -> None:
    manifest = load_manifest()
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    clustering_rows = build_clustering_labels(manifest)
    with open(CLUSTERING_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["report_id", "family_id", "language"])
        writer.writerows(clustering_rows)
    print(f"Wrote {len(clustering_rows)} rows to {CLUSTERING_OUT}")

    wave_rows = build_wave_ground_truth(manifest)
    if len(wave_rows) < 8:
        raise RuntimeError(f"Only {len(wave_rows)} waves in manifest, need >= 8.")
    with open(WAVE_GROUND_TRUTH_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["wave_id", "family_id", "wave_name", "true_acceleration_date", "report_ids"]
        )
        writer.writeheader()
        writer.writerows(wave_rows)
    print(f"Wrote {len(wave_rows)} rows to {WAVE_GROUND_TRUTH_OUT}")

    print(
        "\ndata/labels/backtest.csv NOT produced — deferred until a real embedding "
        "model (Phase 3.1) exists; see this script's module docstring."
    )


if __name__ == "__main__":
    main()
