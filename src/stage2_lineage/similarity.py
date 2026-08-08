"""Cosine similarity helpers. Brute-force is adequate at hackathon/demo corpus
sizes (a few thousand reports) and has fewer failure modes than a FAISS index —
see IMPLEMENTATION_PLAN.md Step 3.2. Swap in FAISS if corpus size grows past
the point brute-force stays within NFR-1.2 (<=50ms/report).
"""
from __future__ import annotations

import numpy as np


def cosine_sim_matrix(vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """vec: (dim,) unit or non-unit vector. matrix: (n, dim). Returns (n,) similarities."""
    if matrix.size == 0:
        return np.array([])
    vec_norm = vec / (np.linalg.norm(vec) + 1e-12)
    mat_norms = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12)
    return mat_norms @ vec_norm


def best_match(vec: np.ndarray, ids: list[str], matrix: np.ndarray) -> tuple[str | None, float]:
    if not ids:
        return None, -1.0
    sims = cosine_sim_matrix(vec, matrix)
    best_idx = int(np.argmax(sims))
    return ids[best_idx], float(sims[best_idx])
