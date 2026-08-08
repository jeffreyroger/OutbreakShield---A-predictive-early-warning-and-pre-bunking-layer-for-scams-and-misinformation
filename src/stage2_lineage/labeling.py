"""Lineage labelling (FR-2.8): short human-readable label via the local
generator. Must never block clustering — on any failure/timeout, fall back to
`variant-<short_id>` (Step 3.6).
"""
from __future__ import annotations

from src.interfaces.factory import get_generator

_PROMPT_TEMPLATE = (
    "Give a short (3-6 word) plain-English label for this scam report family. "
    "No punctuation besides spaces. Example report:\n\n{example_text}\n\nLabel:"
)


def generate_label(variant_id: str, example_text: str) -> tuple[str, bool]:
    """Returns (label, used_fallback)."""
    fallback = f"variant-{variant_id[:8]}"
    try:
        generator = get_generator()
        raw = generator.generate(
            _PROMPT_TEMPLATE.format(example_text=example_text[:500]),
            max_tokens=32,
            temperature=0.3,
        )
        label = raw.strip().strip('"').split("\n")[0][:80]
        if not label:
            return fallback, True
        return label, False
    except Exception:
        return fallback, True
