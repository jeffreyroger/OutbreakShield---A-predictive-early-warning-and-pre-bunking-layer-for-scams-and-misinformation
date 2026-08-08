# Software Requirements Specification
## OutbreakShield — Predictive Scam Early-Warning and Pre-Bunking System

**Version:** 2.0
**Date:** August 2026
**Build constraint:** Fully local. No external AI APIs, no hosted inference, no third-party fraud/detection services. All models run on team-controlled hardware.

---

# 1. Introduction

## 1.1 Purpose

This document specifies the functional and non-functional requirements for OutbreakShield, a system that predicts which population segment a scam variant will reach next and autonomously publishes targeted pre-bunking ("inoculation") content ahead of exposure.

It is written for the implementing team and for evaluators assessing architectural soundness. Every requirement is stated so that its satisfaction is observable.

## 1.2 Scope

OutbreakShield ingests publicly available scam and misinformation reports, clusters them into mutation lineages, estimates per-lineage spread velocity, and autonomously generates and publishes plain-language warnings targeted at the segment predicted to be affected next.

**In scope:** report ingestion, lineage clustering, reproduction-number estimation, inoculation content generation, autonomous publishing, backtest evaluation, observability.

**Explicitly out of scope:** transaction-level fraud classification; account flagging, freezing, or reporting; user identification; any enforcement action; real-time case-count forecasting; integration with banking, telecom, or law-enforcement systems.

The system is a **targeting and timing layer**. It answers *"who should be warned next, when, in what language, about which manipulation technique."* It does not answer *"is this transaction fraudulent."*

## 1.3 Definitions

| Term | Definition |
|---|---|
| **Report** | A single normalised, timestamped account of a scam encounter drawn from a public source. |
| **Lineage / Variant** | A cluster of reports representing one scam family or a mutation thereof. Identified by `variant_id`, linked to a `parent_id`. |
| **Mutation** | A report whose embedding falls outside the acceptance radius of all existing lineages but within the radius of a parent family, triggering creation of a child lineage. |
| **Rt** | Time-varying reproduction number. Estimated per lineage from report arrival times. Rt > 1 indicates accelerating spread. |
| **Segment** | A coarse population bucket: (region tier, language, optional demographic hint). The unit of targeting. |
| **Inoculation / Pre-bunk** | Preventive content delivered before exposure, comprising a technique-level layer and a variant-specific layer. |
| **Weakened dose** | Content describing a manipulation pattern and its defence without providing a reproducible scam script. |
| **Lead time** | Interval between the system's alert timestamp and the timestamp at which the variant became widely reported. |

## 1.4 Local-Build Constraint (governing constraint)

**CON-1.** No component shall make a network call to any hosted model inference endpoint at runtime. All embedding, generation, and clustering computation executes on local hardware.

**CON-2.** Model weights shall be downloaded once during setup and cached locally. The system shall run correctly with networking fully disabled after setup.

**CON-3.** Data ingestion may use the network during the collection phase only. The demonstrated system runs entirely from a local, pre-collected corpus.

**CON-4.** No user-identifying data shall leave the local machine at any point, including during setup.

---

# 2. Overall Description

## 2.1 Product Perspective

OutbreakShield is a self-contained pipeline with five stages and a web frontend. It has no upstream dependency on any external service at runtime. The architecture is deliberately linear with persisted state at each boundary, so that any stage can be demonstrated, tested, or replaced independently.

```
[Sources] → S1 Surveillance → S2 Lineage Clustering → S3 Rt Modeling
                                                            ↓
            Feed API ← S5 Publisher ← S4 Inoculation Generator
                ↓
           Frontend (lineage tree, Rt chart, feed, trace view)
```

## 2.2 Product Functions

1. Ingest and normalise scam reports from a local corpus, replayed on a compressed timeline.
2. Embed reports using a locally hosted multilingual model.
3. Cluster reports into lineages and maintain a mutation tree.
4. Estimate Rt per lineage with confidence intervals.
5. Trigger alerts when a lineage's Rt lower bound exceeds 1.
6. Generate two-layer inoculation content using a locally hosted language model.
7. Autonomously publish to a persisted feed via a documented API.
8. Backtest against historical waves, reporting lead time and coverage.
9. Expose an observability trace of all agent decisions.

## 2.3 User Classes

| Class | Needs |
|---|---|
| **Evaluator / Judge** | Verify the autonomous loop meets spec; interrogate model validity; see evidence of prediction rather than reaction. |
| **Operator (review mode)** | Inspect queued inoculations, approve or reject before publication. |
| **End reader** | Receive plain-language, vernacular, actionable warnings. Assumed low digital literacy. |
| **Developer** | Run, test, and extend the pipeline offline. |

## 2.4 Operating Environment

- **OS:** Linux or macOS. Windows via WSL2.
- **Runtime:** Python 3.11+, Node 20+ (frontend only).
- **Hardware (minimum):** 16 GB RAM, 8-core CPU. Runs with a quantised 7–8B generation model at reduced throughput.
- **Hardware (recommended):** 32 GB RAM, GPU with ≥12 GB VRAM. Required for acceptable generation latency during a live demo.
- **Storage:** ≤20 GB including model weights and corpus.
- **Network:** Required for one-time setup only.

## 2.5 Design Constraints and Assumptions

**Assumptions:**
- A historical corpus of ≥3,000 reports spanning ≥6 months, covering ≥3 languages, is collected before build.
- Reports carry, or permit inference of, a timestamp and a coarse region/language label.
- Under-reporting is approximately constant within a segment over the observation window. (Rt is robust to constant under-reporting; it is not robust to a step change in reporting propensity. This is a stated limitation, not a hidden one.)

**Constraints:**
- Local multilingual embedding quality for low-resource Indian languages is materially below that of hosted models. Mitigation: **DR-4**.
- Local generation quality in vernacular languages is the highest technical risk in the project. Mitigation: **DR-5**.

---

# 3. Functional Requirements

## 3.1 Stage 1 — Surveillance Agent

**FR-1.1** The system shall load reports from a local corpus at `data/corpus/`.

**FR-1.2** Each report shall be normalised to:
```json
{
  "id": "uuid",
  "text": "string",
  "timestamp": "ISO 8601 UTC",
  "language": "ISO 639-1",
  "region": "string",
  "region_tier": "metro | tier2 | tier3 | rural | unknown",
  "segment_id": "string",
  "source": "string",
  "source_url": "string | null"
}
```

**FR-1.3** The system shall deduplicate reports by normalised-text hash, retaining the earliest timestamp. Duplicate count shall be retained as a signal, not discarded — repeated identical reports carry spread information.

**FR-1.4** The system shall detect report language locally. Where detection confidence is below threshold, `language` shall be set to `unknown` and the report shall remain eligible for clustering.

**FR-1.5** The system shall assign each report a `segment_id` derived from `(region_tier, language)`.

**FR-1.6 — Reporting-propensity weighting.** The system shall apply a configurable per-segment weight `w_s` to report counts before Rt estimation, to partially correct for differential under-reporting. Weights shall be declared in `config/segments.yaml` with a stated basis. Default `w_s = 1.0` for all segments, overridable.

**FR-1.7 — Replay harness.** The system shall replay the corpus in timestamp order at a configurable compression ratio (default 3 months → 2 minutes).

**FR-1.8** The active compression ratio and the real date currently being simulated shall be visible on the frontend at all times during replay. *This requirement is non-negotiable: undisclosed compression is misrepresentation.*

**FR-1.9** Replay shall support pause, resume, and seek-to-timestamp.

## 3.2 Stage 2 — Lineage Clustering Agent

**FR-2.1** The system shall embed each report using a locally hosted multilingual sentence-embedding model. No embedding request shall leave the machine.

**FR-2.2** Embeddings shall be persisted to a local vector store, keyed by report `id`.

**FR-2.3** For each incoming report the system shall compute similarity against existing lineage centroids and:
- **(a)** if max similarity ≥ `THRESH_MEMBER`, assign to that lineage;
- **(b)** if `THRESH_MUTATION` ≤ max similarity < `THRESH_MEMBER`, create a **child lineage** with `parent_id` set to the nearest lineage;
- **(c)** if max similarity < `THRESH_MUTATION`, create a **new root lineage**.

**FR-2.4** Thresholds shall be configurable and their values displayed in the UI. They shall be tuned against a labelled subset of ≥200 reports, and the tuning result recorded.

**FR-2.5** Each lineage shall persist: `variant_id`, `parent_id`, `label`, `first_seen`, `last_seen`, `report_count`, `languages[]`, `regions[]`, `centroid`.

**FR-2.6** The system shall expose the full lineage forest as a tree structure for visualisation.

**FR-2.7** Lineage centroids shall be recomputed incrementally on member addition (running mean), not by full recomputation.

**FR-2.8** The system shall generate a short human-readable label for each new lineage using the local generation model. Label generation failure shall not block clustering; fallback is `variant-<short_id>`.

## 3.3 Stage 3 — Spread Modeling Agent

**FR-3.1** The system shall estimate a time-varying reproduction number **Rt** per lineage from the weighted report arrival series, using a renewal-equation (EpiEstim-style) method over a sliding window.

**FR-3.2** The system shall **not** implement susceptible-population-dependent SIR as the primary model. Rationale (recorded here deliberately): the susceptible population of a messaging cluster cannot be credibly estimated, and a model whose central parameter is unjustifiable is a liability under questioning. Rt requires no population denominator.

**FR-3.3** Rt estimation shall produce a point estimate and a credible interval (default 95%).

**FR-3.4** The serial-interval prior (mean, SD) shall be configurable in `config/model.yaml` and displayed in the UI. Its value shall be stated as an assumption, not presented as measured.

**FR-3.5** A lineage shall be flagged **ESCALATING** when the **lower bound** of its Rt interval exceeds 1.0. Point estimates shall not trigger alerts.

**FR-3.6** Lineages with fewer than `MIN_REPORTS` (default 10) in the window shall be marked `INSUFFICIENT_DATA` and shall not trigger alerts.

**FR-3.7** The system shall maintain a ranking of lineages by Rt lower bound, updated each replay tick.

**FR-3.8** The system shall predict a **target segment** for each escalating lineage: the segment with highest recent growth in that lineage's reports that has not yet received an inoculation for it.

**FR-3.9** An optional SIR panel may be rendered as illustrative only, and shall be labelled `Illustrative — not used for alerting`.

**FR-3.10 — Backtest mode.** The system shall support offline backtesting over labelled historical waves, emitting per wave:
- alert timestamp (first ESCALATING flag)
- reference timestamp (wave became widely reported)
- **lead time** = reference − alert
- and in aggregate: **detection coverage** (fraction of major waves flagged in advance) and **false-alarm count**.

**FR-3.11** Backtest results shall be reproducible from a fixed seed and a fixed corpus snapshot.

## 3.4 Stage 4 — Inoculation Content Agent

**FR-4.1** The system shall generate inoculation content using a locally hosted instruction-tuned language model. No generation request shall leave the machine.

**FR-4.2** Each inoculation shall contain **two layers**:
- **(a) Technique layer** — the manipulation pattern (authority impersonation, manufactured urgency, isolation from family, screen-share coercion, refund inversion, etc.), described generically. This layer is what confers protection against unseen mutations.
- **(b) Variant layer** — what this specific scam looks like, in the target segment's language.

**FR-4.3** Output shall include: `title`, `technique_layer`, `variant_layer`, `action_steps[]`, `language`, `target_segment`, `variant_id`, `supporting_report_count`.

**FR-4.4** Content shall be generated in the target segment's language. Where the local model cannot produce acceptable output in that language (see **DR-5**), the system shall fall back to a curated template with model-filled slots, and shall mark the post `template_assisted: true`.

**FR-4.5** Content shall target a low reading level. Sentences shall be short; jargon shall be avoided.

**FR-4.6 — Weakened dose (hard constraint).** Generated content shall **not** contain a reproducible scam script, a verbatim scam message, a phone number, a URL, a QR code, or a step-by-step procedure that could be replayed by an operator. Enforced by prompt constraint **and** by a post-generation validator (**FR-4.8**).

**FR-4.7 — No public targeting.** Published content shall not name a specific district, community, caste, or demographic as being targeted. Segment targeting governs *delivery*, never *text*. Rationale: a public "X community is being targeted" post is a targeting list for the next operator.

**FR-4.8 — Output validator.** Every generated post shall pass a deterministic validator before entering the publish queue, checking for: URLs, phone/account number patterns, imperative payment instructions, named demographics from a blocklist, and minimum/maximum length. Failing posts shall be rejected and regenerated up to `MAX_RETRIES` (default 2), then dropped with a logged reason.

**FR-4.9 — Provenance.** Each post shall carry `supporting_report_count`. No post shall be generated for a lineage with fewer than `MIN_REPORTS` supporting reports.

**FR-4.10 — Rate limiting.** The system shall publish at most `MAX_POSTS_PER_SEGMENT_PER_WINDOW` (default 2 per simulated week) per segment. Rationale: over-warning erodes trust and defeats the intervention.

## 3.5 Stage 5 — Publisher and Feed API

**FR-5.1** `POST /init` shall start a background autonomous loop and return immediately. After this call the system shall continue producing and publishing posts with **zero further input**.

**FR-5.2** The loop shall be idempotent: a second `/init` while running shall not spawn a duplicate loop.

**FR-5.3** `GET /feed` shall return published posts **newest-first**.

**FR-5.4** Each post shall carry a **unique `id`** and an **ISO 8601 UTC `createdAt`** timestamp.

**FR-5.5** Feed state shall be **persisted** and shall survive process restart. On restart the loop shall resume without duplicating previously published posts.

**FR-5.6** `GET /feed` shall support `limit` and `since` parameters.

**FR-5.7 — Human-in-the-loop gate.** The system shall support two modes via `AUTO_PUBLISH`:
- `true` — posts publish directly (autonomous evaluation mode).
- `false` — posts enter a review queue; `GET /review`, `POST /review/{id}/approve`, `POST /review/{id}/reject` govern release.

**FR-5.8** Mode shall be settable at startup and visible in the UI and in `GET /status`.

**FR-5.9** `GET /status` shall return: loop running state, mode, simulated current date, compression ratio, lineage count, escalating lineage count, posts published.

**FR-5.10** The loop shall degrade rather than crash: any stage failure shall be logged, the tick abandoned, and the next tick attempted.

## 3.6 Observability

**FR-6.1** Every agent decision shall emit a structured trace event: stage, input summary, decision, confidence/score, latency, token count where applicable.

**FR-6.2** Traces shall be persisted locally and queryable via `GET /trace`.

**FR-6.3** The frontend shall render a live trace view showing recent decisions with latency.

**FR-6.4** No trace data shall be transmitted off-machine. Any tracing library used shall be run in local/self-hosted mode.

## 3.7 Frontend

**FR-7.1 — Lineage tree.** Interactive visualisation of the mutation forest: nodes sized by report count, coloured by Rt status, edges showing parentage, animating as replay advances. *Primary demonstration asset.*

**FR-7.2 — Rt panel.** Per-lineage Rt over time with credible interval band and the Rt = 1 threshold marked.

**FR-7.3 — Backtest chart.** Alert timestamp vs. wide-reporting timestamp with lead time annotated; aggregate coverage and false-alarm count displayed.

**FR-7.4 — Feed view.** Live-updating published inoculations, newest first, showing both content layers and supporting report count.

**FR-7.5 — Status bar.** Simulated date, compression ratio, mode, loop state — visible at all times.

**FR-7.6 — Trace view.** Live agent decision log.

---

# 4. External Interface Requirements

## 4.1 API

| Method | Path | Purpose |
|---|---|---|
| POST | `/init` | Start autonomous loop |
| GET | `/feed` | Published posts, newest-first |
| GET | `/status` | System state |
| GET | `/lineages` | Lineage forest |
| GET | `/lineages/{id}/rt` | Rt series for a lineage |
| GET | `/backtest` | Backtest results |
| GET | `/trace` | Agent decision trace |
| GET | `/review` | Pending posts (review mode) |
| POST | `/review/{id}/approve` | Approve post |
| POST | `/review/{id}/reject` | Reject post |
| POST | `/replay/pause` · `/replay/resume` · `/replay/seek` | Replay control |

## 4.2 Post Schema

```json
{
  "id": "uuid",
  "createdAt": "2026-08-08T14:32:11Z",
  "title": "string",
  "technique_layer": "string",
  "variant_layer": "string",
  "action_steps": ["string"],
  "language": "hi",
  "target_segment": "tier2:hi",
  "variant_id": "uuid",
  "supporting_report_count": 34,
  "rt_at_publish": 1.42,
  "rt_lower_bound": 1.11,
  "template_assisted": false,
  "approved_by": null
}
```

## 4.3 Local Model Interfaces

**IF-1 Embedding model.** Local multilingual sentence-embedding model, loaded in-process. Interface: `embed(texts: list[str]) -> ndarray`. Selection criterion: Indic-language coverage over English benchmark score.

**IF-2 Generation model.** Local instruction-tuned model served via a local runtime (e.g. Ollama or llama.cpp) bound to `127.0.0.1`. Interface: `generate(prompt, max_tokens, temperature) -> str`.

**IF-3** Both interfaces shall be defined as abstract classes with a **deterministic stub implementation** for testing. The full pipeline shall be runnable end-to-end using stubs with no model weights present. *This is what makes the system testable on a laptop and demo-able if a model fails to load.*

---

# 5. Non-Functional Requirements

## 5.1 Performance

**NFR-1.1** Embedding throughput ≥ 200 reports/second on recommended hardware.
**NFR-1.2** Clustering assignment ≤ 50 ms per report.
**NFR-1.3** Rt estimation for all lineages ≤ 2 s per replay tick.
**NFR-1.4** Inoculation generation ≤ 15 s per post on recommended hardware. **Generation shall be asynchronous and shall never block the replay loop.**
**NFR-1.5** `GET /feed` p95 ≤ 200 ms.
**NFR-1.6** Frontend shall remain responsive with ≥500 lineage nodes rendered.

## 5.2 Reliability

**NFR-2.1** The autonomous loop shall run ≥ 60 minutes unattended without crash or memory growth beyond 20%.
**NFR-2.2** All state shall be recoverable after `SIGKILL`.
**NFR-2.3** Generation model unavailability shall degrade to template-assisted output, not failure.

## 5.3 Security and Privacy

**NFR-3.1** No personally identifying information shall be stored. Names, phone numbers, and account numbers present in source reports shall be redacted at ingestion.
**NFR-3.2** No runtime network egress. Verifiable by running with networking disabled.
**NFR-3.3** All services bind to `127.0.0.1` by default.

## 5.4 Maintainability and Reproducibility

**NFR-4.1** Each stage shall be independently runnable via CLI.
**NFR-4.2** All thresholds, weights, and priors shall live in version-controlled config, never in code.
**NFR-4.3** A fixed seed and corpus snapshot shall reproduce identical backtest results.
**NFR-4.4** Setup shall complete via a single documented command sequence on a clean machine.

## 5.5 Usability

**NFR-5.1** Published content shall be readable at a low literacy level.
**NFR-5.2** Every numeric claim on screen shall be accompanied by its uncertainty or its basis.

---

# 6. Ethical and Safety Requirements

**ETH-1** The system shall not perform, recommend, or enable enforcement action against any individual or account.

**ETH-2** Published content shall never constitute a usable scam script (**FR-4.6**, **FR-4.8**).

**ETH-3** Published content shall never publicly identify a targeted community, district, or demographic (**FR-4.7**).

**ETH-4** Alert volume shall be capped per segment (**FR-4.10**). Inoculation research indicates the intervention's value depends on not inducing generalised distrust; over-warning is a failure mode, not an excess of caution.

**ETH-5** Every published claim shall be traceable to a stated number of source reports (**FR-4.9**).

**ETH-6** Timeline compression shall be disclosed on screen at all times (**FR-1.8**).

**ETH-7** Model limitations — assumed serial interval, unvalidated segment weights, embedding quality gaps in low-resource languages — shall be stated in the UI and in the README, not only when asked.

---

# 7. Design Rationale (recorded decisions)

**DR-1 — Rt instead of SIR.** SIR's susceptible-population term is unjustifiable for messaging clusters. Rt is estimated from arrival times alone, needs no denominator, and directly answers "is this accelerating?" — the only question the system actually needs answered.

**DR-2 — Confidence bound gating.** Alerting on Rt point estimates produces false alarms at low report counts, where Rt is noisiest. Gating on the lower bound trades a little lead time for a large reduction in false alarms. Given **ETH-4**, that trade is correct.

**DR-3 — Two-layer content.** Variant-specific warnings are obsolete on the next mutation. Technique-level inoculation generalises across related attacks, which is the only honest basis for claiming coverage of unseen variants.

**DR-4 — Embedding model risk.** Local multilingual embeddings underperform hosted models on low-resource Indian languages. Mitigation: tune `THRESH_MUTATION` per language against a labelled subset; report per-language clustering quality rather than a single aggregate figure. Do not paper over the gap.

**DR-5 — Generation quality risk (highest project risk).** Local models produce weaker vernacular output than hosted ones, and content quality is the user-facing surface. Mitigation: curated per-language templates with model-filled slots as a guaranteed floor; `template_assisted` flag for honesty; human review mode as the deployment answer.

**DR-6 — Stub implementations.** Abstract model interfaces with deterministic stubs let the full pipeline run without weights. This makes the system testable in CI, demo-able on unknown hardware, and survivable if a model fails to load minutes before presentation.

**DR-7 — Human-in-the-loop as a flag, not a mode.** Autonomous operation is required by evaluation; human oversight is required by responsibility. A single config flag satisfies both without architectural duplication.

**DR-8 — Linear pipeline over multi-agent graph.** A well-instrumented linear pipeline with persisted stage boundaries is more debuggable, more demonstrable, and more explainable than a multi-agent graph. Orchestration frameworks may wrap this later; they are not load-bearing.

---

# 8. Requirement Priority

| Priority | Requirements | Rationale |
|---|---|---|
| **P0 — must** | FR-5.1 to FR-5.6, FR-1.1 to FR-1.3, FR-1.7, FR-1.8 | Autonomous loop and feed spec are the graded deliverable. Disclosure is non-negotiable. |
| **P1 — core** | FR-2.1 to FR-2.7, FR-7.1 | Lineage clustering and its visualisation are the primary differentiator. |
| **P2 — credibility** | FR-3.1 to FR-3.11, FR-7.2, FR-7.3 | Rt and backtest are what convert a demo into a claim. |
| **P3 — safety** | FR-4.6 to FR-4.10, ETH-1 to ETH-7 | Cheap to implement, and their absence is a disqualifying answer. |
| **P4 — quality** | FR-4.1 to FR-4.5, FR-7.4 | Content quality; degradable to templates. |
| **P5 — polish** | FR-6.1 to FR-6.4, FR-7.6, FR-3.9 | Observability is high-signal but must be wired early or skipped entirely. |

---

# 9. Acceptance Criteria

The system is accepted when:

1. `POST /init` starts a loop that publishes autonomously for ≥60 minutes with no further input.
2. `GET /feed` returns newest-first posts with unique IDs and ISO 8601 UTC timestamps, surviving a process restart without duplication.
3. The full pipeline runs with networking disabled after setup.
4. The lineage tree renders and animates over a compressed replay with compression ratio visible throughout.
5. Rt is computed per lineage with credible intervals, and alerts fire only on lower bound > 1.
6. A backtest over ≥8 historical waves reports lead time per wave plus aggregate coverage and false-alarm count, reproducibly from a fixed seed.
7. Every published post carries both content layers and a supporting report count, and passes the output validator.
8. No published post contains a URL, contact number, reproducible script, or named target community.
9. The trace view shows live agent decisions with latency.
10. The pipeline runs end-to-end with stub models and no weights present.

---

# 10. Open Issues

| # | Issue | Owner | Resolution needed by |
|---|---|---|---|
| 1 | Serial-interval prior is assumed, not measured. Sensitivity analysis needed across plausible values. | Modeling | Before backtest is presented |
| 2 | Segment reporting weights lack empirical basis; currently 1.0. Decide whether to keep uniform and state the limitation, or derive crudely from survey data. | Data | Before Rt claims are made |
| 3 | Clustering thresholds require per-language tuning; unclear whether the labelled subset is large enough for low-resource languages. | Modeling | Before lineage tree is demoed |
| 4 | "Wide reporting" reference timestamp for backtest waves needs a stated, defensible definition. | Data | Before backtest is presented |
| 5 | Vernacular generation quality unvalidated by native speakers. | Content | Before any vernacular post is shown |
