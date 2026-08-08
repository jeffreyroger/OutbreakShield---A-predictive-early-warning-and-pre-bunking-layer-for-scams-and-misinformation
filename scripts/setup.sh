#!/usr/bin/env bash
# One-time setup (NFR-4.4). Requires network for this run only (CON-3).
# After this completes, verify the pipeline runs with networking disabled.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== Creating virtualenv =="
python3 -m venv .venv
source .venv/bin/activate

echo "== Installing Python dependencies =="
pip install -r requirements.txt

echo "== Initialising database =="
python -m src.db.init

echo "== Frontend dependencies =="
if [ -d frontend ]; then
  (cd frontend && npm install)
fi

echo "== Done. Model weights are downloaded on first real (non-stub) run. =="
echo "Set MODEL_MODE=stub to run the full pipeline with no weights present."
