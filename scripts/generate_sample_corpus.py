"""Generates a small synthetic corpus for local smoke-testing the pipeline
end-to-end (ingest -> cluster -> Rt -> generate -> publish) without waiting
on real corpus collection (Phase 1). NOT a substitute for Phase 1 — see
tasks.md. Deterministic (fixed seed) so re-runs are reproducible.

Run: python scripts/generate_sample_corpus.py
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus" / "sample.jsonl"

RNG = random.Random(42)

AUTHORITY_TEMPLATES_EN = [
    "Someone called claiming to be a police officer and said my account is linked to a crime, demanded I move my money to a 'safe account' immediately.",
    "A caller pretending to be a bank official said my card would be blocked unless I shared the OTP right now.",
    "Got a call from someone saying they were a customs officer and a parcel with illegal items was in my name, threatened arrest.",
    "Man claiming to be from the courier company said my package was seized and I had to pay a fine over the phone or face police action.",
]
AUTHORITY_TEMPLATES_HI = [
    "एक कॉलर ने खुद को पुलिस अधिकारी बताया और कहा कि मेरा खाता किसी अपराध से जुड़ा है, तुरंत पैसे 'सुरक्षित खाते' में भेजने को कहा।",
    "बैंक अधिकारी बनकर कॉल करने वाले ने कहा कि तुरंत OTP न बताने पर कार्ड ब्लॉक हो जाएगा।",
    "कस्टम अधिकारी बनकर कॉल आया और कहा कि मेरे नाम पर गैरकानूनी सामान वाला पार्सल है, गिरफ्तारी की धमकी दी।",
]
REFUND_TEMPLATES_EN = [
    "Got a call saying I was accidentally sent extra cashback and must send it back immediately via a payment link.",
    "A message said my electricity bill refund was ready but I had to approve a payment request to receive it.",
    "Someone said I overpaid on a delivery and to get the refund I need to share an OTP.",
]
REFUND_TEMPLATES_HI = [
    "एक कॉल आया कि गलती से ज्यादा कैशबैक भेज दिया गया है और तुरंत लिंक से वापस भेजना है।",
    "मैसेज में कहा गया कि बिजली बिल का रिफंड तैयार है लेकिन पहले एक पेमेंट रिक्वेस्ट स्वीकार करनी होगी।",
]

REGIONS = {
    "metro": ["Mumbai", "Delhi", "Bengaluru"],
    "tier2": ["Nagpur", "Indore", "Coimbatore"],
    "tier3": ["Jhansi", "Kolhapur", "Rajahmundry"],
    "rural": ["Sironj", "Malegaon rural", "Anantapur rural"],
}
SOURCES = ["consumer_complaint_board", "scam_report_forum", "regional_news_archive"]


def _pick_region_tier() -> str:
    return RNG.choices(["metro", "tier2", "tier3", "rural"], weights=[3, 3, 2, 1])[0]


def _make_report(day: int, base_date: datetime, template: str, language: str) -> dict:
    tier = _pick_region_tier()
    region = RNG.choice(REGIONS[tier])
    ts = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
    return {
        "text": template,
        "timestamp": ts,
        "region": region,
        "region_tier": tier,
        "language": language,
        "source": RNG.choice(SOURCES),
        "source_url": None,
    }


def generate(n_days: int = 45) -> list[dict]:
    base_date = datetime(2026, 5, 1)
    records: list[dict] = []

    # Family A ("authority_impersonation"): flat/background rate for the
    # first 2/3 of the window, then an accelerating tail -> should trip
    # ESCALATING (FR-3.5) in the second half.
    for day in range(n_days):
        if day < n_days * 0.55:
            n_today = RNG.choices([0, 1, 2], weights=[5, 3, 1])[0]
        else:
            growth = (day - n_days * 0.55) / (n_days * 0.45)
            n_today = int(1 + growth * 9) + RNG.choice([0, 1])
        for _ in range(n_today):
            template = RNG.choice(AUTHORITY_TEMPLATES_EN + AUTHORITY_TEMPLATES_EN + AUTHORITY_TEMPLATES_HI)
            language = "hi" if template in AUTHORITY_TEMPLATES_HI else "en"
            records.append(_make_report(day, base_date, template, language))

    # Family B ("refund_inversion"): steady low background rate throughout,
    # should stay STABLE / INSUFFICIENT_DATA — a negative control.
    for day in range(n_days):
        n_today = RNG.choices([0, 1], weights=[6, 1])[0]
        for _ in range(n_today):
            template = RNG.choice(REFUND_TEMPLATES_EN + REFUND_TEMPLATES_HI)
            language = "hi" if template in REFUND_TEMPLATES_HI else "en"
            records.append(_make_report(day, base_date, template, language))

    RNG.shuffle(records)
    return records


def main() -> None:
    records = generate()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} synthetic reports to {OUT_PATH}")


if __name__ == "__main__":
    main()
