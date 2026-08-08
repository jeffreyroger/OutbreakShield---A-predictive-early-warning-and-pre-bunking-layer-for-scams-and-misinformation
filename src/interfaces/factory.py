"""Selects stub vs. real model implementations via MODEL_MODE env var."""
import os

from src.interfaces.embedder import Embedder, StubEmbedder, LocalEmbedder
from src.interfaces.generator import Generator, StubGenerator, LocalGenerator


def get_embedder() -> Embedder:
    mode = os.environ.get("MODEL_MODE", "stub")
    if mode == "stub":
        return StubEmbedder()
    if mode == "real":
        from src.config import load_config
        cfg = load_config()["model"]["embedding"]
        return LocalEmbedder(model_name=cfg["model_name"])
    raise ValueError(f"Unknown MODEL_MODE: {mode!r} (expected 'stub' or 'real')")


def get_generator() -> Generator:
    mode = os.environ.get("MODEL_MODE", "stub")
    if mode == "stub":
        return StubGenerator()
    if mode == "real":
        from src.config import load_config
        cfg = load_config()["runtime"]["generation"]
        return LocalGenerator(model_name=cfg["model_name"], base_url=cfg.get("base_url", "http://127.0.0.1:11434"))
    raise ValueError(f"Unknown MODEL_MODE: {mode!r} (expected 'stub' or 'real')")
