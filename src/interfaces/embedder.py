"""Abstract embedding interface + deterministic stub (DR-6, IF-1, IF-3).

No embedding request shall leave the machine (FR-2.1, CON-1).
"""
from abc import ABC, abstractmethod
import hashlib

import numpy as np


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Returns an (n, dim) array of unit-normalised embedding vectors."""
        ...


class StubEmbedder(Embedder):
    """Deterministic hash-based pseudo-embeddings. No weights needed.

    Lets the full pipeline run end-to-end with MODEL_MODE=stub and no
    weights present (IF-3).
    """

    def __init__(self, dim: int = 768):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            seed = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            v = rng.normal(size=self.dim)
            out.append(v / np.linalg.norm(v))
        return np.array(out)


class LocalEmbedder(Embedder):
    """Real local multilingual sentence-embedding model, loaded in-process.

    Select on Indic-language coverage, not English benchmark score (DR-4).
    Loads model and caches weights in models/ folder (CON-2, FR-2.1).
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 768))
        if self.model is None:
            import os
            from sentence_transformers import SentenceTransformer
            # Cache directory path: models/
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_dir = os.path.join(base_dir, "models")
            self.model = SentenceTransformer(self.model_name, cache_folder=cache_dir)
        
        # sentence-transformers encode returns unit-normalized embeddings if normalize_embeddings=True
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(embeddings, dtype=np.float64)
