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
    Not yet implemented — wire up in Phase 3, Step 3.1.
    """

    def __init__(self, model_name: str):
        raise NotImplementedError(
            "LocalEmbedder not yet implemented. Use MODEL_MODE=stub for now."
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError
