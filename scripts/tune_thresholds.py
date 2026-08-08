"""Sweeps THRESH_MEMBER / THRESH_MUTATION against data/labels/clustering.csv,
reporting per-language precision/recall (FR-2.4, DR-4).

Run: python scripts/tune_thresholds.py
"""
import sys
from pathlib import Path
import csv
import numpy as np

# Bootstrapping path to import src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.interfaces.embedder import LocalEmbedder
from src.db import repository as repo


def main() -> None:
    csv_path = Path("data/labels/clustering.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist. Run scripts/generate_labels.py first.")
        sys.exit(1)

    print("Loading labeled clustering set...")
    label_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label_rows.append(row)

    report_ids = [row["report_id"] for row in label_rows]
    print(f"Fetching {len(report_ids)} report texts from SQLite...")
    reports = repo.get_reports_by_ids(report_ids)
    report_map = {r["id"]: r for r in reports}

    # Group label rows by language
    by_lang = {}
    for row in label_rows:
        lang = row["language"]
        by_lang.setdefault(lang, []).append(row)

    print("Initializing LocalEmbedder (will download weights to models/ if not cached)...")
    # MiniLM-L12-v2 is configured in model.yaml
    embedder = LocalEmbedder(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    # Pre-embed all reports
    texts = [report_map[rid]["text"] for rid in report_ids if rid in report_map]
    if not texts:
        print("Error: No report texts found in database for labeled report IDs.")
        sys.exit(1)

    print(f"Embedding {len(texts)} texts...")
    embeddings = embedder.embed(texts)
    embedding_map = {}
    idx = 0
    for rid in report_ids:
        if rid in report_map:
            embedding_map[rid] = embeddings[idx]
            idx += 1

    # Sweep thresholds per language
    thresholds = np.arange(0.50, 0.96, 0.02)
    print("\nSweeping thresholds per language:")

    for lang, rows in by_lang.items():
        print(f"\n--- Language: {lang.upper()} (N = {len(rows)} reports) ---")
        
        # Filter rows with available embeddings
        valid_rows = [r for r in rows if r["report_id"] in embedding_map]
        n_valid = len(valid_rows)
        if n_valid < 2:
            print(f"Not enough data for language: {lang}")
            continue

        # Get embeddings and labels
        vecs = np.array([embedding_map[r["report_id"]] for r in valid_rows])
        families = [r["family_id"] for r in valid_rows]

        # Compute pairwise cosine similarities
        # vecs is unit-normalised, so dot product is cosine similarity
        sim_matrix = np.dot(vecs, vecs.T)

        # Compute pairwise ground truth links (excluding self-pairs)
        gt_links = []
        for i in range(n_valid):
            for j in range(i + 1, n_valid):
                gt_links.append(families[i] == families[j])
        gt_links = np.array(gt_links)

        best_t = 0.50
        best_f1 = 0.0
        best_metrics = (0.0, 0.0)

        # Print table header
        print(f"{'Thresh':<10}{'Precision':<12}{'Recall':<12}{'F1-Score':<10}")
        print("-" * 46)

        for t in thresholds:
            pred_links = []
            for i in range(n_valid):
                for j in range(i + 1, n_valid):
                    pred_links.append(sim_matrix[i, j] >= t)
            pred_links = np.array(pred_links)

            tp = np.sum(gt_links & pred_links)
            fp = np.sum(~gt_links & pred_links)
            fn = np.sum(gt_links & ~pred_links)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_t = t
                best_metrics = (precision, recall)

            # Print every 0.04 or best
            if abs(t % 0.04) < 1e-5 or t == 0.94:
                print(f"{t:.2f}      {precision:.4f}      {recall:.4f}      {f1:.4f}")

        print("-" * 46)
        print(f"Best Threshold for {lang.upper()}: {best_t:.2f} (F1: {best_f1:.4f}, Precision: {best_metrics[0]:.4f}, Recall: {best_metrics[1]:.4f})")


if __name__ == "__main__":
    main()
