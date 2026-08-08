"""PII redaction at ingestion (NFR-3.1, docs.md §4). Runs before any storage —
never deferred to display time.
"""
import re

_PHONE_RE = re.compile(r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b")
_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")
_VPA_RE = re.compile(r"\b[\w.\-]{2,}@[a-zA-Z]{2,}\b")
_EMAIL_RE = re.compile(r"\b[\w.\-]+@[\w.\-]+\.\w{2,}\b")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


def redact(text: str) -> str:
    """Strips phone numbers, account numbers, UPI VPAs, emails, and URLs.

    Order matters: emails/URLs first (more specific), then phone, then the
    broader VPA and bare-digit-string patterns last so they don't eat into an
    already-redacted token.
    """
    text = _URL_RE.sub("[redacted-url]", text)
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    text = _VPA_RE.sub("[redacted-vpa]", text)
    text = _ACCOUNT_RE.sub("[redacted-number]", text)
    return text
