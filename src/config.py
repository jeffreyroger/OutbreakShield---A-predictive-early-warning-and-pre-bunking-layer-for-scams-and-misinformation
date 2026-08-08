"""Loads config/*.yaml. Every tunable value lives here, never in code (NFR-4.2)."""
from pathlib import Path
from functools import lru_cache
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

REQUIRED_KEYS = {
    "model.yaml": ["embedding", "clustering", "rt"],
    "segments.yaml": ["region_tiers", "languages", "default_weight", "weights"],
    "runtime.yaml": ["replay", "auto_publish", "rate_limit", "generation"],
}


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for key in REQUIRED_KEYS[name]:
        if key not in data:
            raise KeyError(f"{name} is missing required key: {key}")
    return data


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Returns {'model': {...}, 'segments': {...}, 'runtime': {...}}."""
    return {
        "model": _load_yaml("model.yaml"),
        "segments": _load_yaml("segments.yaml"),
        "runtime": _load_yaml("runtime.yaml"),
    }
