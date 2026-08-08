"""Verifies Step 0.4: stub models run with no weights present (IF-3)."""
import numpy as np

from src.interfaces.embedder import StubEmbedder
from src.interfaces.generator import StubGenerator


def test_stub_embedder_returns_unit_vectors():
    embedder = StubEmbedder(dim=768)
    vectors = embedder.embed(["hello", "world"])
    assert vectors.shape == (2, 768)
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0)


def test_stub_embedder_is_deterministic():
    embedder = StubEmbedder(dim=64)
    a = embedder.embed(["same text"])
    b = embedder.embed(["same text"])
    assert np.allclose(a, b)


def test_stub_generator_returns_string():
    generator = StubGenerator()
    output = generator.generate("any prompt")
    assert isinstance(output, str)
    assert len(output) > 0
