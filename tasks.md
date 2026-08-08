# OutbreakShield — Task Tracker

Tracks progress against the 11 phases in `IMPLEMENTATION_PLAN.md`, cross-referenced to
requirement IDs in `SRS.md`. **Update this file whenever a task's status changes** —
do not let it drift out of sync with the actual repo state. Before starting new work,
read this file first to see what's already done and what's next; before marking
anything done, re-read `docs.md` §8 for what "done" requires.

Status legend: `[x]` done and verified · `[~]` in progress / partially done ·
`[ ]` not started

Last updated: 2026-08-08 (after Phase 1: synthetic corpus generation + labels).

---

## PHASE 0 — Foundation

**Status: [~] Scaffolded, not fully verified against every plan requirement.**

| Step | Task | Status | Notes |
|---|---|---|---|
| 0.1 | Repository skeleton | [x] | `config/`, `data/`, `models/`, `src/{interfaces,stage1..5,trace,db,api}/`, `frontend/`, `scripts/`, `tests/` all created. Every `src/stageN_*` has `__init__.py` and `cli.py`. |
| 0.2 | Config files with defaults | [x] | `config/model.yaml`, `config/segments.yaml`, `config/runtime.yaml` populated with plan defaults. `src/config.py::load_config()` reads all three and raises on missing keys. |
| 0.3 | SQLite schema | [x] | All 8 tables in `src/db/schema.sql`; `python -m src.db.init` is idempotent (verified — ran twice, no error). |
| 0.4 | Model interfaces + stubs | [x] | `Embedder`/`Generator` ABCs with `StubEmbedder`/`StubGenerator` in `src/interfaces/`. `LocalEmbedder`/`LocalGenerator` are stub classes that raise `NotImplementedError` — **real implementations not started**. `MODEL_MODE` env var selects via `src/interfaces/factory.py`. Verified: full test suite passes with `MODEL_MODE=stub` and no weights present. |
| 0.5 | Trace helper | [x] | `src/trace/trace.py::trace()` context manager, writes to `traces` table. **Not yet wired into any stage** — no stage code exists yet to call it from. |

**Gaps / not done in Phase 0:**
- [ ] `tree -L 2` verification not run against an approved reference — layout matches the plan by inspection only.
- [ ] No CI configured yet to run `MODEL_MODE=stub` pipeline automatically (deployment gate, see `docs.md` §3).

---

## PHASE 1 — Corpus Collection

**Status: [~] Synthetic corpus meeting all four quantitative gates, generated and ingested. This is deliberately NOT real collected data** — real bulk scraping of scam-report forums/complaint boards isn't feasible in this environment (no bulk-scraping tooling, and handling real unvetted personal complaint data at scale sits uncomfortably against CON-4/NFR-3.1's spirit). `scripts/generate_corpus.py` produces a large, clearly-labelled synthetic corpus so Phases 2–6 can be exercised meaningfully now; real-world collection remains a genuine follow-up, not done this session. Never marked `[x]` for that reason.

| Step | Task | Status | Notes |
|---|---|---|---|
| 1.1 | Source selection (≥3,000 reports, ≥6 months, ≥3 languages, ≥1 high-value variant e.g. digital arrest/investment/deepfake) | [x]* | `scripts/generate_corpus.py` (seed `20260101`, deterministic) generates 4 scam families — `authority_impersonation`, `refund_inversion`, `digital_arrest`, `investment_deepfake` (the latter two are the explicit high-value-variant coverage requirement) — across 3 languages (hi/en/ta) via template+slot substitution, spanning 2026-01-01 to 2026-07-29 (~6.9 months). **Verified**: `scripts/corpus_stats.py` on the ingested DB shows 3,626 total reports, all 3 languages non-empty (en 1348, ta 1156, hi 1122), all 4 region tiers non-empty (tier2 1397, metro 1175, tier3 694, rural 360). `*` = synthetic, see status note above. |
| 1.2 | Timestamps (seeded jitter for date-only records) | [x] | No new logic needed — the generator emits bare dates and `src/stage1_surveillance/normalize.py::_parse_timestamp` (already implemented, Phase 2) applies its existing seeded-by-id jitter automatically at ingestion. |
| 1.3 | PII redaction at ingestion | [x] | New dedicated script `scripts/verify_pii_redaction.py` sweeps `reports.text` with the same regex patterns `src/stage1_surveillance/pii.py` uses. **Verified with a real positive control**: the generator deliberately injected 26 reports containing fake phone/email/URL/account-number patterns (tracked in `data/corpus/gen_manifest.json`); post-ingest sweep found zero surviving matches across all 5 pattern types — proving redaction actually caught real cases, not just finding an already-empty haystack. |
| 1.4 | Labelled subsets (clustering ≥200, backtest ≥8 waves, "widely reported" definition written down) | [~] | New script `scripts/generate_labels.py` produces `data/labels/clustering.csv` (300 rows, stratified across all 4 families × 3 languages, **verified** every `report_id` resolves against `reports.id` post-ingest) and `data/labels/wave_ground_truth.csv` (10 waves — exceeds the ≥8 floor — with exact generator-controlled `true_acceleration_date` per wave, **verified** all 3,600 referenced `report_id`s resolve against the DB with zero orphans). **`data/labels/backtest.csv` intentionally NOT produced** — see the design note below; this is the one sub-item still open. |

**Design note — the `backtest.csv` gap:** `src/stage3_rt/backtest.py` expects `data/labels/backtest.csv` keyed by `variant_id`, a lineage UUID that only exists after Stage 2 clustering runs. Under `MODEL_MODE=stub` (the only mode implemented — `LocalEmbedder` is still `NotImplementedError`), clustering is not semantically meaningful (every syntactically-unique text becomes its own singleton lineage, confirmed empirically). A `variant_id`-keyed label file can't be produced honestly until Phase 3.1 lands a real embedding model. `wave_ground_truth.csv` is Phase 1.4's actual backtest-set deliverable in `variant_id`-independent form; a named-but-not-built follow-up script, `scripts/build_backtest_labels.py`, will join it against real `lineage_members` once Phase 3.1 exists, to produce the real `backtest.csv`. `src/stage3_rt/backtest.py`'s docstring already records the "widely reported" reference-timestamp definition (3x trailing-14-day-median) required by this step — `wave_ground_truth.csv`'s `true_acceleration_date` gives an independent ground-truth to check that auto-computed proxy against, once real lineages exist.

**New files this phase:** `scripts/generate_corpus.py`, `scripts/generate_labels.py`, `scripts/verify_pii_redaction.py` (all new); `config/segments.yaml` (added `ta` to the languages list); `scripts/corpus_stats.py` and `scripts/backtest.py` also got a small unrelated bugfix — both were missing a `sys.path` bootstrap needed to import `src.*` when run directly as `python scripts/foo.py` (discovered while running verification step 5; harmless, no application logic changed).

**Reproducing this corpus:** `rm data/outbreakshield.db*; python -m src.db.init; python scripts/generate_corpus.py; python scripts/generate_labels.py; python -m src.stage1_surveillance.cli ingest`. `scripts/generate_sample_corpus.py` (the tiny 124-record smoke-test fixture from the backend session) is untouched and still available separately for fast iteration.

**Blocking:** Phase 3.1 (real local embedding model) is now the actual remaining blocker for making Stage 2/3 results *semantically* meaningful — Phase 2 (Surveillance) is no longer blocked (real mechanics now run against 3,626 real-shaped rows instead of 11), and Phase 3/4's *mechanics* (not their real-world validity) can now be exercised at realistic scale.

---

## PHASE 2 — Stage 1: Surveillance

**Status: [x] Logic implemented and verified at real scale.** `src/stage1_surveillance/cli.py` `ingest` and `replay` are wired to real implementations. **No longer blocked on Phase 1** — Phase 1's synthetic corpus (3,626 reports, ~6.9 months, 3 languages) is ingested and persisted in the current DB, not a throwaway fixture. Genuinely real-world data collection is still a separate, unstarted follow-up (see Phase 1's status note) — but Stage 1's own mechanics are now proven at realistic volume, not just against the earlier 11/124-record smoke fixtures.

| Step | Task | FR IDs | Status |
|---|---|---|---|
| 2.1 | Normaliser (raw → `reports` schema, reject malformed loudly) | FR-1.2 | [x] `src/stage1_surveillance/normalize.py::normalise_record`. Malformed records go to `data/corpus/rejects.jsonl` with a reason, never silently dropped. Verified: ingest run against synthetic corpus produced 0 unexpected rejects. |
| 2.2 | Deduplication (hash on normalised text, keep earliest timestamp, increment `dup_count`, never discard) | FR-1.3 | [x] `normalize.py::normalised_text_hash` + `repo.insert_report`. Verified against synthetic corpus (113/124 correctly deduped by exact-text hash). **Known limitation:** duplicates only retain the *earliest* timestamp (per FR-1.3's literal schema), so a message that keeps reappearing over time contributes all of its `dup_count` mass to the first-seen day in the Rt incidence series rather than being spread across its true arrival dates — see Stage 3 note below. |
| 2.3 | Language detection (local only, below-confidence → `unknown`) | FR-1.4 | [x] `src/stage1_surveillance/language.py` — **placeholder heuristic** (Devanagari-vs-Latin character ratio), not a validated model. Flagged in `docs.md`/SRS as the top vernacular-quality risk (DR-4); swap for a real local language-ID model before any real vernacular claim is made. |
| 2.4 | Segment assignment (`region_tier:language`) | FR-1.5 | [x] Done inside `normalise_record`. |
| 2.5 | Reporting-propensity weights (`config/segments.yaml`, default 1.0, decide uniform-vs-derived and state it) | FR-1.6 | [x] Weighting applied at Rt-estimation time (`src/stage3_rt/weighting.py::get_segment_weight`), not at ingestion — kept the raw report always recoverable. **Open Issue 2 still open**: weights remain uniform (1.0); no survey-derived weights have been cited yet. |
| 2.6 | Replay harness (compressed timeline, pause/resume/seek, `simulated_now`) | FR-1.7, FR-1.8, FR-1.9 | [x] `src/stage1_surveillance/replay.py::ReplayClock`. Pause/resume/seek all implemented and exercised via `/replay/*` endpoints. Verified: ran a full synthetic-corpus replay end-to-end via `TestClient` with idempotent `/init`, confirmed `simulated_now` advanced and `reports_replayed` reached the corpus total with no errors. `simulated_now`/compression ratio are exposed continuously via `GET /status` (ETH-6 — not yet rendered in frontend, see Phase 7). |

---

## PHASE 3 — Stage 2: Lineage Clustering

**Status: [~] Clustering mechanics fully implemented and wired; real embedding model not started.** Corpus and labelled data are no longer the blocker (Phase 1 delivered both, synthetically) — **Phase 3.1 (a real local embedding model) is now the sole remaining blocker** for this phase meaning anything semantically. This is the primary demo differentiator — do not let it slip once 3.1 lands.

| Step | Task | FR IDs | Status |
|---|---|---|---|
| 3.1 | Local embedding model (select on Indic coverage, verify offline load) | FR-2.1, IF-1 | [ ] `LocalEmbedder` in `src/interfaces/embedder.py` is still a stub that raises `NotImplementedError`. All clustering currently runs on `StubEmbedder` (deterministic hash-based vectors) — **structurally correct but not semantically meaningful**: two different phrasings of the same scam will not cluster together under the stub, only exact-duplicate text will. This is expected/by-design for `MODEL_MODE=stub` and was confirmed directly in this session's smoke test (11 unique synthetic reports → 11 singleton lineages, zero false merges). |
| 3.2 | Vector persistence (`embeddings` table + in-memory index) | FR-2.2 | [x] `repo.upsert_embedding`/`get_embedding`, brute-force cosine via `src/stage2_lineage/similarity.py` (adequate at demo/hackathon scale per the plan; revisit only if `NFR-1.2` starts to slip). |
| 3.3 | Incremental clustering assignment (member / mutation / new-root) | FR-2.3 | [x] `src/stage2_lineage/cluster.py::assign_report` + `process_reports`. Idempotency guard added beyond the original spec: `repo.filter_already_clustered` skips reports that already have a `lineage_members` row, so re-running clustering (e.g. after a restart) never double-assigns — verified via the loop smoke test (11 already-clustered reports fed back through the loop produced zero new lineage rows). |
| 3.4 | Threshold tuning (`scripts/tune_thresholds.py`, per-language precision/recall) | FR-2.4, DR-4 | [ ] Script still scaffolded/`NotImplementedError`. The ≥200-report labelled clustering set it needs now **exists** (`data/labels/clustering.csv`, 300 rows, Phase 1.4) — the remaining blocker is Phase 3.1: tuning `THRESH_MEMBER`/`THRESH_MUTATION` against `StubEmbedder`'s semantically-meaningless hash vectors wouldn't produce a real answer, only a number. Ready to implement the moment a real embedding model exists. |
| 3.5 | Incremental centroids (running mean, never full recompute) | FR-2.7 | [x] `repo.update_lineage_after_member_add` — running mean computed in `cluster.py::_apply_decision`, no full recompute path exists. |
| 3.6 | Lineage labelling (async, fallback `variant-<short_id>`) | FR-2.8 | [~] `src/stage2_lineage/labeling.py::generate_label` implemented with try/except fallback to `variant-<short_id>` on any generator failure — **runs synchronously inline in the clustering path, not on a separate async path**. Acceptable today because `StubGenerator` is instant; will need to move off the critical path once `LocalGenerator` (real, ~seconds-latency) is wired in Phase 5, per NFR-1.4's async requirement. Tracked as a gap, not forgotten. |
| 3.7 | Tree export (`GET /lineages`) | FR-2.6 | [x] `src/stage2_lineage/tree.py::build_forest` + wired into `GET /lineages`. Verified: no orphan `parent_id` references possible by construction (nodes are keyed by `variant_id`; anything whose parent isn't in the node map is treated as a root). |

---

## PHASE 4 — Stage 3: Rt Modeling

**Status: [x] Core estimator, gating, ranking, and backtest harness fully implemented, tested, and wired.** The synthetic-recovery test was written and passing before anything else was allowed to depend on this module, per the plan's explicit instruction.

| Step | Task | FR IDs | Status |
|---|---|---|---|
| 4.1 | Weighted arrival series | — | [x] `src/stage3_rt/estimation.py::build_daily_incidence` — daily bins weighted by `dup_count * get_segment_weight(segment_id)`. **Known limitation** (inherited from FR-1.3's schema, see Phase 2.2 note): duplicate reports contribute their full weight to the *earliest* day seen, not their true recurrence dates, so a message that keeps resurfacing looks like a single early spike rather than sustained/growing incidence. Worth revisiting once real corpus data shows whether this materially affects lead time. |
| 4.2 | Renewal-equation Rt (own NumPy/SciPy implementation, synthetic-data test written **first**) | FR-3.1, FR-3.2, DR-1 | [x] `src/stage3_rt/renewal.py` — Cori et al. discretised-serial-interval / Gamma-Poisson posterior, implemented from scratch (no external stats service, per CON-1/docs.md §2). `tests/unit/test_renewal.py` (4 tests, **written and passing before** `estimation.py`/`ranking.py`/`backtest.py` were built on top of it): synthetic growing epidemic (R=1.8) recovers a credible interval covering the true value and correctly gates `rt_lower > 1.0`; synthetic declining epidemic (R=0.6) does not falsely read as growth; insufficient-history and serial-interval-normalisation edge cases covered. |
| 4.3 | Serial-interval sensitivity sweep (1.5–4 days), lead-time table in README | Open Issue 1 | [ ] Not started. Wave ground truth now exists (`data/labels/wave_ground_truth.csv`, 10 waves, Phase 1.4) but isn't yet joinable into `backtest.py`'s `variant_id`-keyed format — blocked on Phase 3.1, same as Phase 3.4, not on Phase 1 anymore. |
| 4.4 | Alert gating on `rt_lower > 1.0` and `n_reports >= MIN_REPORTS` | FR-3.5, FR-3.6, DR-2 | [x] `estimation.py::estimate_lineage_rt` — gates on the **lower bound**, never the point estimate, exactly per DR-2. Every lineage gets an estimate row every call (even `INSUFFICIENT_DATA`) so the Rt-over-time panel (FR-7.2) has a continuous series once the frontend is wired. |
| 4.5 | Ranking + target-segment selection (no duplicate inoculation per segment/variant) | FR-3.7, FR-3.8 | [x] `src/stage3_rt/ranking.py::rank_lineages` (sorted by `rt_lower` desc) and `select_target_segment` (highest-report-count segment in the lineage that `repo.segment_already_has_post_for_variant` says hasn't been targeted yet). |
| 4.6 | Backtest harness (`scripts/backtest.py`, lead time + coverage + false-alarm count, fixed-seed reproducibility) | FR-3.10, FR-3.11, NFR-4.3 | [x] `src/stage3_rt/backtest.py::run_backtest`. **Resolves Open Issue 4** with a concrete, documented default: "widely reported" = first day raw volume exceeds 3x its trailing 14-day median (auto-computed from `reports`/`lineage_members`, no hand-labelled data required to run). If `data/labels/backtest.csv` exists, its hand-labelled reference timestamps take priority per-wave. Purely a deterministic read over persisted state — reproducible by construction (no randomness in the function itself). Verified via smoke test: correctly returned an empty, well-typed result (`n_waves: 0`) against data too thin to have any major wave, rather than erroring. `scripts/backtest.py` is now a thin wrapper calling the same function (also reachable via `python -m src.stage3_rt.cli backtest` or `GET /backtest`). |

---

## PHASE 5 — Stage 4: Inoculation Content

**Status: [~] Orchestration, validator, fallback, rate-limit and provenance gates all implemented and smoke-tested. Two real gaps remain: template coverage is minimal (2 techniques, not native-speaker-reviewed) and generation is fully synchronous (fine under the stub, a real blocker once `LocalGenerator` lands).**

| Step | Task | FR IDs | Status |
|---|---|---|---|
| 5.1 | Per-(technique × language) templates, native-speaker reviewed | FR-4.4, DR-5 | [~] `src/stage4_content/templates/` now has 4 real templates: `authority_impersonation.{en,hi}.yaml` and `refund_inversion.{en,hi}.yaml`, loaded via `templates.py::load_template`/`fill_template`. **Not yet native-speaker reviewed** (ETH-7 gap — the Hindi text was written by the assistant, not validated) and only 2 of the techniques listed in SRS §3.4 (isolation from family, screen-share coercion still uncovered). `templates.py::infer_technique` picks a technique via a crude keyword heuristic over the lineage's report text — explicitly flagged in its docstring as an unvalidated placeholder, same caveat class as language detection (Phase 2.3). |
| 5.2 | Local generator setup (Ollama/llama.cpp, `127.0.0.1`, offline-verified) | IF-2 | [ ] `LocalGenerator` in `src/interfaces/generator.py` is still a stub that raises `NotImplementedError`. All generation currently runs on `StubGenerator`, which always returns one fixed, valid English post regardless of prompt — sufficient to prove the orchestration wiring (validator/fallback/rate-limit/provenance all confirmed working around it) but **proves nothing about real content quality**. |
| 5.3 | Two-layer prompt (technique + variant, hard constraints in prompt) | FR-4.2 | [x] `src/stage4_content/generate.py::_PROMPT_TEMPLATE` + `_HARD_CONSTRAINTS` — asks for both layers plus JSON output; hard constraints (no URL/phone/account/QR, no verbatim script, no named community) stated explicitly in the prompt. Per docs.md §4, these prompt constraints are treated as advisory only — FR-4.8's validator is the actual enforcement, not this text. |
| 5.4 | Deterministic output validator | FR-4.6, FR-4.8 | [x] Unchanged from Phase 0 scaffold: `src/stage4_content/validator.py`, 5 tests passing. **`DEMOGRAPHIC_BLOCKLIST` is still intentionally empty — this remains a release blocker per docs.md §4/§8, not resolved this session.** |
| 5.5 | Fallback path (template on failure/timeout, `template_assisted: true`) | FR-4.4 | [x] `generate.py::_try_free_generation` (retries up to `MAX_RETRIES`, validates every candidate) falls through to `_fallback_template` on exhaustion; `generate_content_for_lineage` returns `template_assisted` accurately either way. **Directly verified this session**: forced the generator to return invalid output and confirmed the result came back `ok=True, template_assisted=True` with real Hindi template content loaded. No timeout enforcement yet — `config/runtime.yaml`'s `generation.timeout_seconds` is declared but unused, since `StubGenerator` returns instantly; needs a real timeout wrapper once `LocalGenerator` (Phase 5.2) can actually hang. |
| 5.6 | Provenance + rate limiting | FR-4.9, FR-4.10 | [x] `generate.py::check_provenance` (lineage `report_count >= MIN_REPORTS`) and `check_rate_limit` (posts per segment in trailing 7 simulated days, via `repo.count_posts_for_segment_in_window`). **Directly verified this session**: a singleton (1-report) lineage was correctly rejected by `check_provenance` before any generation was attempted. |
| 5.7 | Async execution off the replay loop | NFR-1.4 | [ ] **Not done — currently synchronous inline in the publisher loop tick** (`stage5_publisher/loop.py::_publish_or_queue` calls `generate_content_for_lineage` directly). Harmless today because `StubGenerator` is instant, but this is a real correctness gap against NFR-1.4 the moment `LocalGenerator` is wired in — a 15s generation call would stall the tick loop (and, once the frontend is live, visibly stutter the lineage tree animation per the plan's explicit warning). Needs a worker queue before Phase 5.2 ships for real. |

---

## PHASE 6 — Stage 5: Publisher and API

**Status: [~] Loop, persistence, review mode, and every API route are implemented and wired to real logic — verified via a live `TestClient` run this session. Two things are explicitly not yet proven: a real `SIGKILL` restart test, and a 60-minute unattended run (only a few seconds of wall-clock loop time was observed). This is P0 — literally what's graded/deployed on, treat the two open items as the top priority for the next session.**

| Step | Task | FR IDs | Status |
|---|---|---|---|
| 6.1 | `POST /init` (idempotent background loop) | FR-5.1, FR-5.2 | [x] `src/stage5_publisher/loop.py::PublisherLoop.start`, wired via `service.init_loop` → `POST /init`. **Directly verified this session**: called `/init` twice in a row — first call returned `{"started": true}` and spawned the thread; second call while running returned `{"started": false, "already_running": true}` with no duplicate thread and no duplicate lineage/post rows. |
| 6.2 | Loop body (tick: replay → ingest → embed → cluster → Rt → escalation check → generate → publish, each traced) | — | [x] `PublisherLoop._run_tick`: pulls due reports from the replay clock, clusters only those (idempotency-guarded, see Phase 3.3), re-estimates Rt for every lineage, iterates escalating lineages checking provenance/target-segment/rate-limit before generating+persisting. Every substep wrapped in `trace(...)`. **Verified this session** via a compressed-timeline `TestClient` run: `tick_count` advanced, `reports_replayed` reached the corpus total, `last_error` stayed `None` throughout. |
| 6.3 | Post schema + feed (newest-first, unique ID, ISO 8601 UTC, `limit`/`since`) | FR-5.3, FR-5.4, FR-5.6 | [x] `repo.insert_post`/`get_feed`, `GET /feed` supports `limit`/`since`. IDs are `uuid4`, timestamps forced through the `%Y-%m-%dT%H:%M:%SZ` format everywhere in the repository layer. **Not yet exercised with an actual published post** in this session's smoke test (the synthetic stub-embedding corpus never produced an escalating lineage — see Phase 3/4 notes) — feed ordering/uniqueness logic is implemented and unit-reasoned but wants a real multi-post verification pass once real embeddings exist. |
| 6.4 | Persistence + restart safety (`SIGKILL` test) | FR-5.5, NFR-2.2 | [~] All state is SQLite-backed (WAL mode) and clustering/posting are idempotency-guarded so a naive re-run can't duplicate work. **However, a real `SIGKILL` test has not been run** — and there's a known, honest gap: `ReplayClock` keeps its cursor/elapsed-time state only in memory, so after a hard kill and process restart, replay resumes from the beginning of the corpus rather than where it left off. This is safe (no duplicate posts/lineages, per the DB-level guards) but means the simulated-date display would visibly jump backward on restart — worth deciding whether to persist clock state via `loop_state` before this ships. Flagging explicitly rather than silently calling this "done." |
| 6.5 | Review mode (`AUTO_PUBLISH=false`, `/review` endpoints) | FR-5.7, FR-5.8, DR-7 | [x] `loop.py` stores `_auto_publish` and writes posts with `state='queued'` instead of `'published'` when false; `service.approve_post`/`reject_post` transition `queued → published/rejected` with an `approved_by` tag. Mode is echoed in `GET /status`. **Not yet exercised in review mode specifically** in this session's smoke test (only ran with `auto_publish=True`) — logic is symmetric and code-reviewed but wants a dedicated run. |
| 6.6 | Fault tolerance (log + abandon tick + continue, 60-min unattended test) | FR-5.10, NFR-2.1 | [~] `PublisherLoop._run` wraps each tick in try/except, logs to `traces` via `trace("stage5_publisher", "tick_error")`, and continues to the next tick rather than dying. **The 60-minute unattended run required by NFR-2.1 has not been performed** — only a few seconds were observed this session. This is a real open item, not a formality; schedule it before any deploy per docs.md §7. |
| 6.7 | `/status` and `/trace` | FR-5.9, FR-6.2 | [x] `service.get_status()` returns every field FR-5.9 lists (loop running, mode, simulated date, compression ratio, lineage count, escalating count, posts published); `GET /trace` returns recent trace rows. Both **directly verified this session** via `TestClient`. |

---

## PHASE 7 — Frontend

**Status: [~] All six required views scaffolded as static placeholder components with correct props/structure intent; no live data wiring, no D3/Recharts implementation yet.**

| Step | Task | FR IDs | Status |
|---|---|---|---|
| 7.1 | Lineage tree (D3, sized/coloured by Rt status, animates) | FR-7.1 | [ ] `frontend/src/components/LineageTree.tsx` is a placeholder. **Primary demo asset — build first when this phase starts.** |
| 7.2 | Status bar (sim date, compression ratio, mode, loop state) | FR-7.5, ETH-6 | [ ] `StatusBar.tsx` is a static placeholder with no data binding. |
| 7.3 | Rt panel (credible-interval band, Rt=1 line) | FR-7.2 | [ ] `RtPanel.tsx` placeholder. |
| 7.4 | Backtest chart | FR-7.3 | [ ] `BacktestChart.tsx` placeholder. |
| 7.5 | Feed view (both layers, `template_assisted` badge) | FR-7.4 | [ ] `Feed.tsx` placeholder. |
| 7.6 | Trace view | FR-7.6 | [ ] `TraceView.tsx` placeholder. |
| 7.7 | Limitations panel | ETH-7 | [~] `LimitationsPanel.tsx` has static text matching `docs.md` §5 — needs to become data-driven from actual config values rather than hardcoded strings. |

`frontend/src/lib/api.ts` has a typed client for all `GET` endpoints — not yet used by any component (all components are static placeholders).

---

## PHASE 8 — Guardrails Verification

**Status: [ ] Not started — cannot run meaningfully until Phases 1–6 produce real `reports`/`posts` data.**

| Check | Method | Requirement | Status |
|---|---|---|---|
| No URLs/numbers in any post | Regex sweep over `posts` | FR-4.6 | [~] Validator is unit-tested (5 tests) and is now on the actual publish path (every post from `generate_content_for_lineage` is validated before it can be returned) — but a sweep over a real, non-trivial `posts` table hasn't been run since no real corpus has produced escalating lineages yet. |
| No named communities/districts | Blocklist sweep | FR-4.7 | [ ] Blocklist is still empty — **unchanged from Phase 0, still a release blocker per docs.md §4.** |
| No PII in `reports` | Regex sweep | NFR-3.1 | [ ] |
| No reproducible scam script | Manual read of 20 random posts | FR-4.6 | [ ] |
| Rate limit holds | Query max posts per segment per sim week | FR-4.10 | [ ] |
| Provenance present | Assert no post with count < `MIN_REPORTS` | FR-4.9 | [ ] |
| No runtime egress | Full pipeline run with networking disabled | NFR-3.2, CON-1 | [ ] **Run this at least a day before any deploy, per `docs.md` §2 — not on the day of.** |

---

## PHASE 9 — Integration and Acceptance

**Status: [ ] Not started.** SRS §9 acceptance criteria, tracked here 1:1:

| # | Criterion | Status |
|---|---|---|
| 1 | `/init` runs autonomously ≥60 min unattended | [ ] |
| 2 | Feed newest-first, unique IDs, ISO 8601 UTC, restart-safe | [ ] |
| 3 | Full pipeline runs with networking disabled | [ ] |
| 4 | Lineage tree renders/animates, compression ratio visible throughout | [ ] |
| 5 | Rt with credible intervals; alerts only on lower bound > 1 | [ ] |
| 6 | Backtest over ≥8 waves, reproducible from fixed seed | [ ] |
| 7 | Every post has both layers + supporting count, passes validator | [ ] |
| 8 | No post contains URL, number, script, or named community | [ ] |
| 9 | Trace view live | [ ] |
| 10 | Pipeline runs with `MODEL_MODE=stub` and empty `models/` | [x] **Now verified end-to-end**, not just at scaffold level: with `models/` empty, ran ingest → cluster → Rt estimate → backtest via CLI, then a full `TestClient` session driving `/init` (with idempotency check) through a compressed replay to completion, exercising `/status`, `/lineages`, `/feed`, `/trace`, `/backtest`, `/review` — zero exceptions, `last_error` stayed `None` throughout. Re-run this check after any change to the interfaces layer or the loop. |

---

## PHASE 10 — Rehearsal

**Status: [ ] Not started.** Depends on Phases 1–9 being functionally complete.

| Step | Task | Status |
|---|---|---|
| 10.1 | Run the 3-minute demo script three times, timed | [ ] |
| 10.2 | Failure drills (generator dead, model won't load, replay desync, laptop swap) | [ ] |
| 10.3 | Q&A drill (SUMMARY §7 table, cold) | [ ] |
| 10.4 | Freeze: tag release, snapshot DB/corpus, stop adding features | [ ] |

---

## Cross-cutting items not tied to a single phase

| Item | Status | Notes |
|---|---|---|
| `docs.md` hard-rules file | [x] | Created in the scaffolding session. Encodes CON-1..4, ETH-1..7, FR-4.x guardrails, DR decisions, and NFR reliability rules as binding constraints. Re-checked this session — no rule violated by the backend implementation (verified: no network calls beyond the local generator/embedder interfaces which are still stubs; guardrail validator sits on every generation path; rate limit and provenance gates are enforced in code, not just prompted for). |
| `tasks.md` (this file) | [x] | Kept current this session — every phase table above reflects real, individually-verified implementation state, not aspirational status. |
| Repository layer (`src/db/repository.py`) | [x] | Added this session — not called out as its own phase in `IMPLEMENTATION_PLAN.md` but was a necessary foundation every stage depends on. All reads/writes for `reports`, `embeddings`, `lineages`, `lineage_members`, `rt_estimates`, `posts`, `traces`, `loop_state` go through it; no stage writes raw SQL directly. |
| `scripts/generate_sample_corpus.py` | [x] | Small (124-record) dev tool from the backend session: deterministic synthetic-corpus generator for fast local smoke-testing. Left untouched — still useful for quick iteration separately from Phase 1's larger corpus. |
| `scripts/generate_corpus.py` / `generate_labels.py` / `verify_pii_redaction.py` | [x] | Added this session for Phase 1 — see Phase 1's table above for full detail. All three explicitly document (in their own docstrings) that the corpus they produce is synthetic, not real collected data. |
| CI wiring for `MODEL_MODE=stub` pipeline | [ ] | Still not set up. Should run `pytest` plus a `TestClient`-based `/init` smoke test (the same one performed manually in the backend session) on every change before deploy. |
| Native-speaker review of vernacular content | [ ] | Blocked on Phase 5 templates existing — they now exist (2 techniques × 2 languages) but are **unreviewed**; the Hindi text was written by the assistant, not validated by a speaker. |
| `data/labels/` "widely reported" definition write-up | [x] | Resolved differently than originally planned: instead of only a written definition awaiting hand-labelled data, `src/stage3_rt/backtest.py` implements the definition (3x trailing-14-day-median) as executable, auto-computed logic that works with zero hand-labelled input, and defers to `data/labels/backtest.csv` when it exists. The definition is documented in that module's docstring. |
| **New gap: async generation (NFR-1.4)** | [ ] | `stage5_publisher/loop.py` calls content generation synchronously inline in the tick. Harmless under `StubGenerator`; will violate NFR-1.4 the moment `LocalGenerator` is real. See Phase 5.7. |
| **New gap: demographic blocklist (FR-4.7)** | [ ] | `src/stage4_content/validator.py::DEMOGRAPHIC_BLOCKLIST` is still empty. Release blocker per docs.md §4/§8 — content cannot be trusted to satisfy FR-4.7 until this has real terms in it. |
| **New gap: ReplayClock state not persisted across restart** | [ ] | See Phase 6.4. Not a duplication/correctness risk (DB-level idempotency guards hold), but the simulated-date display would jump backward after a hard restart. Decide whether to persist clock state in `loop_state` before deploy. |
| **New gap: no real `SIGKILL` / 60-minute unattended test yet** | [ ] | See Phase 6.4/6.6. Both are explicit SRS acceptance criteria (NFR-2.1, NFR-2.2) that have not actually been run, only reasoned about from the code. Top priority for the next session alongside real embeddings. |
| **New: `scripts/build_backtest_labels.py` (named, not built)** | [ ] | Will join `data/labels/wave_ground_truth.csv` against real `lineage_members` once Phase 3.1 lands a real embedding model, to finally produce `data/labels/backtest.csv`. See Phase 1.4's design note. |
| **Fixed this session: `scripts/corpus_stats.py` / `scripts/backtest.py` path bug** | [x] | Both imported `src.*` at module level with no `sys.path` bootstrap, so running them directly (`python scripts/foo.py`) raised `ModuleNotFoundError` — only surfaced now because this was the first session to actually run them standalone rather than via `pytest` or `-m`. Fixed with a `sys.path.insert` guard, same pattern used in the new Phase 1 scripts. No application logic changed. |

---

## What to work on next (recommended order, per critical path)

1. **Populate `DEMOGRAPHIC_BLOCKLIST` (FR-4.7)** and run a real `SIGKILL`-restart test plus a 60-minute unattended loop run (NFR-2.1/2.2) — all three are cheap, all three are explicit release blockers/acceptance criteria that are still open, and none of them require real data to do.
2. **Phase 3.1 — a real local embedding model.** This is now the single biggest unlock in the project: it's the shared blocker for Phase 3.4 (threshold tuning), Phase 4.3 (serial-interval sensitivity sweep), the `backtest.csv`/`scripts/build_backtest_labels.py` gap, and for the 3,626-report synthetic corpus (already ingested and ready) to start clustering *meaningfully* instead of into singleton lineages.
3. **Phase 5.2 — a real local generation model**, alongside moving generation off the tick loop onto an async worker queue first (Phase 5.7, per NFR-1.4) so a real ~15s generation call doesn't stall the loop.
4. **Real-world corpus collection** — Phase 1's synthetic corpus unblocks engineering work but is not a substitute; genuine data collection (per SRS §3.1's source list) remains a real, separate follow-up whenever that becomes feasible.
5. **Phase 7 — real frontend data wiring**, now that every endpoint it needs returns real (not stub) JSON shapes, backed by a realistically-sized corpus.
6. Native-speaker review of the four existing content templates (Phase 5.1) plus writing the remaining technique templates (isolation from family, screen-share coercion) before Phase 5 is considered complete.

Frontend wiring (Phase 7) remains untouched — the backend session's component shells
are ready to be pointed at the now-real API responses, running against a corpus that's
now realistically sized rather than a handful of smoke-test records.
