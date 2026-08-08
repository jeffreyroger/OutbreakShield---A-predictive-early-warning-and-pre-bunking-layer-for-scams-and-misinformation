# OutbreakShield — Hard Rules

**This file is binding.** Every rule below is derived from `SRS.md`, `SUMMARY.md`, and
`IMPLEMENTATION_PLAN.md` and is treated as a hard constraint, not a guideline. If a
change under consideration would violate a rule here, it does not ship — the rule wins,
not the shortcut. If a rule needs to change, it is changed here first, deliberately,
with the reason recorded — never silently bypassed in code.

This project **will be deployed**, not just demoed once. Every rule below is written
assuming the system keeps running unattended after the person who wrote the code has
stopped watching it. "Works in one run on my machine" does not satisfy any rule here.

---

## 0. Process rule — validate before touching anything

Before any coding session, config change, or planning work: **read `SRS.md`,
`SUMMARY.md`, and `IMPLEMENTATION_PLAN.md` in full first.** Do not work from memory of
a previous session. These three files are the single source of truth for scope,
architecture, and priority. If a request conflicts with them, surface the conflict —
do not silently resolve it in either direction.

After reading, check `tasks.md` to see what is already done and what is next. Update
`tasks.md` as part of finishing any unit of work, not as an afterthought at the end of
a session.

---

## 1. Scope — what this system is and is not

OutbreakShield is a **targeting and timing layer**. It decides *who to warn, when, in
what language, about which manipulation technique.*

**Hard scope boundary — never cross this, regardless of what would be technically easy
or what a feature request implies:**

- **NEVER** classify an individual transaction as fraudulent.
- **NEVER** flag, freeze, block, or report a specific account or user.
- **NEVER** identify or attempt to identify a specific individual.
- **NEVER** integrate with a banking, telecom, or law-enforcement system.
- **NEVER** claim real-time forecasting of case counts. Rt ranks acceleration; it does
  not predict absolute numbers, and no UI text or generated content may imply it does.
- **NEVER** add multi-agent orchestration frameworks as a substitute for the linear,
  persisted-boundary pipeline (DR-8). The five-stage linear design is a deliberate
  choice, not a placeholder waiting to be "upgraded."

If a task looks like it needs any of the above to be "more useful," the correct
response is to say so and stop, not to quietly implement it.

---

## 2. Local-only constraint (CON-1 to CON-4) — non-negotiable

- **CON-1.** No component makes a network call to a hosted model inference endpoint
  at runtime. Embedding, generation, and clustering all execute on local hardware,
  in-process or via a local runtime bound to `127.0.0.1`.
- **CON-2.** Model weights are downloaded once during setup and cached. After setup,
  the system must run correctly with networking fully disabled. **Test this explicitly,
  at least a day before any demo or deploy — never on the day of.** Some libraries
  phone home on load even with cached weights; this has to be checked, not assumed.
- **CON-3.** Network access during data collection is fine. The deployed/demoed system
  runs from a local, pre-collected corpus.
- **CON-4.** No user-identifying data leaves the local machine, ever, including during
  setup.

**Deployment implication:** before any deploy, run the full pipeline with networking
disabled and confirm it still works end-to-end. This is a release gate, not optional
QA. See Phase 8 of `IMPLEMENTATION_PLAN.md`.

---

## 3. Model interface discipline (DR-6, IF-1 to IF-3)

- Every model dependency (embedding, generation) is defined as an **abstract class**
  with a **deterministic stub implementation**.
- `MODEL_MODE=stub` must always produce a working, schema-correct pipeline with **no
  weights present**. This is not a test-only convenience — it is the deployment
  fallback if a model fails to load. Never let this drift out of sync with the real
  implementation's output contract (same schema, same fields).
- Do not bypass the interface layer to call a model runtime directly from stage logic.
  Everything goes through `Embedder` / `Generator`.

---

## 4. Content guardrails (FR-4.6 to FR-4.10, ETH-1 to ETH-7) — hard constraints

These are enforced in **code** (prompt constraints alone are insufficient — see
Step 5.4 of the implementation plan), and every one of them is a release blocker if
violated, not a follow-up ticket.

- **Weakened dose only.** Generated or templated content never contains a reproducible
  scam script, a verbatim scam message, a phone number, an account/VPA number, a URL,
  a QR code, or a step-by-step procedure an operator could replay. Describe the
  manipulation pattern and the defence — never the playbook.
- **No public targeting.** Published content never names a specific district,
  community, caste, or demographic. Segment targeting governs *delivery* only, never
  *text*. A post that says "X community is being targeted" is a targeting list for the
  next scammer — this is disqualifying, not a style note.
- **Deterministic validator required.** Every generated post passes a non-model
  validator (`src/stage4_content/validator.py`) before it can enter the publish queue:
  URL check, phone/account/VPA pattern check, payment-imperative check, demographic
  blocklist check, length bounds. Failing posts retry up to `MAX_RETRIES`, then are
  dropped with a logged reason — never force-published.
- **Provenance required.** Every post carries `supporting_report_count`. No post is
  generated for a lineage with fewer than `MIN_REPORTS` supporting reports (config,
  default 10).
- **Rate limiting is mandatory.** At most `MAX_POSTS_PER_SEGMENT_PER_WINDOW` (config,
  default 2 per simulated week) per segment. This exists because over-warning erodes
  trust and defeats the intervention — it is a correctness requirement, not a
  nice-to-have throttle.
- **No enforcement action, ever.** No account flagging, freezing, or user
  identification, under any circumstance, including "just logging it internally for
  review."
- **Alert gating on the confidence lower bound, never the point estimate.** A lineage
  is `ESCALATING` only when `rt_lower > 1.0` **and** `n_reports >= MIN_REPORTS`.
  Point-estimate-only triggers are a false-alarm risk explicitly rejected by design
  (DR-2).
- **PII redaction happens at ingestion, before storage** — never deferred to display
  time. Phone numbers, account numbers, UPI VPAs, emails, URLs, and detectable person
  names are stripped from `reports.text` before it is written to the database, because
  PII that reaches storage will propagate into embeddings and generated content and
  becomes unrecoverable once published.
- **Every numeric claim shown to a user is accompanied by its uncertainty or basis**
  (NFR-5.2). Never surface a bare Rt number, lead time, or coverage percentage without
  its interval, assumption, or sample size next to it.

---

## 5. Disclosure requirements — never hide these

- **Replay compression ratio and simulated current date are visible on screen at all
  times during replay** (FR-1.8, ETH-6). Undisclosed compression is misrepresentation,
  full stop — this is true whether it's a live demo or a deployed instance.
- **`AUTO_PUBLISH` mode is visible** in the UI and via `GET /status` (FR-5.8). A viewer
  must always be able to tell whether posts are auto-publishing or queued for review.
- **Model limitations are stated in the UI and README, not only when asked** (ETH-7):
  assumed serial interval, unvalidated/uniform segment weights, per-language embedding
  quality gaps. Volunteer these; do not wait to be caught not mentioning them.
- **`template_assisted: true`** is set and shown whenever a post used the curated
  template fallback rather than free generation (FR-4.4). This is a transparency flag,
  not an implementation detail to suppress.

---

## 6. Modeling rules — do not "simplify" these away

- **Rt (time-varying reproduction number), not SIR, is the primary spread model**
  (DR-1, FR-3.2). SIR requires a susceptible-population denominator that cannot be
  credibly estimated for a messaging cluster. An SIR panel may exist as an
  **illustrative-only** visual, explicitly labelled `Illustrative — not used for
  alerting` (FR-3.9), and must never be load-bearing for any alert or claim.
- **Thresholds, weights, and priors live in `config/*.yaml`, never in code**
  (NFR-4.2). If a number needs tuning, it needs to already be in config — don't add a
  new hardcoded constant to fix something at build or deploy time.
- **Per-language quality is reported separately, not aggregated into one number**
  (DR-4). A single aggregate clustering-quality figure hides exactly the gap
  (low-resource-language performance) that the project has committed to being honest
  about.
- **Centroid updates are incremental (running mean), never full recomputation**
  (FR-2.7) — full recomputation is an O(n²) trap that will stall the pipeline at
  scale, including in deployment under real corpus growth, not just at demo size.
- **Duplicate reports are never discarded** — increment `dup_count` and keep them
  (FR-1.3, Step 2.2). They are spread signal, not noise.
- **Backtests must be reproducible from a fixed seed and corpus snapshot**
  (NFR-4.3). If a backtest result can't be regenerated byte-identical from the same
  inputs, something in the pipeline has a hidden nondeterminism — treat that as a bug,
  not a rounding difference.

---

## 7. Reliability rules (deployment posture)

- `POST /init` starts an idempotent autonomous loop — **a second call while running
  must never spawn a duplicate loop** (FR-5.1, FR-5.2). Guard this with `loop_state`,
  not with a comment saying "don't call this twice."
- **All state lives in SQLite and must survive `SIGKILL`** (NFR-2.2). On restart, the
  loop resumes from `loop_state` without republishing or duplicating posts (FR-5.5).
  This must actually be tested with a real `SIGKILL`, not assumed from clean-shutdown
  behavior.
- **Any single stage failure is logged and the tick is abandoned; the next tick still
  runs** (FR-5.10). One bad report, one failed generation call, or one clustering
  exception must never take down the loop. The loop must survive ≥60 minutes
  unattended without crash or >20% memory growth (NFR-2.1) — this is the deployment
  reliability bar, not just a hackathon uptime target.
- **Generation runs asynchronously, off the replay/serving loop** (NFR-1.4). A slow
  (up to 15s) generation call must never block ingestion, clustering, or the feed API.
- **All services bind to `127.0.0.1` by default** (NFR-3.3). Do not widen this binding
  without an explicit, separate decision — this is a security boundary, not an
  accident of local dev.
- **Feed API performance:** `GET /feed` must stay at p95 ≤ 200 ms (NFR-1.5) regardless
  of how large the `posts` table grows in a long-running deployment. If a query starts
  degrading with data volume, that's a regression against this rule.

---

## 8. What "done" means for any piece of work

A task is not complete because code exists for it. It is complete when:

1. It satisfies the specific FR-/NFR-/DR-/ETH- requirement ID(s) it maps to in
   `SRS.md` — cite the ID when marking it done in `tasks.md`.
2. It has been verified by the check described for that step in
   `IMPLEMENTATION_PLAN.md` (each step has an explicit "Verify:" line — run it).
3. It does not violate any rule in this file.
4. `tasks.md` has been updated to reflect the new state.

If a shortcut is taken to hit a deadline, it must be recorded as a known gap in
`tasks.md`, not silently left implicit.

---

## 9. Amending this file

Rules here come from the three source documents. If a rule here turns out to be wrong
or the source documents change, update **this file and the source document together**
in the same change, and note why. Never let `docs.md` silently drift out of sync with
`SRS.md`.
