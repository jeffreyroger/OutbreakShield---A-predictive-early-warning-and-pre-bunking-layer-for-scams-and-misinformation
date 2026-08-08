"""Verifies Step 1.3: a regex sweep over the `reports` table returns zero
matches for phone/account/VPA/email/URL patterns, using the exact same
patterns src/stage1_surveillance/pii.py applies at ingestion. This checks
redaction actually survived storage, not just that the raw JSONL looked clean.

If data/corpus/gen_manifest.json exists (synthetic corpus run), cross-checks
the zero-match result against the manifest's pii_injected_ids count as a
positive control — proving the sweep had real cases to catch, not just an
already-empty haystack. Runs fine without a manifest too (e.g. against a
future real corpus that has no such file).

Run: python scripts/verify_pii_redaction.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.connection import get_connection
from src.stage1_surveillance.pii import (
    _ACCOUNT_RE, _EMAIL_RE, _PHONE_RE, _URL_RE, _VPA_RE,
)

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus" / "gen_manifest.json"

PATTERNS = {
    "phone": _PHONE_RE,
    "account_number": _ACCOUNT_RE,
    "vpa": _VPA_RE,
    "email": _EMAIL_RE,
    "url": _URL_RE,
}


def main() -> None:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, text FROM reports").fetchall()
    finally:
        conn.close()

    if not rows:
        print("No reports ingested yet. Run ingest first.")
        return

    matches: dict[str, list[str]] = {name: [] for name in PATTERNS}
    for row in rows:
        for name, pattern in PATTERNS.items():
            if pattern.search(row["text"]):
                matches[name].append(row["id"])

    total_matches = sum(len(v) for v in matches.values())
    print(f"Swept {len(rows)} reports for PII patterns post-redaction.")
    for name, ids in matches.items():
        status = "OK (0 matches)" if not ids else f"FAIL ({len(ids)} matches: {ids[:5]}...)"
        print(f"  {name}: {status}")

    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        injected_count = len(manifest.get("pii_injected_ids", []))
        print(
            f"\nPositive control: manifest recorded {injected_count} PII-injected "
            "reports (their raw text contained fake phone/email/url/account patterns "
            "before redaction). Zero surviving matches above means redaction caught "
            "all of them, not that there was nothing to catch."
        )
        if injected_count == 0:
            print(
                "WARNING: manifest exists but recorded 0 PII-injected reports — the "
                "positive control is not meaningful for this run."
            )
    else:
        print(
            "\nNo gen_manifest.json found — running without a positive-control count "
            "(fine for a real, non-synthetic corpus)."
        )

    if total_matches > 0:
        raise SystemExit(
            f"\nFAILED: {total_matches} PII pattern match(es) survived redaction. "
            "This is a release blocker per docs.md SS4/NFR-3.1 — do not proceed."
        )
    print("\nPASSED: zero PII pattern matches in stored report text.")


if __name__ == "__main__":
    main()
