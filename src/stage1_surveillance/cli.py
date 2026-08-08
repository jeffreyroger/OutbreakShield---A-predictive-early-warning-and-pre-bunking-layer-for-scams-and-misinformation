"""CLI for Stage 1 — Surveillance Agent (FR-1.x).

Usage:
    python -m src.stage1_surveillance.cli ingest
    python -m src.stage1_surveillance.cli replay --seek 2026-03-01T00:00:00Z
"""
import argparse
from datetime import datetime, timezone


def cmd_ingest(args: argparse.Namespace) -> None:
    from src.stage1_surveillance.normalize import ingest_corpus

    summary = ingest_corpus()
    print(
        f"Inserted: {summary['inserted']} | Duplicates: {summary['duplicates']} | "
        f"Rejected: {summary['rejected']} (see data/corpus/rejects.jsonl)"
    )


def cmd_replay(args: argparse.Namespace) -> None:
    from src.stage1_surveillance.replay import get_clock

    clock = get_clock()
    clock.start()
    if args.seek:
        target = datetime.fromisoformat(args.seek.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        clock.seek(target)
    print(clock.get_status())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stage1_surveillance")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Normalise and load the corpus")
    p_ingest.set_defaults(func=cmd_ingest)

    p_replay = sub.add_parser("replay", help="Start/seek the replay clock and print status")
    p_replay.add_argument("--seek", help="ISO 8601 timestamp to seek to")
    p_replay.set_defaults(func=cmd_replay)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
