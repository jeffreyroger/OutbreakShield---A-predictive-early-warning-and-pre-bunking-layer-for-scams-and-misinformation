"""Prints corpus coverage: count, date range, per-language and per-region-tier breakdown.

Run: python scripts/corpus_stats.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.connection import get_connection


def main() -> None:
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]
        print(f"Total reports: {total}")
        if total == 0:
            print("No reports ingested yet. Run `python -m src.stage1_surveillance.cli ingest`.")
            return

        date_range = conn.execute(
            "SELECT MIN(timestamp) AS lo, MAX(timestamp) AS hi FROM reports"
        ).fetchone()
        print(f"Date range: {date_range['lo']} .. {date_range['hi']}")

        print("\nBy language:")
        for row in conn.execute(
            "SELECT language, COUNT(*) AS n FROM reports GROUP BY language ORDER BY n DESC"
        ):
            print(f"  {row['language']}: {row['n']}")

        print("\nBy region tier:")
        for row in conn.execute(
            "SELECT region_tier, COUNT(*) AS n FROM reports GROUP BY region_tier ORDER BY n DESC"
        ):
            print(f"  {row['region_tier']}: {row['n']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
