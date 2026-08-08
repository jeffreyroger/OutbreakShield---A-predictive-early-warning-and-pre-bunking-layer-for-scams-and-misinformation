"""CLI for Stage 5 — Publisher (FR-5.x).

Usage:
    python -m src.stage5_publisher.cli init
    python -m src.stage5_publisher.cli init --review   # AUTO_PUBLISH=false
"""
import argparse
import time


def cmd_init(args: argparse.Namespace) -> None:
    from src.stage5_publisher.service import get_status, init_loop

    result = init_loop(auto_publish=not args.review)
    print(result)
    if not args.foreground:
        return

    print("Running in foreground. Ctrl+C to stop (loop keeps running in-process until exit).")
    try:
        while True:
            time.sleep(5)
            print(get_status())
    except KeyboardInterrupt:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stage5_publisher")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Start the autonomous publishing loop")
    p_init.add_argument(
        "--review", action="store_true",
        help="Start in review mode (AUTO_PUBLISH=false) instead of autonomous publish",
    )
    p_init.add_argument(
        "--foreground", action="store_true",
        help="Block and print status periodically instead of returning immediately",
    )
    p_init.set_defaults(func=cmd_init)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
