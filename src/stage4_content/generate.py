"""Stage 4 orchestration (FR-4.1 to FR-4.10): two-layer content, validated,
falls back to template, rate-limited, provenance-checked. Prompt constraints
alone are not trusted — every candidate passes the deterministic validator
(Step 5.4) before it can be returned as publishable.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.config import load_config
from src.db import repository as repo
from src.interfaces.factory import get_generator
from src.stage4_content.templates import fill_template, infer_technique, load_template
from src.stage4_content.validator import validate
from src.trace import trace

_HARD_CONSTRAINTS = (
    "Rules you must never break: do not include a URL, phone number, account "
    "number, UPI ID, or QR code. Do not write a verbatim scam message or a "
    "step-by-step procedure someone could replay. Do not name any specific "
    "district, community, caste, or demographic. Keep sentences short and "
    "avoid jargon."
)

_PROMPT_TEMPLATE = (
    "Write a two-layer scam-prevention warning in {language}.\n"
    "{constraints}\n\n"
    "Layer 1 (technique_layer): describe this general manipulation pattern, "
    "generically, so it protects against similar future scams.\n"
    "Layer 2 (variant_layer): describe what this specific scam looks like right "
    "now, based on: {context}\n\n"
    "Respond as JSON with keys: title, technique_layer, variant_layer, action_steps "
    "(a list of short strings)."
)


class GenerationResult:
    def __init__(self, content: dict | None, template_assisted: bool, reason: str | None = None):
        self.content = content
        self.template_assisted = template_assisted
        self.reason = reason

    @property
    def ok(self) -> bool:
        return self.content is not None


def _try_free_generation(language: str, context: str, max_retries: int) -> dict | None:
    generator = get_generator()
    prompt = _PROMPT_TEMPLATE.format(
        language=language, constraints=_HARD_CONSTRAINTS, context=context
    )
    for attempt in range(max_retries + 1):
        try:
            raw = generator.generate(prompt, max_tokens=512, temperature=0.7)
            parsed = json.loads(raw)
            candidate = {
                "title": str(parsed["title"]),
                "technique_layer": str(parsed["technique_layer"]),
                "variant_layer": str(parsed["variant_layer"]),
                "action_steps": [str(s) for s in parsed["action_steps"]],
            }
        except Exception:
            continue
        ok, _reason = validate(candidate)
        if ok:
            return candidate
    return None


def _fallback_template(technique: str, language: str, region_generic: str, variant_signal: str) -> dict | None:
    template = load_template(technique, language)
    if template is None:
        return None
    candidate = fill_template(template, region_generic, variant_signal)
    ok, _reason = validate(candidate)
    return candidate if ok else None


def generate_content_for_lineage(variant_id: str, target_segment: str) -> GenerationResult:
    """Produces validated content (free generation, or template fallback) for
    one (lineage, target segment) pair. Does not persist or publish — that is
    Stage 5's job, which also assigns id/createdAt/rt-at-publish (FR-5.4).
    """
    cfg = load_config()["runtime"]["generation"]
    lineage = repo.get_lineage(variant_id)
    if lineage is None:
        return GenerationResult(None, False, "lineage_not_found")

    member_reports = repo.get_lineage_member_reports(variant_id)
    sample_texts = [r["text"] for r in member_reports[:20]]
    technique = infer_technique(sample_texts)

    region_tier, language = (target_segment.split(":", 1) + ["unknown"])[:2]
    variant_signal = lineage["label"]
    context = (
        f"a '{technique}' scam pattern (lineage label: {lineage['label']}) affecting "
        f"the {region_tier} segment, described generically without naming any place"
    )

    with trace("stage4_content", f"{variant_id}:{target_segment}") as rec:
        free = _try_free_generation(language, context, cfg["max_retries"])
        if free is not None:
            rec["decision"] = "free_generation"
            return GenerationResult(free, template_assisted=False)

        template_result = _fallback_template(technique, language, region_tier, variant_signal)
        if template_result is not None:
            rec["decision"] = "template_fallback"
            return GenerationResult(template_result, template_assisted=True)

        rec["decision"] = "dropped"
        return GenerationResult(None, False, "no_valid_content_available")


def check_rate_limit(target_segment: str, variant_id: str, as_of: datetime | None = None) -> bool:
    """True if another post may be created for this segment right now (FR-4.10)."""
    cfg = load_config()["runtime"]["rate_limit"]
    as_of = as_of or datetime.now(timezone.utc)
    since = (as_of - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = repo.count_posts_for_segment_in_window(target_segment, since)
    return count < cfg["max_posts_per_segment_per_sim_week"]


def check_provenance(variant_id: str) -> bool:
    """True if the lineage has enough supporting reports to publish about
    (FR-4.9: no post below MIN_REPORTS)."""
    min_reports = load_config()["model"]["rt"]["min_reports"]
    lineage = repo.get_lineage(variant_id)
    return lineage is not None and lineage["report_count"] >= min_reports
