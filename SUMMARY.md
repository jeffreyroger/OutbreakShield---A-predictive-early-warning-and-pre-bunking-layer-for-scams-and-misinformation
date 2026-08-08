# OutbreakShield — Project Summary

**A predictive early-warning and pre-bunking layer for scams and misinformation.**
Built end-to-end in-house and **fully local**. No hosted model APIs, no government APIs, no bank feeds, no third-party fraud services. All embedding, clustering and generation runs on team-controlled hardware; the demonstrated system runs with networking disabled.

*Version 2 — August 2026*

---

## 1. One-Paragraph Summary

India has world-class scam *detection* and effectively no scam *prediction*. Every existing system — bank-side risk scoring, telecom blocking, cybercrime reporting portals, on-device call screening — is fed by reports and therefore structurally late, and structurally blind to the users least likely to report. OutbreakShield sits above that gap. It treats scam variants as pathogens: it ingests public scam reports, clusters them into lineages to detect mutation, estimates a time-varying reproduction number (Rt) per lineage from real report arrival times, ranks which lineage is accelerating, and then autonomously generates and publishes plain-language inoculation content targeted at the population segment predicted to be hit next — before exposure. It does not detect fraud, block transactions, or flag accounts. It decides **who to warn, when, in what language, and about which manipulation technique.**

---

## 2. Problem Statement

Three facts define the problem:

1. **Recovery is not a lever.** Of ₹2,294.79 crore lost to cyber fraud in 2022, roughly ₹0.57 crore was returned to victims. Money that leaves is gone. Prevention is the only meaningful intervention point.
2. **Reporting lag is structural.** Roughly 1 in 5 UPI users have faced fraud, and about half of victims never report. Any system fed by reports reacts after the wave, and systematically under-serves low-digital-literacy, vernacular, Tier-2/3 and senior users — precisely the highest-risk segments.
3. **Variants now mutate at machine speed.** Scam copy is increasingly LLM-generated. A single operator can produce regional and lingual variants in minutes. Signature lists and keyword filters cannot track this; lineage tracking in embedding space can.

Meanwhile the money has moved. UPI collect-request fraud remains the volume leader, but investment scams account for the large majority of rupees stolen, and digital-arrest, voice-cloning and deepfake-endorsement scams are the growth categories. Awareness campaigns exist but are scheduled months in advance rather than triggered by an accelerating variant. **That timing gap is the product.**

---

## 3. What This Is Not

Stating scope negatively is a credibility asset, not a hedge. OutbreakShield:

- does **not** classify individual transactions as fraudulent
- does **not** flag, freeze, or report accounts or users
- does **not** claim real-time forecasting of case counts
- does **not** replace detection infrastructure — it consumes the same public signal and answers a different question

It is a **targeting and timing layer**, and it is deliberately outside the enforcement loop.

---

## 3A. Local Stack

Everything below runs on one machine. Nothing calls out at runtime.

| Layer | Choice | Note |
|---|---|---|
| Embeddings | Local multilingual sentence-embedding model, in-process | Select on Indic coverage, not English benchmark score |
| Generation | Local instruction-tuned 7–8B model via Ollama or llama.cpp, bound to `127.0.0.1` | Quantised build acceptable on 16 GB RAM |
| Vector store | Local FAISS index or SQLite + numpy | No hosted vector DB |
| Rt estimation | NumPy/SciPy, own renewal-equation implementation | No external stats service |
| Persistence | SQLite | Survives SIGKILL; single file to back up |
| API | FastAPI | Binds localhost by default |
| Frontend | React + D3 (lineage tree), Recharts (Rt) | Static build, served locally |
| Tracing | Structured events → local SQLite table → trace view | Self-hosted only |

**Hardware:** 16 GB RAM / 8-core CPU minimum; 32 GB + 12 GB VRAM recommended for demo-grade generation latency.

**Setup discipline:** weights are downloaded once during setup and cached. After setup, disable networking and confirm the full pipeline still runs. Do this test at least a day before the demo, not on the morning of.

---

## 3B. The Two Risks That Actually Threaten This Build

**Vernacular generation quality is the top risk.** Local models are materially weaker in Indian languages than hosted ones, and generated content is the entire user-facing surface. Mitigation is a guaranteed floor: curated per-language templates with model-filled slots, a `template_assisted` flag on any post that used them, and free generation treated as the upgrade rather than the baseline. Build the templates first.

**Model-load failure at demo time is the second.** Define the embedding and generation interfaces as abstract classes with deterministic stub implementations, so the full pipeline runs end-to-end with no weights present. This makes the system testable in CI, runnable on a teammate's laptop, and survivable if a model fails to load twenty minutes before you present.

One performance note that follows from going local: generation takes seconds, not milliseconds. It must run asynchronously off the replay loop, or a 15-second call will visibly stall the lineage tree animation — the one visual you cannot afford to have stutter.

---

## 4. System Architecture

Five stages. Each is independently demonstrable, which matters for degradation under time pressure.

### Stage 1 — Surveillance Agent
**Job:** build a clean, timestamped, segment-tagged stream of scam reports.

- **Sources:** consumer complaint boards, scam-report forums and subreddits, regional and vernacular news archives, publicly aggregated cybercrime summaries.
- **Normalisation:** each report → `{id, text, timestamp, language, region, segment_hint, source}`.
- **Segment tagging:** derive a coarse segment label (region tier, language, apparent demographic where stated). Coarse is fine; the model only needs consistent buckets.
- **Reporting-propensity weighting:** because roughly half of victims never report, the stream is a *biased sample*, not ground truth. Apply a per-segment constant weight before fitting. Twenty lines of code that pre-empt the single sharpest technical question you will be asked.
- **Replay harness:** collect the dataset ahead of time and replay it on a compressed timeline (e.g. 3 months → 2 minutes). **Display the compression ratio on screen.** Stated compression reads as rigour; discovered compression reads as fraud.

### Stage 2 — Strain-Clustering Agent
**Job:** distinguish a genuine new variant from a repeat of a known one, and place it in a lineage.

- Embed each incoming report using a **locally hosted** multilingual embedding model — Indic-language coverage matters more than English benchmark score.
- Cluster against known scam families; assign each report to a family or open a new lineage node.
- Maintain a **lineage tree**: parent variant → regional/lingual descendants, with branch timestamps.
- Emit `variant_id`, `parent_id`, `first_seen`, `languages`, `regions`.

**This is the strongest demo visual in the project.** Nobody expects a scam dashboard to render a virus lineage tree. Protect it above everything except the autonomous loop.

### Stage 3 — Spread-Modeling Agent (credibility core)
**Job:** rank which lineage is accelerating, with stated uncertainty.

Use **time-varying reproduction number (Rt)** estimation, not raw SIR.

- **Why not SIR:** SIR requires a susceptible-population denominator (S). You cannot credibly estimate the susceptible population of a WhatsApp cluster, and any judge with epidemiology background will ask. That question sinks the demo.
- **Why Rt:** it is estimated from the report *arrival series* alone via a renewal equation (EpiEstim-style) over a sliding window. No denominator required. It is what outbreak responders actually use for the "is this accelerating?" question, which is exactly your question.
- **Trigger rule:** Rt > 1 **with a lower confidence bound above 1** → escalating lineage → alert. Gating on the bound rather than the point estimate is what keeps false-alarm volume down.
- Optionally keep an SIR panel as an *illustrative* visual, clearly labelled as such. Never make it load-bearing.

**Framing for judges:** *"We estimate a time-varying reproduction number per variant from real report arrival times. It ranks acceleration and states its own uncertainty. It does not forecast case counts and we don't claim it does."*

### Stage 4 — Inoculation-Content Agent
**Job:** produce the warning, in two layers.

- **Technique-level pre-bunk** — the manipulation pattern itself: authority impersonation, manufactured urgency, isolation from family, screen-share coercion, fake-refund inversion. Inoculation research finds technique-level inoculation confers a "blanket of protection" across related attacks. **This is what lets you claim coverage of the mutation you haven't seen yet** — a real capability, not framing.
- **Variant-specific pre-bunk** — what this exact scam looks like, in the target language, at a reading level matched to the segment.

Content rules are enforced as hard prompt constraints, not suggestions (see §5).

### Stage 5 — Publisher (autonomous agent spec)
**Job:** run unattended and satisfy the grading spec exactly.

- `init` starts a background loop that continues posting with zero further prompting.
- Post schema: unique `id`, ISO 8601 UTC `createdAt`, newest-first ordering, persisted state across restarts.
- The feed itself is the narrative — an ongoing immunisation campaign, not a list of alerts.
- **Human-in-the-loop gate:** implement as a config flag. `AUTO_PUBLISH=true` for the graded autonomous run; `review` mode queues posts for approval. Human approval as a first-class primitive is the defining architectural shift in agentic systems this year. This flag costs an hour and earns full marks on autonomy *and* a complete governance answer. **Highest value-per-hour item in the project.**

---

## 5. Guardrails

Encode these as constraints, and have the reasoning ready verbally.

| Risk | Control |
|---|---|
| Publishing a usable scam playbook | Weakened-dose content only. Describe the manipulation pattern and the defence. Never a reproducible script, number, or message template. |
| Publishing a targeting list | Never name districts, communities, or demographics in published content. Segment targeting stays internal; published text stays general. |
| Alert fatigue / eroding trust | Gate on Rt confidence lower bound, not point estimate. Cap posts per segment per week. Inoculation research specifically values not breeding generalised distrust — over-warning defeats the intervention. |
| Being wrong about a person or account | Stay entirely out of enforcement. No account flagging, no user identification. Courts across multiple states have pushed back hard on over-broad account freezes; explicitly disclaiming enforcement is a strength. |
| Model hallucinating a scam that doesn't exist | Every published post traces to ≥N clustered source reports. Post carries the supporting report count. |

---

## 6. Evaluation

Two metrics, not one. A single lead-time anecdote invites "so what?"

**Lead time.** On a real historical wave: timestamp at which Rt crossed 1 with a confident lower bound, versus the timestamp at which the variant became widely reported. Report the delta. One chart, one number.

**Coverage / precision.** Across a handful of historical waves: of the variants that later became major, what fraction did the system flag in advance — and how many false alarms did that cost? A crude precision/recall pair on 8–10 waves beats one impressive anecdote and signals you understand what evaluation means.

**Observability.** Emit a structured trace event per agent decision to a local SQLite table and render it on one screen — stage, decision, score, latency, tokens. No hosted tracing service; self-hosted or nothing. This is table stakes in agentic reviews in 2026 and almost no hackathon team shows it. Wire it early or skip it — retrofitting tracing at hour 30 is a trap.

**On intervention efficacy:** you do not need to prove pre-bunking works. Field evidence already does — roughly 5–10% technique-recognition lift in a YouTube field study, a ~22 point lift holding at five-month follow-up on Instagram, and a 33-study meta-analysis (combined N ≈ 37,000) supporting improved discrimination without generalised distrust. **Hand this to the judges explicitly:** the intervention is evidenced; what you contribute is targeting and timing. That is a far smaller burden of proof and you should say so.

---

## 7. Judge Q&A

| Question | Answer |
|---|---|
| "Isn't this already solved by existing fraud systems?" | Those detect and block transactions and numbers. None of them decide who to warn next. We're a targeting and timing layer above the detection stack, not a competitor to it. |
| "Is this real epidemiological modelling?" | We estimate a time-varying reproduction number per variant from real report timestamps — standard outbreak-response machinery, used to rank acceleration, not to forecast counts. |
| "Half of victims never report — doesn't that break the model?" | It biases the input, so we weight reporting propensity per segment. Rt is estimated on arrival *rate*, which is more robust to roughly-constant under-reporting than absolute counts are. |
| "Is this live data?" | Real historical data on a compressed replay timeline, stated on screen. Live ingestion is an engineering extension, not a research one. |
| "Does pre-bunking actually work?" | Yes, with field evidence and meta-analytic support. Our contribution isn't the intervention — it's deciding who receives it and when. |
| "What stops this becoming a scam tutorial?" | Weakened-dose content only, no reproducible scripts, no public naming of targeted communities, and a human approval gate before publish. |
| "Why lineage tracking instead of a classifier?" | Scam copy is machine-generated now. Variants outrun signature lists. Lineage tracking in embedding space follows mutation; keyword matching can't. |

---

## 8. Build Priority

Cut from the bottom. This ordering is the single most useful thing in this document at hour 20.

1. **Autonomous posting loop + feed API** — non-negotiable, this is literally what's graded.
2. **Mutation-lineage visual** — best "wow" asset; protect at all costs.
3. **Rt backtest chart (lead time + coverage)** — credibility asset.
4. **Human-in-the-loop approval flag** — cheap, answers governance outright.
5. **Technique-level inoculation layer** — the differentiator in content quality.
6. **Tracing dashboard** — high signal, low cost, but only if wired early.
7. **Multi-agent orchestration** — nice-to-have, and lower value on a local build. A well-instrumented linear pipeline with persisted stage boundaries is more debuggable and more explainable than a graph, and orchestration frameworks add no capability here. Judges grade the explanation, not the framework.

---

## 9. Team Split

| Track | Owns |
|---|---|
| **Data + Surveillance** | Source and clean the historical dataset; compressed replay harness; segment tagging; reporting-propensity weighting. |
| **Modeling** | Multilingual embeddings; lineage clustering; Rt estimation with confidence intervals; backtest harness emitting lead time and coverage. |
| **Agent / Backend** | `init` → autonomous loop → `feed`; persistence; post schema; `AUTO_PUBLISH` / review gate; tracing. |
| **Content / Explainability** | Two-layer inoculation generator (technique + variant); vernacular output; guardrails encoded as prompt constraints. |
| **Frontend / Demo** | Lineage tree + Rt/lead-time chart. These two visuals carry the entire pitch; everything else is supporting evidence. |

---

## 10. Demo Script (3 minutes)

1. **(20s) The hook.** ₹2,294 crore lost in 2022; ₹0.57 crore returned. Recovery isn't a lever.
2. **(20s) The gap.** India has excellent scam detection. Nobody's system decides who to warn next.
3. **(50s) Live replay.** Start the compressed timeline. Watch the lineage tree branch as a variant mutates across regions and languages. Narrate: *"these variants are machine-generated now — that's why signature lists can't keep up."*
4. **(40s) The model fires.** Rt crosses 1 on one lineage. Show the confidence band. Show the ranked variant list re-order.
5. **(30s) The feed.** An inoculation post appears — autonomously, unprompted. Show the technique-level layer and the vernacular variant-specific layer.
6. **(20s) The proof.** Backtest chart: here's when we'd have flagged it, here's when it actually broke, here's the lead time, here's our hit rate across ten waves.

---

## 11. Pitch Lines

**Submission form (one line):**
> *"India has world-class scam detection and almost no scam prediction. OutbreakShield models scam variants like disease lineages — tracking mutation, estimating spread velocity, and autonomously warning the next at-risk community before the scam reaches them."*

**The three sentences that win the room:**
1. *"Of ₹2,294 crore lost to cyber fraud in 2022, ₹0.57 crore was returned to victims. Recovery isn't a lever. Prevention is the only lever."*
2. *"India already has excellent scam detection. What it doesn't have is scam prediction — nobody's system decides who to warn next."*
3. *"Scam copy is machine-generated now. Variants outrun signature lists, so we track lineage instead — and inoculate against the technique, which covers the mutation we haven't seen yet."*
