#!/usr/bin/env python3
"""Initializes PostgreSQL schema for EIS Parser."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize PostgreSQL schema")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "").strip(),
        help="PostgreSQL connection URL (default: DATABASE_URL env)",
    )
    parser.add_argument(
        "--schema-file",
        default=str(Path(__file__).with_name("postgres_schema.sql")),
        help="Path to SQL schema file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("DATABASE_URL is required")
        return 1

    schema_path = Path(args.schema_file)
    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}")
        return 1

    sql = schema_path.read_text(encoding="utf-8-sig")

    conn = psycopg2.connect(args.database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("PostgreSQL schema initialized successfully")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
