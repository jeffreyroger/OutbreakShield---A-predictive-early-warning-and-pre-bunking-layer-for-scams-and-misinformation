# OutbreakShield — Prompt Engineering Transcript (PROMPTS.md)

**Live Deployed App:** http://outbreakshield.surge.sh
**GitHub Repository:** https://github.com/jeffreyroger/OutbreakShield---A-predictive-early-warning-and-pre-bunking-layer-for-scams-and-misinformation

This file contains key prompts and architectural instructions used to build OutbreakShield under local-only constraints. It serves as evidence of systematic engineering and "vibe-coding" discipline.

---

## Prompt 1: Project Scaffolding and Setup (Phase 0)

**Intent:** Scaffold a five-stage linear pipeline with persisted SQLite database boundaries.

```
Set up a clean directory skeleton for OutbreakShield:
1. Initialize config/ folders for model.yaml, segments.yaml, runtime.yaml.
2. Setup sqlite database initialization at src/db/connection.py and src/db/repository.py.
3. Write abstract class interfaces for Embedder and Generator, and stub implementations that return deterministic outputs (hash-based vectors and mock json posts) so we can run the pipeline without local weight loading.
4. Setup structured trace context manager to capture latency and decisions for S1..S5 stages in SQLite.
```

---

## Prompt 2: Synthetic Corpus Generation & Verification (Phase 1)

**Intent:** Generate a 3,000+ record multilingual synthetic corpus with seed-reproducible dates, PII injection, and classification labels.

```
Create a python script `scripts/generate_corpus.py` to produce a seed-reproducible synthetic corpus:
1. Generate >= 3,000 reports across 3 languages (en, hi, ta) and 4 region tiers (metro, tier2, tier3, rural).
2. Generate four scam families: authority_impersonation, refund_inversion, digital_arrest, and investment_deepfake (high-value variants).
3. Inject realistic PII patterns (phone numbers, account numbers, UPI IDs, URLs) into exactly 26 records, and create `scripts/verify_pii_redaction.py` to assert regex redaction is 100% effective post-ingestion.
4. Create stratified labeled subsets in data/labels/clustering.csv for threshold tuning and data/labels/wave_ground_truth.csv for Rt backtesting.
```

---

## Prompt 3: Multilingual Embedding & Threshold Tuning (Phase 3)

**Intent:** Implement local multilingual sentence embeddings and write a sweep script to tune thresholds per language.

```
1. Implement LocalEmbedder in src/interfaces/embedder.py using `sentence-transformers` and the model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` with weights cached in the models/ directory.
2. Implement scripts/tune_thresholds.py to load labeled clustering.csv, fetch report texts, embed them, compute pairwise cosine similarities, and sweep similarity thresholds (0.50 to 0.95) to find the F1-maximizing member and mutation thresholds per language (English, Hindi, and Tamil).
3. Update config/model.yaml with the tuned per-language thresholds:
   - EN: member=0.70, mutation=0.52
   - HI: member=0.68, mutation=0.50
   - TA: member=0.94, mutation=0.90
4. Update src/stage2_lineage/cluster.py to check for language-specific thresholds when assigning new reports to family lineages.
```

---

## Prompt 4: renewal-equation Rt Estimator & Gating (Phase 4)

**Intent:** Implement renewal-equation based Rt estimation from scratch using numpy/scipy and write a synthetic recovery test.

```
Implement a custom renewal-equation Rt estimator in src/stage3_rt/renewal.py:
1. Binned weighted arrivals (incidence) calculation based on report dates, dup_counts, and segment weights.
2. Discretize gamma-based serial interval (mean=2.5, SD=1.5) and calculate total infectiousness Lambda_t.
3. Compute posterior gamma distribution to retrieve Rt point estimates and 95% credible intervals.
4. Write test_renewal.py to simulate an epidemic with known constant R and assert the estimator successfully recovers R inside the interval and gates correctly on rt_lower > 1.0.
```

---

## Prompt 5: Inoculation Content Generation & Async Queue (Phase 5 & 6)

**Intent:** Setup local generation via Ollama, output validation, template fallback, and async execution queue.

```
1. Implement LocalGenerator in src/interfaces/generator.py communicating with Ollama API (/api/generate) with format='json' option.
2. Update validator.py with a DEMOGRAPHIC_BLOCKLIST to reject posts mentioning targeted caste, religion, or specific districts (Jamtara, Mewat, etc.) as target text.
3. Decouple generation latency from the tick loop (NFR-1.4): implement an in-process thread-safe background Queue (Queue) and worker thread in loop.py to handle generation asynchronously.
4. Persist simulated replay clock cursor and elapsed seconds in loop_state SQLite table to handle SIGKILL restarts safely.
```

---

## Prompt 6: Interactive Glassmorphic React/TypeScript Dashboard (Phase 7)

**Intent:** Implement D3 lineage visualization and Recharts modeling analytics in React with a dark glassmorphic styling system.

```
Develop a high-fidelity dashboard:
1. Create a glassmorphic dark theme in index.css with outfit font and neon accents (violet/rose/blue).
2. StatusBar: Display simulated time, play/pause controls, compression ratio, and auto-publish mode.
3. LineageTree: Use D3 force/tidy layout to draw the mutation forest, node radii scaled by report count, and color coded by Rt status. Implement click-to-select variant.
4. RtPanel: Render a Recharts Area chart displaying the selected lineage's Rt estimates and shaded confidence interval band with reference line Rt = 1.
5. BacktestChart: Render vertical Recharts bar chart comparing warning date vs. ground-truth acceleration.
6. Feed: Show published inoculations with technique and variant layers, alongside approval moderation queue controls.
7. TraceView: Render a live table of agent trace logs (latency, decisions, scores).
```
