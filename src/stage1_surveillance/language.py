"""Local, dependency-free language detection heuristic (FR-1.4).

This is a placeholder detector, not a validated model — SRS Open Issue 5 /
DR-4 flag vernacular/low-resource quality as the top project risk, and this
module is explicitly the crudest layer in that chain. It exists so the
pipeline has a deterministic, offline, zero-dependency signal to build
against; swap in a real local language-ID model without changing the
`detect_language` call signature.
"""
import re

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_TAMIL_RE = re.compile(r"[஀-௿]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")

CONFIDENCE_THRESHOLD = 0.55


def detect_language(text: str) -> str:
    """Returns an ISO 639-1 code, or 'unknown' when confidence is below
    threshold (FR-1.4) — the report remains eligible for clustering either way.
    """
    if not text or not text.strip():
        return "unknown"

    devanagari_chars = len(_DEVANAGARI_RE.findall(text))
    tamil_chars = len(_TAMIL_RE.findall(text))
    latin_chars = sum(len(w) for w in _LATIN_WORD_RE.findall(text))
    total = devanagari_chars + tamil_chars + latin_chars
    if total == 0:
        return "unknown"

    devanagari_ratio = devanagari_chars / total
    tamil_ratio = tamil_chars / total
    latin_ratio = latin_chars / total

    if devanagari_ratio >= CONFIDENCE_THRESHOLD:
        return "hi"
    if tamil_ratio >= CONFIDENCE_THRESHOLD:
        return "ta"
    if latin_ratio >= CONFIDENCE_THRESHOLD:
        return "en"
    return "unknown"
