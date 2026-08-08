"""Standalone CLI wrapper for the offline backtest (FR-3.10, FR-3.11).
Thin wrapper — the real logic lives in src/stage3_rt/backtest.py, also
reachable via `python -m src.stage3_rt.cli backtest` or `GET /backtest`.

Run: python scripts/backtest.py
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed", type=int, default=0,
        help="No-op placeholder: run_backtest() is a deterministic read over "
        "persisted state (NFR-4.3), not a stochastic simulation, so there is "
        "nothing to seed today. Kept for CLI compatibility with the original spec.",
    )
    args = parser.parse_args()

    from src.stage3_rt.backtest import run_backtest

    print(json.dumps(run_backtest(), indent=2, default=str))


if __name__ == "__main__":
    main()
