"""CLI for Stage 3 — Spread Modeling Agent (FR-3.x).

Usage:
    python -m src.stage3_rt.cli estimate
    python -m src.stage3_rt.cli backtest
"""
import argparse
import json


def cmd_estimate(args: argparse.Namespace) -> None:
    from src.stage3_rt.estimation import estimate_all_lineages

    results = estimate_all_lineages()
    for r in results:
        print(f"{r['variant_id']}: {r['status']} rt={r['rt']} lower={r['rt_lower']}")
    print(f"\n{len(results)} lineage(s) estimated.")


def cmd_backtest(args: argparse.Namespace) -> None:
    from src.stage3_rt.backtest import run_backtest

    print(json.dumps(run_backtest(), indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stage3_rt")
    sub = parser.add_subparsers(dest="command", required=True)

    p_estimate = sub.add_parser("estimate", help="Estimate Rt for all lineages")
    p_estimate.set_defaults(func=cmd_estimate)

    p_backtest = sub.add_parser("backtest", help="Run offline backtest over labelled waves")
    p_backtest.set_defaults(func=cmd_backtest)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
