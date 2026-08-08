"""Curated per-(technique, language) templates — the quality floor (DR-5).
Loaded before any free generation is attempted; free generation is the
upgrade, never the baseline (IMPLEMENTATION_PLAN.md Step 5.1).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_KEYWORD_TECHNIQUE_MAP = [
    (re.compile(r"\brefund|cashback|reversal|wrong(ly)? (sent|credited)\b", re.I), "refund_inversion"),
    (re.compile(r"\bpolice|officer|customs|court|arrest|bank official|courier|government\b", re.I), "authority_impersonation"),
]
DEFAULT_TECHNIQUE = "authority_impersonation"


def infer_technique(sample_texts: list[str]) -> str:
    """Crude keyword heuristic (placeholder — SRS Open Issue 5 flags this class
    of classification as unvalidated). Picks the first matching technique
    across a sample of the lineage's reports; defaults to authority
    impersonation, the most common pattern in the corpus this project targets.
    """
    for text in sample_texts:
        for pattern, technique in _KEYWORD_TECHNIQUE_MAP:
            if pattern.search(text or ""):
                return technique
    return DEFAULT_TECHNIQUE


def load_template(technique: str, language: str) -> dict | None:
    path = TEMPLATES_DIR / f"{technique}.{language}.yaml"
    if not path.exists():
        # Fall back to English template for the technique if the target
        # language has no curated template yet (DR-5 quality-floor gap,
        # reported not hidden — see docs.md §5 / ETH-7).
        path = TEMPLATES_DIR / f"{technique}.en.yaml"
        if not path.exists():
            return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fill_template(template: dict, region_generic: str, variant_signal: str) -> dict:
    variant_layer = template["variant_layer_template"].format(
        region_generic=region_generic, variant_signal=variant_signal,
    ).strip()
    return {
        "title": template["title"],
        "technique_layer": template["technique_layer"].strip(),
        "variant_layer": variant_layer,
        "action_steps": list(template["action_steps"]),
    }
