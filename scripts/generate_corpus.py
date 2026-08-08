"""Generates a large SYNTHETIC placeholder corpus for Phase 1 of
IMPLEMENTATION_PLAN.md. This is NOT real collected scam-report data — see
tasks.md. It exists to meet Phase 1's quantitative targets (>=3,000 distinct
reports, >=6 months span, >=3 languages, >=1 high-value manipulation variant)
so Phases 2-6 (already fully implemented against a tiny 124-record smoke-test
fixture) can be exercised meaningfully before real corpus collection happens.

Deterministic (fixed seed) so re-runs are reproducible (NFR-4.3 discipline).
Does not touch scripts/generate_sample_corpus.py, which stays as the small,
fast smoke-test generator.

Output:
  data/corpus/synthetic_v1.jsonl   — raw records in the schema
                                      src/stage1_surveillance/normalize.py expects
  data/corpus/gen_manifest.json    — generator-side ground truth (family/wave/
                                      duplicate/PII membership per report id),
                                      consumed by scripts/generate_labels.py
                                      and scripts/verify_pii_redaction.py

IMPORTANT ordering constraint: base (unique) records are written first, in
shuffled order among themselves, followed by duplicate-copy records, followed
by PII-injected records. Duplicate copies must always appear AFTER the base
record they copy, because src/stage1_surveillance/normalize.py's dedup keeps
whichever row is inserted FIRST for a given text_hash (i.e. first-in-file,
since ingestion is not timestamp-sorted) — this ordering is what keeps a
duplicate copy's id from ever needing to be treated as a real reports.id, and
keeps the labels files' report_id references valid without touching src/.

Run: python scripts/generate_corpus.py
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "corpus"
OUT_JSONL = CORPUS_DIR / "synthetic_v1.jsonl"
OUT_MANIFEST = CORPUS_DIR / "gen_manifest.json"

SEED = 20260101
RNG = random.Random(SEED)

BASE_DATE = datetime(2026, 1, 1)
TOTAL_DAYS = 210  # ~7 months, comfortably above the >=6-month floor

TARGET_UNIQUE_COUNT = 3600
DUPLICATE_FRACTION = 0.04
N_PII_INJECTED = 26

LANGUAGES = ["en", "hi", "ta"]

INSTITUTIONS = [
    "police", "customs department", "courier company",
    "income tax department", "cyber crime cell", "bank",
]
APPS = ["QuickTrade Pro", "GlobalWealth FX", "SmartGainz", "TrustInvest Elite", "RapidCoin Traders"]
AMOUNTS = [5000, 10000, 25000, 50000, 75000, 100000, 250000, 500000]
HOURS = [1, 2, 3, 4, 6]

REGIONS = {
    "metro": ["Mumbai", "Delhi", "Bengaluru", "Chennai"],
    "tier2": ["Nagpur", "Indore", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem"],
    "tier3": ["Jhansi", "Kolhapur", "Rajahmundry", "Erode", "Thanjavur", "Dindigul"],
    "rural": ["Sironj", "Malegaon rural", "Anantapur rural", "Sivaganga rural", "Namakkal rural"],
}
TN_REGIONS = {
    "metro": ["Chennai"],
    "tier2": ["Madurai", "Tiruchirappalli", "Salem", "Coimbatore"],
    "tier3": ["Erode", "Thanjavur", "Dindigul"],
    "rural": ["Sivaganga rural", "Namakkal rural"],
}
SOURCES = ["consumer_complaint_board", "scam_report_forum", "regional_news_archive"]

FAMILIES: dict[str, dict[str, list[str]]] = {
    "authority_impersonation": {
        "en": [
            "Someone called claiming to be a {institution} officer from {place} and said "
            "my account is linked to a case, demanded I move Rs {amount} to a 'safe "
            "account' within {hours} hours.",
            "A caller pretending to be a {institution} official said my card would be "
            "blocked unless I shared the OTP right away.",
            "Got a call from someone saying they were a {institution} officer and a "
            "parcel addressed to {place} was seized, threatened arrest within {hours} hours.",
            "Man claiming to be from {institution} said my package was held and I had to "
            "pay a fine of Rs {amount} over the phone or face police action.",
            "Received a call from a fake {institution} number saying my ID was linked to "
            "smuggling, asked me to stay on video call and pay Rs {amount}.",
        ],
        "hi": [
            "{institution} अधिकारी बनकर कॉल आया और कहा कि मेरा खाता किसी केस से जुड़ा है, "
            "{hours} घंटे में {amount} रुपये 'सुरक्षित खाते' में भेजने को कहा।",
            "{institution} अधिकारी बनकर कॉल करने वाले ने कहा कि तुरंत OTP न बताने पर कार्ड "
            "ब्लॉक हो जाएगा।",
            "{institution} अधिकारी बनकर कॉल आया, कहा कि {place} भेजा गया पार्सल जब्त हुआ है, "
            "{hours} घंटे में गिरफ्तारी की धमकी दी।",
            "{institution} से बताकर कॉल करने वाले ने कहा कि पार्सल रोका गया है और फोन पर "
            "{amount} रुपये जुर्माना देना होगा वरना पुलिस कार्रवाई होगी।",
        ],
        "ta": [
            "{institution} அதிகாரி என்று அழைத்து, என் கணக்கு ஒரு வழக்குடன் தொடர்புடையது "
            "என்று கூறி {hours} மணி நேரத்தில் {amount} ரூபாயை 'பாதுகாப்பான கணக்கிற்கு' "
            "அனுப்ப சொன்னார்கள்.",
            "{institution} அதிகாரி போல் அழைத்தவர், உடனே OTP கொடுக்கவில்லை என்றால் கார்டு "
            "பிளாக் ஆகும் என்று கூறினார்.",
            "{institution} அதிகாரி என்று கூறி, {place}க்கு அனுப்பப்பட்ட பார்சல் "
            "பறிமுதல் செய்யப்பட்டதாகவும், {hours} மணி நேரத்தில் கைது செய்வதாகவும் "
            "மிரட்டினார்கள்.",
        ],
    },
    "refund_inversion": {
        "en": [
            "Got a call saying I was accidentally sent extra cashback of Rs {amount} and "
            "must send it back immediately via a payment link.",
            "A message said my {institution} bill refund of Rs {amount} was ready but I "
            "had to approve a payment request to receive it.",
            "Someone said I overpaid Rs {amount} on a delivery to {place} and to get the "
            "refund I need to share an OTP.",
        ],
        "hi": [
            "एक कॉल आया कि गलती से {amount} रुपये ज्यादा कैशबैक भेज दिया गया है और तुरंत "
            "लिंक से वापस भेजना है।",
            "मैसेज में कहा गया कि {institution} बिल का {amount} रुपये रिफंड तैयार है "
            "लेकिन पहले एक पेमेंट रिक्वेस्ट स्वीकार करनी होगी।",
        ],
        "ta": [
            "தவறுதலாக {amount} ரூபாய் கூடுதல் கேஷ்பேக் அனுப்பப்பட்டதாகவும், உடனே லிங்க் "
            "வழியாக திருப்பி அனுப்ப வேண்டும் என்றும் அழைப்பு வந்தது.",
            "{place}க்கான டெலிவரியில் {amount} ரூபாய் அதிகமாக செலுத்தியதாகவும், "
            "பணத்தைப் பெற OTP தேவை என்றும் ஒருவர் கூறினார்.",
        ],
    },
    "digital_arrest": {
        "en": [
            "A video call from someone in a fake police uniform said I am under 'digital "
            "arrest' for a case in {place} and must stay on camera and transfer Rs "
            "{amount} to avoid real arrest.",
            "Caller claimed to be from {institution} cyber cell, said a parcel with "
            "illegal items was booked in my name from {place}, ordered me to remain on "
            "video call and pay Rs {amount} as 'refundable security'.",
            "Someone impersonating a central investigation officer said I'm under "
            "investigation and must not disconnect the video call or tell family, "
            "demanded Rs {amount} within {hours} hours.",
        ],
        "hi": [
            "नकली पुलिस वर्दी में एक वीडियो कॉल आया, कहा कि मैं {place} के एक केस में "
            "'डिजिटल अरेस्ट' में हूं, कैमरे पर बने रहना होगा और गिरफ्तारी से बचने के लिए "
            "{amount} रुपये भेजने होंगे।",
            "{institution} साइबर सेल से बताकर कॉल आया, कहा कि मेरे नाम से {place} से "
            "गैरकानूनी सामान वाला पार्सल बुक हुआ है, वीडियो कॉल पर बने रहकर {amount} रुपये "
            "'सिक्योरिटी' के तौर पर देने को कहा।",
            "खुद को जांच अधिकारी बताने वाले ने कहा कि मैं जांच के दायरे में हूं, कॉल न "
            "काटूं और परिवार को न बताऊं, {hours} घंटे में {amount} रुपये मांगे।",
        ],
        "ta": [
            "போலீஸ் சீருடையில் ஒருவர் வீடியோ கால் செய்து, {place} தொடர்பான வழக்கில் நான் "
            "'டிஜிட்டல் கைது'யில் இருப்பதாகவும், கேமராவில் இருந்தபடி {amount} ரூபாய் "
            "அனுப்ப வேண்டும் என்றும் கூறினார்.",
            "{institution} சைபர் செல் என்று கூறி அழைத்தவர், என் பெயரில் {place}லிருந்து "
            "சட்டவிரோத பொருட்கள் அனுப்பப்பட்டதாகவும், வீடியோ கால் துண்டிக்காமல் "
            "{amount} ரூபாய் 'பாதுகாப்பு தொகையாக' கொடுக்க வேண்டும் என்றும் கூறினார்.",
        ],
    },
    "investment_deepfake": {
        "en": [
            "Saw a video of a well-known businessman endorsing a trading app called "
            "{app}, invested Rs {amount} and now can't withdraw.",
            "A deepfake video of a celebrity promoting {app} investment scheme convinced "
            "me to deposit Rs {amount}, the platform stopped responding.",
            "Joined a WhatsApp group promoting {app} after seeing an AI-generated video, "
            "was asked to deposit Rs {amount} more to 'unlock' withdrawal.",
        ],
        "hi": [
            "एक जाने-माने बिजनेसमैन का वीडियो देखा जिसमें {app} नाम की ट्रेडिंग ऐप का "
            "प्रचार था, {amount} रुपये लगाए और अब निकाल नहीं पा रहा।",
            "एक सेलिब्रिटी का डीपफेक वीडियो देखकर {app} स्कीम में {amount} रुपये जमा "
            "किए, अब प्लेटफॉर्म जवाब नहीं दे रहा।",
        ],
        "ta": [
            "ஒரு பிரபல தொழிலதிபர் {app} எனும் டிரேடிங் ஆப்பை பரிந்துரைக்கும் வீடியோ "
            "பார்த்து {amount} ரூபாய் முதலீடு செய்தேன், இப்போது எடுக்க முடியவில்லை.",
            "AI உருவாக்கிய ஒரு பிரபலத்தின் வீடியோவைப் பார்த்து {app} திட்டத்தில் "
            "{amount} ரூபாய் செலுத்தினேன், தளம் இப்போது பதிலளிக்கவில்லை.",
        ],
    },
}

PII_SNIPPETS_EN = [
    " Call me back at 9876543210 to confirm.",
    " Send confirmation to fake.user@example.com.",
    " Check the status at http://fake-refund-status.example/verify.",
    " My alternate account number is 123456789012 if needed.",
]

# (family_id, wave_index, start_day, accel_day, end_day, primary_language, primary_tier, peak)
WAVES = [
    ("authority_impersonation", 1, 0, 45, 70, "en", "metro", 12),
    ("authority_impersonation", 2, 90, 130, 160, "hi", "tier2", 12),
    ("refund_inversion", 1, 10, 70, 90, "en", "tier2", 5),
    ("refund_inversion", 2, 100, 150, 175, "ta", "tier3", 5),
    ("digital_arrest", 1, 30, 85, 110, "ta", "tier2", 14),
    ("digital_arrest", 2, 120, 160, 190, "en", "metro", 14),
    ("digital_arrest", 3, 150, 195, 210, "hi", "rural", 14),
    ("investment_deepfake", 1, 0, 40, 60, "en", "metro", 13),
    ("investment_deepfake", 2, 70, 110, 140, "ta", "tier2", 13),
    ("investment_deepfake", 3, 130, 175, 200, "hi", "tier3", 13),
]


def pick_language(primary: str) -> str:
    if RNG.random() < 0.7:
        return primary
    return RNG.choice([l for l in LANGUAGES if l != primary])


def pick_tier(primary: str) -> str:
    if RNG.random() < 0.6:
        return primary
    return RNG.choices(["metro", "tier2", "tier3", "rural"], weights=[3, 3, 2, 1])[0]


def pick_place(tier: str, language: str) -> str:
    pool = TN_REGIONS[tier] if (language == "ta" and RNG.random() < 0.7) else REGIONS[tier]
    return RNG.choice(pool)


def make_text(family_id: str, language: str, tier: str) -> tuple[str, str]:
    """Returns (text, place) — place is returned too so the caller can use it as `region`."""
    place = pick_place(tier, language)
    slots = {
        "institution": RNG.choice(INSTITUTIONS),
        "amount": f"{RNG.choice(AMOUNTS):,}",
        "hours": RNG.choice(HOURS),
        "place": place,
        "app": RNG.choice(APPS),
    }
    template = RNG.choice(FAMILIES[family_id][language])
    return template.format(**slots), place


def make_unique_text(
    family_id: str, language: str, tier: str, seen_texts: set[str], disambiguator: int,
    max_attempts: int = 25,
) -> tuple[str, str]:
    """Like make_text, but guarantees the returned text is not already in
    seen_texts. Low-template-count families (e.g. refund_inversion) can
    exhaust their slot-substitution space well before reaching the volume
    target — retries with fresh slot draws first; if the space is truly
    exhausted, appends a short disambiguating suffix so uniqueness is never
    silently violated (which would otherwise show up as an unintended
    duplicate at ingestion instead of a deliberately-injected one)."""
    for _ in range(max_attempts):
        text, place = make_text(family_id, language, tier)
        if text not in seen_texts:
            seen_texts.add(text)
            return text, place
    # Slot space exhausted for this bucket — force uniqueness explicitly.
    text, place = make_text(family_id, language, tier)
    text = f"{text} [ref {disambiguator}]"
    seen_texts.add(text)
    return text, place


def generate_base_records() -> tuple[list[dict], dict, list[dict]]:
    """Returns (records, id_to_meta, wave_meta_list)."""
    records: list[dict] = []
    id_to_meta: dict[str, dict] = {}
    wave_meta_list: list[dict] = []
    seen_texts: set[str] = set()
    counter = 0

    for family_id, wave_idx, start_day, accel_day, end_day, primary_lang, primary_tier, peak in WAVES:
        wave_id = f"{family_id}_wave{wave_idx}"
        wave_ids_this_wave: list[str] = []

        for day in range(start_day, end_day):
            if day < accel_day:
                n_today = RNG.choices([0, 1, 2], weights=[6, 3, 1])[0]
            else:
                growth = (day - accel_day) / max(1, (end_day - accel_day))
                n_today = int(1 + growth * peak) + RNG.choice([0, 1])

            for _ in range(n_today):
                language = pick_language(primary_lang)
                tier = pick_tier(primary_tier)
                counter += 1
                text, place = make_unique_text(family_id, language, tier, seen_texts, counter)
                rid = f"syn-{counter:06d}"
                date_str = (BASE_DATE + timedelta(days=day)).strftime("%Y-%m-%d")
                record = {
                    "id": rid, "text": text, "timestamp": date_str, "region": place,
                    "region_tier": tier, "language": language,
                    "source": RNG.choice(SOURCES), "source_url": None,
                }
                records.append(record)
                id_to_meta[rid] = {
                    "family_id": family_id, "wave_id": wave_id, "language": language,
                    "kind": "base",
                }
                wave_ids_this_wave.append(rid)

        accel_date = (BASE_DATE + timedelta(days=accel_day)).strftime("%Y-%m-%d")
        wave_meta_list.append({
            "wave_id": wave_id, "family_id": family_id,
            "wave_name": f"{family_id} wave {wave_idx}",
            "true_acceleration_date": accel_date,
            "primary_language": primary_lang, "primary_region_tier": primary_tier,
            "report_ids": wave_ids_this_wave,
        })

    return records, id_to_meta, wave_meta_list


def top_up_to_target(records: list[dict], id_to_meta: dict, wave_meta_list: list[dict], counter_start: int) -> int:
    """Adds extra records (spread across random waves) if under TARGET_UNIQUE_COUNT."""
    counter = counter_start
    wave_lookup = {w["wave_id"]: w for w in wave_meta_list}
    seen_texts = {r["text"] for r in records}

    while len(records) < TARGET_UNIQUE_COUNT:
        family_id, wave_idx, start_day, accel_day, end_day, primary_lang, primary_tier, _ = RNG.choice(WAVES)
        wave_id = f"{family_id}_wave{wave_idx}"
        day = RNG.randint(start_day, end_day - 1)
        language = pick_language(primary_lang)
        tier = pick_tier(primary_tier)
        counter += 1
        text, place = make_unique_text(family_id, language, tier, seen_texts, counter)
        rid = f"syn-{counter:06d}"
        date_str = (BASE_DATE + timedelta(days=day)).strftime("%Y-%m-%d")
        record = {
            "id": rid, "text": text, "timestamp": date_str, "region": place,
            "region_tier": tier, "language": language,
            "source": RNG.choice(SOURCES), "source_url": None,
        }
        records.append(record)
        id_to_meta[rid] = {"family_id": family_id, "wave_id": wave_id, "language": language, "kind": "base"}
        wave_lookup[wave_id]["report_ids"].append(rid)

    return counter


def inject_duplicates(records: list[dict], counter_start: int) -> tuple[list[dict], list[dict], int]:
    """Returns (duplicate_records, duplicate_manifest_entries, new_counter)."""
    counter = counter_start
    n_dupes = int(len(records) * DUPLICATE_FRACTION)
    duplicate_records = []
    duplicate_entries = []

    for _ in range(n_dupes):
        original = RNG.choice(records)
        counter += 1
        rid = f"syn-{counter:06d}"
        day_offset = RNG.randint(0, TOTAL_DAYS - 1)
        date_str = (BASE_DATE + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        tier = RNG.choice(["metro", "tier2", "tier3", "rural"])
        place = pick_place(tier, original["language"])
        copy_record = {
            "id": rid, "text": original["text"], "timestamp": date_str, "region": place,
            "region_tier": tier, "language": original["language"],
            "source": RNG.choice(SOURCES), "source_url": None,
        }
        duplicate_records.append(copy_record)
        duplicate_entries.append({
            "copy_id": rid, "original_id": original["id"], "text_hash_basis": original["text"],
        })

    return duplicate_records, duplicate_entries, counter


def inject_pii(records: list[dict], id_to_meta: dict, counter_start: int) -> tuple[list[dict], list[str], int]:
    counter = counter_start
    pii_records = []
    pii_ids = []
    sample_bases = RNG.sample(records, min(N_PII_INJECTED, len(records)))

    for base in sample_bases:
        counter += 1
        rid = f"syn-{counter:06d}"
        snippet = RNG.choice(PII_SNIPPETS_EN)
        text = base["text"] + snippet
        record = {
            "id": rid, "text": text, "timestamp": base["timestamp"], "region": base["region"],
            "region_tier": base["region_tier"], "language": base["language"],
            "source": base["source"], "source_url": None,
        }
        pii_records.append(record)
        pii_ids.append(rid)
        meta = dict(id_to_meta[base["id"]])
        meta["kind"] = "pii_injected"
        id_to_meta[rid] = meta

    return pii_records, pii_ids, counter


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    base_records, id_to_meta, wave_meta_list = generate_base_records()
    counter = len(base_records)
    counter = top_up_to_target(base_records, id_to_meta, wave_meta_list, counter)

    RNG.shuffle(base_records)  # shuffle among base records only (ordering constraint, see module docstring)

    duplicate_records, duplicate_entries, counter = inject_duplicates(base_records, counter)
    pii_records, pii_ids, counter = inject_pii(base_records, id_to_meta, counter)

    # Ordering: base (shuffled) -> duplicates -> pii. Duplicates always after their original.
    all_records = base_records + duplicate_records + pii_records

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "seed": SEED,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_date": BASE_DATE.strftime("%Y-%m-%d"),
        "total_days": TOTAL_DAYS,
        "target_unique_count": TARGET_UNIQUE_COUNT,
        "actual_base_count": len(base_records),
        "duplicate_injected_count": len(duplicate_records),
        "pii_injected_count": len(pii_records),
        "total_raw_lines": len(all_records),
        "families": list(FAMILIES.keys()),
        "waves": wave_meta_list,
        "reports": id_to_meta,
        "duplicates": duplicate_entries,
        "pii_injected_ids": pii_ids,
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(all_records)} raw lines to {OUT_JSONL}")
    print(f"  base (unique) records: {len(base_records)}")
    print(f"  duplicate copies:      {len(duplicate_records)}")
    print(f"  PII-injected records:  {len(pii_records)}")
    print(f"Manifest written to {OUT_MANIFEST}")
    print("\nPer-family base counts:")
    from collections import Counter
    fam_counts = Counter(m["family_id"] for m in id_to_meta.values() if m["kind"] == "base")
    for fam, n in fam_counts.items():
        print(f"  {fam}: {n}")
    print("\nPer-language base counts:")
    lang_counts = Counter(m["language"] for m in id_to_meta.values() if m["kind"] == "base")
    for lang, n in lang_counts.items():
        print(f"  {lang}: {n}")


if __name__ == "__main__":
    main()
