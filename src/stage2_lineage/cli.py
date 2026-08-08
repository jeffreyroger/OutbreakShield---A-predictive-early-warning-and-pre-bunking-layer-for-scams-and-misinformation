"""CLI for Stage 2 — Lineage Clustering Agent (FR-2.x).

Usage:
    python -m src.stage2_lineage.cli cluster
    python -m src.stage2_lineage.cli tree
"""
import argparse
import json


def cmd_cluster(args: argparse.Namespace) -> None:
    from src.stage2_lineage.cluster import process_pending

    summary = process_pending(limit=args.limit)
    print(summary)


def cmd_tree(args: argparse.Namespace) -> None:
    from src.stage2_lineage.tree import build_forest

    print(json.dumps(build_forest(), indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stage2_lineage")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cluster = sub.add_parser("cluster", help="Embed and assign pending reports to lineages")
    p_cluster.add_argument("--limit", type=int, default=None)
    p_cluster.set_defaults(func=cmd_cluster)

    p_tree = sub.add_parser("tree", help="Export the lineage forest")
    p_tree.set_defaults(func=cmd_tree)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
