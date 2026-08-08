"""Deliberately bad content must be caught (FR-4.8)."""
from src.stage4_content.validator import validate

VALID_POST = {
    "title": "Watch out for fake authority calls",
    "technique_layer": "Scammers impersonate an authority figure to create fear and "
    "pressure you into acting fast, before you have time to verify anything they say.",
    "variant_layer": "Recent reports describe callers claiming to be from a courier "
    "company demanding urgent action to release a package.",
    "action_steps": ["Hang up.", "Verify independently.", "Never share OTPs."],
}


def test_valid_post_passes():
    ok, reason = validate(VALID_POST)
    assert ok, reason


def test_rejects_url():
    post = {**VALID_POST, "variant_layer": VALID_POST["variant_layer"] + " Visit http://evil.example"}
    ok, reason = validate(post)
    assert not ok and reason == "contains_url"


def test_rejects_phone_number():
    post = {**VALID_POST, "variant_layer": VALID_POST["variant_layer"] + " Call 9876543210"}
    ok, reason = validate(post)
    assert not ok and reason == "contains_phone_number"


def test_rejects_payment_imperative():
    post = {**VALID_POST, "action_steps": ["Transfer the fee immediately"]}
    ok, reason = validate(post)
    assert not ok and reason == "contains_payment_imperative"


def test_rejects_too_short():
    post = {"title": "Hi", "technique_layer": "", "variant_layer": "", "action_steps": []}
    ok, reason = validate(post)
    assert not ok and reason == "length_out_of_bounds"
