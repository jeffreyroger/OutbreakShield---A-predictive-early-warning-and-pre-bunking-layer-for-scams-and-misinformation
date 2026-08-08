"""Stage 1 normaliser (FR-1.1 to FR-1.6): raw corpus records -> `reports` schema.

Raw record shape expected in data/corpus/*.jsonl (one JSON object per line):
    {
      "id": "optional-uuid",
      "text": "report text",
      "timestamp": "ISO 8601, or a bare date",
      "region": "string",
      "region_tier": "metro|tier2|tier3|rural|unknown"  (optional, inferred if absent),
      "language": "hi|en|..."  (optional, detected if absent),
      "source": "string",
      "source_url": "string" (optional)
    }

Malformed records are rejected loudly to a rejects file, never silently dropped
(Step 2.1 of IMPLEMENTATION_PLAN.md).
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from src.db import repository as repo
from src.stage1_surveillance.language import detect_language
from src.stage1_surveillance.pii import redact
from src.trace import trace

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "corpus"
REJECTS_PATH = CORPUS_DIR / "rejects.jsonl"

_VALID_TIERS = {"metro", "tier2", "tier3", "rural", "unknown"}
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalised_text_hash(text: str) -> str:
    """Lowercase, whitespace-collapsed, punctuation-stripped text hash for
    deduplication (FR-1.3, Step 2.2)."""
    cleaned = text.lower().strip()
    cleaned = _PUNCT_RE.sub("", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _parse_timestamp(raw: dict, report_id: str) -> str:
    """Deterministically jitters date-only timestamps within the day, seeded by
    report id, to avoid false-simultaneity spikes (Step 1.2)."""
    from datetime import datetime, timedelta, timezone
    import hashlib as _hashlib

    ts_raw = raw.get("timestamp")
    if not ts_raw:
        raise ValueError("missing timestamp")

    ts_str = str(ts_raw).strip()
    date_only = re.fullmatch(r"\d{4}-\d{2}-\d{2}", ts_str)
    if date_only:
        base = datetime.strptime(ts_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        seed = int(_hashlib.sha256(report_id.encode()).hexdigest()[:8], 16)
        seconds_into_day = seed % 86400
        dt = base + timedelta(seconds=seconds_into_day)
    else:
        ts_norm = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise_record(raw: dict) -> dict:
    """Raises ValueError on malformed input; caller routes those to rejects."""
    text = raw.get("text")
    if not text or not str(text).strip():
        raise ValueError("missing or empty text")

    report_id = raw.get("id") or str(uuid.uuid4())
    timestamp = _parse_timestamp(raw, report_id)

    redacted_text = redact(str(text))
    language = raw.get("language") or detect_language(redacted_text)

    region_tier = raw.get("region_tier") or "unknown"
    if region_tier not in _VALID_TIERS:
        region_tier = "unknown"

    return {
        "id": report_id,
        "text": redacted_text,
        "text_hash": normalised_text_hash(redacted_text),
        "timestamp": timestamp,
        "language": language,
        "region": raw.get("region") or "unknown",
        "region_tier": region_tier,
        "segment_id": f"{region_tier}:{language}",
        "source": raw.get("source") or "unknown",
        "source_url": raw.get("source_url"),
    }


def ingest_corpus(corpus_dir: Path = CORPUS_DIR) -> dict:
    """Loads every *.jsonl file in corpus_dir, normalises, dedups, and inserts
    into `reports`. Returns a summary dict. (FR-1.1 to FR-1.3, Step 2.1-2.2)
    """
    corpus_dir.mkdir(parents=True, exist_ok=True)
    inserted = 0
    duplicates = 0
    rejected = 0

    with open(REJECTS_PATH, "w", encoding="utf-8") as rejects_file:
        for path in sorted(corpus_dir.glob("*.jsonl")):
            if path.name == "rejects.jsonl":
                continue
            with open(path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    with trace("stage1_surveillance", f"{path.name}:{line_no}") as rec:
                        try:
                            raw = json.loads(line)
                            report = normalise_record(raw)
                            is_new = repo.insert_report(report)
                            if is_new:
                                inserted += 1
                                rec["decision"] = "inserted"
                            else:
                                duplicates += 1
                                rec["decision"] = "duplicate"
                        except (json.JSONDecodeError, ValueError, KeyError) as exc:
                            rejected += 1
                            rec["decision"] = "rejected"
                            rejects_file.write(json.dumps({
                                "file": path.name, "line": line_no,
                                "raw": line, "reason": str(exc),
                            }) + "\n")

    return {"inserted": inserted, "duplicates": duplicates, "rejected": rejected}
