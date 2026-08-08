# OutbreakShield

**Live Deployed App:** http://outbreakshield.surge.sh

Predictive early-warning and pre-bunking layer for scams and misinformation.
Fully local: no hosted model APIs, no external services at runtime. See
[SUMMARY.md](SUMMARY.md) for the pitch, [SRS.md](SRS.md) for requirements,
and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the build sequence.

## Layout

```
config/          thresholds, Rt priors, segment weights, runtime flags (never hardcode these)
data/
  corpus/        raw collected reports (gitignored)
  labels/        hand-labelled subsets for tuning + backtest (gitignored)
  outbreakshield.db   SQLite (gitignored, created by src/db/init.py)
models/          downloaded weights (gitignored)
src/
  interfaces/    abstract Embedder/Generator + deterministic stubs (MODEL_MODE=stub)
  stage1_surveillance/   ingestion, normalisation, replay harness
  stage2_lineage/        embedding + clustering into mutation lineages
  stage3_rt/              time-varying reproduction number estimation + backtest
  stage4_content/         two-layer inoculation generation + output validator
  stage5_publisher/       autonomous publish loop
  trace/          structured per-decision tracing
  db/             SQLite schema + connection
  api/            FastAPI app (binds 127.0.0.1)
frontend/        React + D3/Recharts UI (lineage tree, Rt panel, feed, trace view)
scripts/         setup.sh, corpus_stats.py, tune_thresholds.py, backtest.py
tests/
  unit/          fast, no I/O beyond the local SQLite file
  integration/
```

## Setup

```bash
bash scripts/setup.sh          # creates .venv, installs deps, inits DB, installs frontend deps
cp .env.example .env
```

Each stage is independently runnable:

```bash
python -m src.stage1_surveillance.cli ingest
python -m src.stage2_lineage.cli cluster
python -m src.stage3_rt.cli estimate
python -m src.stage4_content.cli generate --variant-id <id>
python -m src.stage5_publisher.cli init
```

API:

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend && npm run dev
```

## Testing without model weights

`MODEL_MODE=stub` (the default) runs the entire pipeline with deterministic
stub embeddings/generation and no weights present:

```bash
pytest
```

Switch to `MODEL_MODE=real` once local embedding and generation models are
wired up (Phase 3 / Phase 5 of the implementation plan).

## Local-only constraint

No component may call a hosted inference endpoint at runtime. Model weights
are downloaded once during setup; after that, the full pipeline must run
with networking disabled. Verify this explicitly before a demo (see
IMPLEMENTATION_PLAN.md, Phase 8).

## Known limitations (stated up front, per ETH-7)

- Serial-interval prior in `config/model.yaml` is assumed, not measured.
- Segment reporting weights in `config/segments.yaml` default to uniform (1.0).
- Local embedding/generation quality in low-resource Indian languages is
  unvalidated until Phase 3/5 tuning and native-speaker review.
