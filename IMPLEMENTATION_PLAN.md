# OutbreakShield — Implementation Plan

**Fully local build. No hosted model APIs, no external services at runtime.**
Companion to `SRS.md` and `SUMMARY.md`. Requirement IDs (FR-x, NFR-x, DR-x) refer to the SRS.

---

## How To Read This

Work is organised into **11 phases**. Phases 0–4 are strictly sequential — each produces an artifact the next consumes. Phases 5–8 can partly parallelise across the five-person team split. Phases 9–10 are integration and rehearsal.

Each step states: **what you build**, **how to verify it**, and **what breaks if you skip it**. The verification line is the important one — a step isn't done because code exists, it's done because the check passes.

**Two rules that govern the whole build:**

1. **Nothing calls out at runtime.** Weights download once during setup, then networking goes off. Test this early.
2. **Every stage persists its output.** SQLite between every stage boundary. This is what lets you debug stage 3 without re-running stages 1–2, and what lets you demo stage 2 if stage 4 is broken.

---

# PHASE 0 — Foundation
**Duration: 2–3 hours. Do this before splitting up. Everyone present.**

Skipping this phase is the most common way hackathon teams lose a day to merge conflicts and environment drift.

## Step 0.1 — Repository skeleton

```
outbreakshield/
├── config/
│   ├── model.yaml          # thresholds, Rt priors, serial interval
│   ├── segments.yaml       # segment definitions + reporting weights
│   └── runtime.yaml        # compression ratio, AUTO_PUBLISH, rate limits
├── data/
│   ├── corpus/             # raw collected reports (gitignored, but committed as a snapshot tarball)
│   ├── labels/             # hand-labelled subsets for tuning + backtest
│   └── outbreakshield.db   # SQLite (gitignored)
├── models/                 # downloaded weights (gitignored)
├── src/
│   ├── interfaces/         # abstract Embedder, Generator + STUBS
│   ├── stage1_surveillance/
│   ├── stage2_lineage/
│   ├── stage3_rt/
│   ├── stage4_content/
│   ├── stage5_publisher/
│   ├── trace/
│   ├── db/
│   └── api/
├── frontend/
├── scripts/                # setup.sh, backtest.py, tune_thresholds.py
├── tests/
└── README.md
```

**Verify:** `tree -L 2` matches. Every `src/stageN_*` has an `__init__.py` and a `cli.py`.

**Why:** the `cli.py` per stage (NFR-4.1) is what lets five people work without blocking each other.

## Step 0.2 — Config files, populated with defaults

`config/model.yaml`:
```yaml
embedding:
  model_name: "<local multilingual model>"
  dim: 768
clustering:
  thresh_member: 0.82        # ≥ this → join existing lineage
  thresh_mutation: 0.68      # ≥ this but < member → child lineage
  # < thresh_mutation → new root lineage
rt:
  window_days: 7
  serial_interval_mean: 2.5  # ASSUMED — see Open Issue 1
  serial_interval_sd: 1.5    # ASSUMED
  credible_interval: 0.95
  min_reports: 10
```

`config/runtime.yaml`:
```yaml
replay:
  compression_ratio: 64800   # 3 months → 2 minutes
auto_publish: true
rate_limit:
  max_posts_per_segment_per_sim_week: 2
generation:
  max_retries: 2
  timeout_seconds: 30
```

**Verify:** a `load_config()` helper reads all three and raises loudly on a missing key.

**Why:** NFR-4.2. Thresholds you'll tune fifteen times must never be in code. Every number here is one you will change under time pressure.

## Step 0.3 — SQLite schema

```sql
CREATE TABLE reports (
  id TEXT PRIMARY KEY, text TEXT, text_hash TEXT,
  timestamp TEXT, language TEXT, region TEXT, region_tier TEXT,
  segment_id TEXT, source TEXT, source_url TEXT,
  dup_count INTEGER DEFAULT 1
);
CREATE INDEX idx_reports_ts ON reports(timestamp);

CREATE TABLE embeddings (report_id TEXT PRIMARY KEY, vector BLOB);

CREATE TABLE lineages (
  variant_id TEXT PRIMARY KEY, parent_id TEXT, label TEXT,
  first_seen TEXT, last_seen TEXT, report_count INTEGER,
  languages TEXT, regions TEXT, centroid BLOB
);

CREATE TABLE lineage_members (report_id TEXT, variant_id TEXT, assigned_at TEXT);

CREATE TABLE rt_estimates (
  variant_id TEXT, as_of TEXT, rt REAL, rt_lower REAL, rt_upper REAL,
  status TEXT, n_reports INTEGER
);

CREATE TABLE posts (
  id TEXT PRIMARY KEY, created_at TEXT, title TEXT,
  technique_layer TEXT, variant_layer TEXT, action_steps TEXT,
  language TEXT, target_segment TEXT, variant_id TEXT,
  supporting_report_count INTEGER, rt_at_publish REAL, rt_lower_bound REAL,
  template_assisted INTEGER, state TEXT, approved_by TEXT
);
CREATE INDEX idx_posts_created ON posts(created_at DESC);

CREATE TABLE traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, stage TEXT,
  input_summary TEXT, decision TEXT, score REAL,
  latency_ms INTEGER, tokens INTEGER
);

CREATE TABLE loop_state (key TEXT PRIMARY KEY, value TEXT);
```

**Verify:** `python -m src.db.init` creates the DB idempotently; running twice is safe.

**Why:** FR-5.5 (restart survival) and NFR-2.2 are impossible to retrofit. `posts.state` (`queued`/`published`/`rejected`) is what makes FR-5.7 review mode a one-line change instead of a refactor.

## Step 0.4 — Model interfaces and stubs ← **highest-leverage step in the plan**

`src/interfaces/embedder.py`:
```python
class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray: ...

class StubEmbedder(Embedder):
    """Deterministic hash-based pseudo-embeddings. No weights needed."""
    def embed(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(t.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            v = rng.normal(size=768)
            out.append(v / np.linalg.norm(v))
        return np.array(out)
```

`src/interfaces/generator.py`: same pattern — `StubGenerator` returns a fixed, valid, schema-correct inoculation.

Selected via env var: `MODEL_MODE=stub|real`.

**Verify:** with `MODEL_MODE=stub` and `models/` empty, the entire pipeline runs end to end.

**Why (DR-6):** this is your insurance policy. It makes the system testable in CI, runnable on any teammate's laptop, and demo-able if a model fails to load twenty minutes before you present. Teams that skip this discover at hour 34 that only one laptop can run the project.

## Step 0.5 — Trace helper

```python
@contextmanager
def trace(stage: str, input_summary: str):
    t0 = time.perf_counter()
    rec = {"decision": None, "score": None, "tokens": None}
    try:
        yield rec
    finally:
        db.insert_trace(stage=stage, input_summary=input_summary,
                        latency_ms=int((time.perf_counter()-t0)*1000), **rec)
```

**Verify:** a dummy traced call writes one row.

**Why (FR-6.1):** wrapping calls costs seconds now and hours at hour 30. Wire it now or accept you won't have it.

---

# PHASE 1 — Corpus Collection
**Duration: 4–6 hours. Owner: Data track. Start immediately, runs parallel to Phases 0 and 2.**

This phase gates everything downstream and is the most commonly underestimated. Start it first.

## Step 1.1 — Source selection

Target **≥3,000 reports, ≥6 months span, ≥3 languages**. Draw from: consumer complaint boards, scam-report forums and subreddits, regional and vernacular news archives, publicly aggregated cybercrime summaries.

**Coverage requirement:** include at least one **high-value manipulation variant** — digital arrest or investment/deepfake — not only UPI refund scams. A demo showing only UPI collect-request fraud looks scoped in 2024.

**Verify:** `scripts/corpus_stats.py` prints count, date range, per-language and per-region-tier breakdown. Every bucket you intend to target must be non-empty.

**Breaks if skipped:** thin coverage in a language means clustering there is noise, and you'll discover it during the demo.

## Step 1.2 — Timestamps

Every report needs a usable timestamp — **the entire Rt model is a function of arrival times.** Where only a date exists, jitter within the day deterministically (seeded by report id) rather than collapsing everything to midnight, which creates false simultaneity spikes.

**Verify:** zero null timestamps; a histogram of arrivals shows no implausible single-instant spikes.

## Step 1.3 — PII redaction at ingestion

Regex-strip phone numbers, account numbers, UPI VPAs, emails, URLs, and person names where detectable. **At ingestion, before storage** (NFR-3.1) — not at display time.

**Verify:** a regex sweep over the `reports` table returns zero matches for phone/account/URL patterns.

**Breaks if skipped:** PII propagates into embeddings, into generated content, and into your published feed. This is unrecoverable once it's in the demo.

## Step 1.4 — Labelled subsets

Two hand-labelled sets:
- **Clustering set (≥200 reports):** which reports belong to the same scam family. Used to tune thresholds (Step 3.4).
- **Backtest set (≥8 waves):** for each historical wave, the variant, and a **"widely reported" reference timestamp**.

**Define "widely reported" explicitly now** (Open Issue 4). A workable definition: the date on which report volume for that variant first exceeds 3× its trailing 14-day median. Write the definition down; a judge will ask, and "we eyeballed it" is a bad answer.

**Verify:** both sets in `data/labels/` as CSV, with the reference-timestamp definition in the README.

---

# PHASE 2 — Stage 1: Surveillance
**Duration: 3–4 hours. Owner: Data track.**

## Step 2.1 — Normaliser
Map each raw record to the FR-1.2 schema. Reject malformed records loudly to a rejects file; never silently drop.

**Verify:** `python -m src.stage1_surveillance.cli ingest` populates `reports`; rejects file reviewed.

## Step 2.2 — Deduplication (FR-1.3)
Hash on normalised text (lowercase, whitespace-collapsed, punctuation-stripped). Keep earliest timestamp, **increment `dup_count`**.

**Do not discard duplicates.** Repeated identical reports are spread signal — that's a variant propagating verbatim, which is exactly what you're measuring.

**Verify:** dup count reported; spot-check five collapsed groups are genuine duplicates.

## Step 2.3 — Language detection (FR-1.4)
Local detector only. Below-confidence → `unknown`, still eligible for clustering.

**Verify:** per-language counts plausible; manually check 20 samples including transliterated Hinglish, which detectors handle poorly.

## Step 2.4 — Segment assignment (FR-1.5)
`segment_id = f"{region_tier}:{language}"`. Coarse is correct — the model needs consistent buckets, not precision.

## Step 2.5 — Reporting-propensity weights (FR-1.6)
Declare `w_s` per segment in `config/segments.yaml`. **Default all to 1.0.**

Resolve Open Issue 2 now by choosing one of two honest positions:
- **(a)** Keep uniform weights and state the limitation on screen and in the README.
- **(b)** Derive crude weights from survey data on differential reporting and cite the basis.

Either is defensible. What is not defensible is invented weights presented as measured. Whichever you choose, say it before you're asked.

## Step 2.6 — Replay harness (FR-1.7 to FR-1.9)
A clock that walks the corpus in timestamp order, emitting reports at compressed wall-clock intervals. Expose pause / resume / seek. Track `simulated_now`.

**Verify:** a 3-month corpus completes in ~2 minutes at default ratio; pause/resume/seek work; `simulated_now` monotonic.

**Breaks if skipped:** without seek you cannot re-run a specific moment during Q&A, which you will need.

---

# PHASE 3 — Stage 2: Lineage Clustering
**Duration: 6–8 hours. Owner: Modeling track. This is your differentiator — budget generously.**

## Step 3.1 — Local embedding model

Download once, cache in `models/`. **Select on Indic-language coverage, not English benchmark score** (DR-4). Load in-process, batch of 32–64.

**Verify:** `embed()` returns correct-dimension unit vectors; throughput ≥200 reports/sec (NFR-1.1); **runs with networking disabled**.

**Test the offline case now, not later.** Some libraries phone home on load even with cached weights.

## Step 3.2 — Vector persistence (FR-2.2)
Store as BLOB in `embeddings`, plus an in-memory FAISS index (or numpy matrix — at 3,000 reports brute-force cosine is entirely adequate and has fewer failure modes).

**Verify:** embeddings survive restart; no re-embedding on second run.

## Step 3.3 — Incremental clustering (FR-2.3)

```python
def assign(report, embedding):
    sims = cosine(embedding, all_lineage_centroids)
    best, best_sim = argmax(sims), max(sims)
    if best_sim >= THRESH_MEMBER:
        return ("member", best)
    elif best_sim >= THRESH_MUTATION:
        return ("mutation", best)      # child lineage, parent = best
    else:
        return ("new_root", None)
```

Wrap in `trace()` recording the decision and similarity score.

**Verify:** on the labelled set, member assignments align with hand labels; mutations produce sensible parents.

## Step 3.4 — Threshold tuning (FR-2.4)

`scripts/tune_thresholds.py` sweeps both thresholds against the labelled clustering set, reporting pairwise precision/recall per threshold pair.

**Tune per language and report per-language quality separately** (DR-4). Local embeddings underperform in low-resource languages; a single aggregate number hides that. Reporting the gap yourself is stronger than having it found.

**Verify:** chosen thresholds written to `config/model.yaml`; a per-language quality table is in the README and displayable on screen.

## Step 3.5 — Incremental centroids (FR-2.7)
Running mean on member addition. Never full recomputation — that's an O(n²) trap that will stall your replay loop at scale.

## Step 3.6 — Lineage labelling (FR-2.8)
Short label from the local generator. **Must not block clustering** — async, with fallback `variant-<short_id>` on failure or timeout.

**Verify:** killing the generator mid-run leaves clustering fully functional with fallback labels.

## Step 3.7 — Tree export (FR-2.6)
`GET /lineages` returns the forest as nested JSON with per-node report count, Rt status, languages, regions, first-seen.

**Verify:** valid tree; no orphan `parent_id` references.

---

# PHASE 4 — Stage 3: Rt Modeling
**Duration: 5–7 hours. Owner: Modeling track. This is your credibility asset.**

## Step 4.1 — Weighted arrival series
Per lineage, bucket reports into daily bins over the sliding window, weighted by `w_s` and `dup_count`.

**Verify:** series sums match weighted report counts.

## Step 4.2 — Renewal-equation Rt (FR-3.1)

Implement it yourself in NumPy/SciPy — it's about 60 lines and depending on an external stats service violates the local constraint.

Method: discretise the serial-interval distribution from the configured mean/SD; compute total infectiousness Λ_t = Σ I_{t-s} · w(s); estimate Rt over the window with a Gamma prior on Rt, yielding a Gamma posterior; take the point estimate and the 95% credible interval from the posterior.

**Verify:** on synthetic data with known R, recovered Rt is within the credible interval. **Write this test first** — it's the only thing standing between you and a plausible-looking but wrong number on stage.

**Why not SIR (FR-3.2, DR-1):** SIR needs a susceptible-population denominator you cannot credibly estimate for a messaging cluster. Rt needs only arrival times. If asked, say this directly — it reads as having thought about it, which you have.

## Step 4.3 — Serial-interval sensitivity (Open Issue 1)
Sweep the assumed mean across a plausible range (say 1.5–4 days) and record how alert timing shifts.

**Verify:** a small table in the README showing lead time under each assumption.

**Why:** "you assumed the serial interval" is the sharpest available technical question. Having the sensitivity table converts it from a hit into a demonstration of rigour.

## Step 4.4 — Alert gating (FR-3.5, FR-3.6, DR-2)
Flag `ESCALATING` only when **`rt_lower > 1.0`** and `n_reports >= MIN_REPORTS`. Otherwise `INSUFFICIENT_DATA` or `STABLE`.

**Never alert on point estimates.** At low counts Rt is extremely noisy; gating on the lower bound trades a little lead time for a large reduction in false alarms, which is the right trade given rate-limiting and trust concerns.

## Step 4.5 — Ranking and target segment (FR-3.7, FR-3.8)
Rank lineages by `rt_lower`. For each escalating lineage, target segment = highest recent growth in that lineage's reports **that has not already received an inoculation for it**.

**Verify:** ranking updates per tick; no segment receives a duplicate inoculation for the same variant.

## Step 4.6 — Backtest harness (FR-3.10, FR-3.11)

`scripts/backtest.py` replays the corpus with publishing disabled and emits per wave: alert timestamp, reference timestamp, **lead time**; and in aggregate: **coverage** (fraction of major waves flagged in advance) and **false-alarm count**.

**Report both metrics.** Lead time alone invites "so what?" A crude precision/recall pair across 8–10 waves is what signals you understand evaluation.

**Verify:** fixed seed + fixed corpus snapshot → byte-identical results across runs (NFR-4.3). Judges may ask you to re-run it.

---

# PHASE 5 — Stage 4: Inoculation Content
**Duration: 6–8 hours. Owner: Content track. Highest-risk phase.**

## Step 5.1 — Templates first ← **do this before touching the model** (DR-5)

For each target language, hand-write a template per manipulation technique with model-fillable slots:

```
[TECHNIQUE: authority_impersonation | lang: hi]
title: "{authority_type} बनकर आने वाली कॉल से सावधान"
technique_layer: "<fixed, hand-written, native-reviewed>"
variant_layer: "इन दिनों {region_generic} में ... {variant_signal}"
action_steps: [<fixed>]
```

**Why first:** local models are materially weaker in Indian languages than hosted ones, and generated content is your entire user-facing surface. Templates are your guaranteed quality floor. Free generation becomes the upgrade, not the baseline. Teams that invert this order ship a demo whose most visible artifact is the weakest component.

**Verify:** every (technique × language) pair has a template, each reviewed by a native speaker on the team.

## Step 5.2 — Local generator setup
Ollama or llama.cpp bound to `127.0.0.1`, quantised 7–8B instruction-tuned model.

**Verify:** generation works with networking disabled; latency measured (NFR-1.4 target ≤15 s).

## Step 5.3 — Two-layer prompt (FR-4.2)

- **Technique layer** — generic manipulation pattern. This is what generalises to unseen mutations (DR-3) and is the honest basis for calling the system predictive.
- **Variant layer** — this specific scam, in the target language, short sentences, low reading level.

Hard constraints in the prompt (FR-4.6, FR-4.7): no URLs, no phone/account numbers, no verbatim scam message, no step-by-step reproducible procedure, no named district/community/caste/demographic.

## Step 5.4 — Output validator (FR-4.8) ← **deterministic, not model-based**

```python
def validate(post) -> tuple[bool, str|None]:
    # reject on: URL pattern, phone/account/VPA pattern,
    # imperative payment instruction, blocklisted demographic term,
    # length outside [MIN, MAX]
```

Retry up to `MAX_RETRIES`, then drop with a logged reason.

**Verify:** unit tests with deliberately bad content — each violation class must be caught. **Prompt constraints alone are insufficient**; the validator is the actual control.

## Step 5.5 — Fallback path (FR-4.4)
On repeated validation failure, timeout, or unavailable model → curated template, `template_assisted: true`.

**Verify:** with the generator killed, posts still appear, correctly flagged.

**Why the flag matters:** it's the difference between graceful degradation and quiet overclaiming. Leave it visible in the UI.

## Step 5.6 — Provenance and rate limiting (FR-4.9, FR-4.10)
`supporting_report_count` on every post; no post below `MIN_REPORTS`. Cap at 2 posts per segment per simulated week.

**Why the cap (ETH-4):** over-warning erodes trust, and the inoculation literature specifically values not inducing generalised distrust. Uncapped alerting defeats the intervention it's trying to deliver.

## Step 5.7 — Async execution (NFR-1.4)
Generation runs off the replay loop via a worker queue. **A 15-second synchronous call will visibly stall the lineage tree animation** — the one visual you cannot afford to have stutter.

**Verify:** tree animates smoothly while generation runs.

---

# PHASE 6 — Stage 5: Publisher and API
**Duration: 4–5 hours. Owner: Backend track. P0 — this is what's graded.**

## Step 6.1 — `POST /init` (FR-5.1, FR-5.2)
Starts a background loop, returns immediately. **Idempotent** — a second call while running must not spawn a duplicate loop. Guard via a `loop_state` row.

**Verify:** call twice; exactly one loop; no duplicate posts.

## Step 6.2 — Loop body
Per tick: advance replay clock → ingest due reports → embed → cluster → recompute Rt → check escalations → enqueue generation → publish ready posts. Each substep traced.

## Step 6.3 — Post schema and feed (FR-5.3, FR-5.4, FR-5.6)
`GET /feed` newest-first, unique `id`, ISO 8601 UTC `createdAt`, with `limit` and `since`.

**Verify against the grading spec literally.** Check ordering, ID uniqueness across a full run, and that timestamps parse as ISO 8601 UTC with a `Z` suffix. This is the cheapest place to lose marks and the easiest to check.

## Step 6.4 — Persistence and restart (FR-5.5, NFR-2.2)
All state in SQLite. On restart, resume from `loop_state` without republishing.

**Verify:** `SIGKILL` mid-run, restart, confirm no duplicates and no lost state. Run this test explicitly — don't assume.

## Step 6.5 — Review mode (FR-5.7, FR-5.8, DR-7)
`AUTO_PUBLISH=false` → posts enter `state='queued'`; `GET /review`, `POST /review/{id}/approve|reject`.

Because `posts.state` exists from Phase 0, this is a config branch, not a refactor.

**Verify:** both modes work; mode visible in `/status` and the UI.

**Why this is high value:** autonomy is required by the evaluation spec, human oversight is required by responsibility. One flag satisfies both, and it converts the governance question from a weakness into a prepared answer.

## Step 6.6 — Fault tolerance (FR-5.10)
Any stage exception → log, abandon tick, continue. The loop must survive 60 minutes unattended without crash or >20% memory growth (NFR-2.1).

**Verify:** run 60 minutes; monitor RSS.

## Step 6.7 — `/status` and `/trace` (FR-5.9, FR-6.2)

---

# PHASE 7 — Frontend
**Duration: 8–10 hours. Owner: Frontend track. Start early — this carries the pitch.**

## Step 7.1 — Lineage tree (FR-7.1) ← **primary demo asset, build first**
D3 force or tidy tree. Nodes sized by report count, coloured by Rt status (grey insufficient / blue stable / red escalating). Animates as replay advances — **new branches must visibly appear**, since that motion is the entire "wow" moment.

**Verify:** smooth with 500+ nodes (NFR-1.6); branching is visible, not just a static graph that quietly changes.

## Step 7.2 — Status bar (FR-7.5) ← **build second, it's non-negotiable**
Always visible: simulated date, **compression ratio**, mode, loop state.

**Why (FR-1.8, ETH-6):** stated compression reads as rigour; discovered compression reads as fraud. This is a one-hour component that protects the entire project's credibility.

## Step 7.3 — Rt panel (FR-7.2)
Rt over time per lineage with the credible-interval band shaded and the Rt = 1 line marked. **Show the band, not just the line** — the band is what justifies your alerting rule.

## Step 7.4 — Backtest chart (FR-7.3)
Alert timestamp vs. wide-reporting timestamp, lead time annotated, aggregate coverage and false-alarm count displayed.

## Step 7.5 — Feed (FR-7.4)
Live-updating, newest first, **both content layers visible**, supporting report count shown, `template_assisted` badge where applicable.

## Step 7.6 — Trace view (FR-7.6)
Live agent decisions with latency. Low effort, disproportionately high credibility — almost no hackathon team shows this.

## Step 7.7 — Limitations panel (ETH-7)
A visible panel stating: assumed serial interval, segment weight basis, per-language embedding quality, replay compression.

**Why:** volunteering limitations before being asked is the single cheapest credibility move available, and it defuses your three hardest questions pre-emptively.

---

# PHASE 8 — Guardrails Verification
**Duration: 2 hours. Owner: whoever is least blocked. Do not skip.**

| Check | Method | Requirement |
|---|---|---|
| No URLs/numbers in any post | Regex sweep over `posts` | FR-4.6 |
| No named communities/districts | Blocklist sweep | FR-4.7 |
| No PII in `reports` | Regex sweep | NFR-3.1 |
| No reproducible scam script | Manual read of 20 random posts | FR-4.6 |
| Rate limit holds | Query max posts per segment per sim week | FR-4.10 |
| Provenance present | Assert no post with count < MIN_REPORTS | FR-4.9 |
| No runtime egress | **Run full pipeline with networking disabled** | NFR-3.2, CON-1 |

**Run the networking-off test at least a day before the demo.** Some libraries phone home on model load even with cached weights, and discovering that on the morning of is a bad day.

---

# PHASE 9 — Integration and Acceptance
**Duration: 3–4 hours. Everyone.**

Walk the SRS §9 acceptance list, all ten, checking each explicitly:

1. `/init` runs autonomously ≥60 min unattended
2. Feed newest-first, unique IDs, ISO 8601 UTC, restart-safe
3. Full pipeline runs with networking disabled
4. Tree renders and animates, compression ratio visible throughout
5. Rt with credible intervals; alerts only on lower bound > 1
6. Backtest over ≥8 waves, reproducible from fixed seed
7. Every post has both layers and a supporting count, passes validator
8. No post contains URL, number, script, or named community
9. Trace view live
10. **Pipeline runs with `MODEL_MODE=stub` and empty `models/`**

Item 10 is your fallback demo. Confirm it actually works, on a second machine.

---

# PHASE 10 — Rehearsal
**Duration: 2 hours.**

## Step 10.1 — Run the 3-minute script
Per SUMMARY §10: hook → gap → live replay → Rt fires → feed post appears → backtest proof. Time it. Run it three times.

## Step 10.2 — Failure drills
Rehearse: generator dead (templates take over), model won't load (stub mode), replay desync (seek to a known-good timestamp), laptop swap (second machine runs it).

## Step 10.3 — Q&A drill
Each person answers the SUMMARY §7 table cold. The four you will definitely get:
- *"Isn't this already solved?"* → detection vs. targeting-and-timing
- *"Is this real epidemiology?"* → Rt from arrival times, ranks acceleration, doesn't forecast counts
- *"Half of victims don't report — doesn't that break it?"* → weighted; Rt uses rate, robust to roughly-constant under-reporting; state the step-change limitation
- *"What stops this being a scam tutorial?"* → weakened dose, deterministic validator, no public targeting, review gate

## Step 10.4 — Freeze
Tag the release. Snapshot the DB and corpus. **Stop adding features.** The last-hour feature is the one that breaks the demo.

---

# Critical Path and Parallelisation

```
Phase 0 (all, 3h)
   ├── Phase 1 Corpus ──── Phase 2 Surveillance ──┐   [Data]
   ├── Phase 3 Clustering ─── Phase 4 Rt ─────────┤   [Modeling]
   ├── Phase 5 Content ───────────────────────────┤   [Content]
   ├── Phase 6 Publisher ─────────────────────────┤   [Backend]
   └── Phase 7 Frontend ──────────────────────────┘   [Frontend]
                                                   Phase 8 → 9 → 10
```

**True critical path:** Phase 1 → 2 → 3 → 4. Corpus collection gates everything, so start it in hour one.

**Unblocking trick:** Backend, Content and Frontend all build against **stub models and synthetic fixtures** from Phase 0, so nobody waits on the corpus. This is the practical payoff of Step 0.4.

---

# Cut Order Under Time Pressure

Cut from the bottom. Decide by looking at this list, not by arguing at 3 a.m.

| Keep rank | Item | Note |
|---|---|---|
| 1 | Autonomous loop + feed API | Literally what's graded. Never cut. |
| 2 | Lineage tree visual | Your differentiator. |
| 3 | Rt + backtest chart | Converts demo into claim. |
| 4 | Guardrails + validator | Cheap; absence is disqualifying. |
| 5 | Review-mode flag | One hour, answers governance outright. |
| 6 | Two-layer content | Degrade to templates if needed. |
| 7 | Trace view | Cut only if not wired in Phase 0. |
| 8 | SIR illustrative panel | Cut freely. Never load-bearing. |
| 9 | Multi-agent orchestration | Cut first. Adds no capability on a local build. |

---

# Standing Risks

| Risk | Trigger | Mitigation | Owner |
|---|---|---|---|
| Vernacular generation quality poor | Native-speaker review fails | Templates as floor (Step 5.1); `template_assisted` flag | Content |
| Model won't load at demo | Hardware/driver issue | `MODEL_MODE=stub` (Step 0.4); second machine tested | Backend |
| Corpus too thin in a language | Step 1.1 stats show gaps | Drop that language from targeting; say so rather than demo noise | Data |
| Embedding quality poor in low-resource languages | Step 3.4 per-language table | Report the gap explicitly; tune thresholds per language | Modeling |
| Rt implementation subtly wrong | Synthetic test fails | Write the synthetic-recovery test **before** the real one (Step 4.2) | Modeling |
| Generation stalls the replay loop | Tree animation stutters | Async worker queue (Step 5.7) | Backend |
| Library phones home on load | Networking-off test fails | Test in Phase 8, a day early | All |

---

# Open Issues — Resolution Deadlines

| # | Issue | Resolve by |
|---|---|---|
| 1 | Serial-interval prior assumed → run sensitivity sweep | Step 4.3, before backtest is shown |
| 2 | Segment weights lack empirical basis → choose uniform-and-state, or derive-and-cite | Step 2.5, before any Rt claim |
| 3 | Per-language threshold tuning may lack data in low-resource languages | Step 3.4, before tree is demoed |
| 4 | "Widely reported" reference timestamp needs a written definition | Step 1.4, before backtest is built |
| 5 | Vernacular output unvalidated by native speakers | Step 5.1, before any vernacular post is shown |
