"""Idempotent DB initialiser. Run: python -m src.db.init"""
from pathlib import Path
from src.db.connection import get_connection

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_db() -> None:
    conn = get_connection()
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("DB initialised.")
