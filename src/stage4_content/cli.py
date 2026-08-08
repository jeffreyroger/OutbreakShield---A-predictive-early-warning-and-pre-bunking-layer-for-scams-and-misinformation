"""CLI for Stage 4 — Inoculation Content Agent (FR-4.x).

Usage:
    python -m src.stage4_content.cli generate --variant-id <id> --segment tier2:hi
"""
import argparse
import json


def cmd_generate(args: argparse.Namespace) -> None:
    from src.stage4_content.generate import (
        check_provenance, check_rate_limit, generate_content_for_lineage,
    )

    if not check_provenance(args.variant_id):
        print("Rejected: lineage below MIN_REPORTS provenance threshold (FR-4.9).")
        return
    if not check_rate_limit(args.segment, args.variant_id):
        print("Rejected: segment rate limit reached for this window (FR-4.10).")
        return

    result = generate_content_for_lineage(args.variant_id, args.segment)
    if not result.ok:
        print(f"No publishable content produced: {result.reason}")
        return
    print(json.dumps({**result.content, "template_assisted": result.template_assisted}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stage4_content")
    sub = parser.add_subparsers(dest="command", required=True)

    p_generate = sub.add_parser("generate", help="Generate an inoculation post for a lineage")
    p_generate.add_argument("--variant-id", required=True)
    p_generate.add_argument("--segment", required=True, help="e.g. tier2:hi")
    p_generate.set_defaults(func=cmd_generate)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
