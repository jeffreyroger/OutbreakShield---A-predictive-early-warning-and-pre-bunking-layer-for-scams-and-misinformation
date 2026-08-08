"""Deterministic output validator (FR-4.6, FR-4.8). Prompt constraints are not enough."""
import re

URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
PHONE_RE = re.compile(r"\b\d{10}\b|\+91[\s-]?\d{10}")
ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")
VPA_RE = re.compile(r"\b[\w.\-]{2,}@[a-zA-Z]{2,}\b")
PAYMENT_IMPERATIVE_RE = re.compile(
    r"\b(transfer|send|pay|share your (otp|pin|password))\b", re.IGNORECASE
)

# Populate with real terms before publishing (FR-4.7). Kept empty here deliberately —
# a blocklist is a policy decision, not a scaffolding placeholder.
DEMOGRAPHIC_BLOCKLIST: list[str] = []

MIN_LENGTH = 40
MAX_LENGTH = 2000


def validate(post: dict) -> tuple[bool, str | None]:
    """Returns (is_valid, rejection_reason)."""
    text = " ".join(
        str(post.get(field, "")) for field in ("title", "technique_layer", "variant_layer")
    )
    action_steps = post.get("action_steps") or []
    text += " " + " ".join(str(s) for s in action_steps)

    if URL_RE.search(text):
        return False, "contains_url"
    if PHONE_RE.search(text):
        return False, "contains_phone_number"
    if VPA_RE.search(text):
        return False, "contains_vpa_or_email"
    if PAYMENT_IMPERATIVE_RE.search(text):
        return False, "contains_payment_imperative"
    for term in DEMOGRAPHIC_BLOCKLIST:
        if term.lower() in text.lower():
            return False, f"names_blocklisted_demographic:{term}"
    if not (MIN_LENGTH <= len(text) <= MAX_LENGTH):
        return False, "length_out_of_bounds"

    return True, None
