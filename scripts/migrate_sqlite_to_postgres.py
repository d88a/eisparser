#!/usr/bin/env python3
"""Migrates data from SQLite to PostgreSQL for EIS Parser."""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import psycopg2

MAX_ROW_WARNINGS_PER_TABLE = 20


TABLES = [
    {
        "name": "zakupki",
        "columns": [
            "reg_number",
            "description",
            "update_date",
            "bid_end_date",
            "initial_price",
            "link",
            "combined_text",
            "two_gis_url",
            "processed_at",
            "status",
            "prepared_by_user_id",
            "prepared_at",
        ],
        "conflict": ["reg_number"],
    },
    {
        "name": "ai_results",
        "columns": [
            "reg_number",
            "zakupka_name",
            "address",
            "city",
            "area_min_m2",
            "area_max_m2",
            "rooms",
            "rooms_parsed",
            "floor",
            "building_floors_min",
            "year_build_str",
            "wear_percent",
            "zakazchik",
        ],
        "conflict": ["reg_number"],
    },
    {
        "name": "users",
        "columns": ["id", "email", "role", "created_at"],
        "conflict": ["id"],
    },
    {
        "name": "decisions",
        "columns": ["id", "user_id", "reg_number", "stage", "decision", "comment", "created_at"],
        "conflict": ["id"],
    },
    {
        "name": "user_overrides",
        "columns": ["id", "user_id", "reg_number", "field_name", "value", "created_at"],
        "conflict": ["id"],
    },
    {
        "name": "user_selections",
        "columns": ["id", "user_id", "reg_number", "selected_at"],
        "conflict": ["id"],
    },
    {
        "name": "listings",
        "columns": [
            "id",
            "zakupka_reg_number",
            "rank",
            "price_rub",
            "address",
            "rooms",
            "area_m2",
            "floor",
            "building_floors",
            "building_year",
            "two_gis_url",
            "external_source",
            "external_url",
            "fetched_at",
            "query_url",
        ],
        "conflict": ["id"],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        default=str(Path("results") / "eis_data.db"),
        help="Path to source SQLite DB (default: results/eis_data.db)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "").strip(),
        help="PostgreSQL connection URL (default: DATABASE_URL env)",
    )
    parser.add_argument(
        "--schema-file",
        default=str(Path(__file__).with_name("postgres_schema.sql")),
        help="Path to PostgreSQL schema SQL file",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate target PostgreSQL tables before import",
    )
    return parser.parse_args()


def sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def sqlite_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def build_upsert_sql(table_name: str, columns: list[str], conflict_columns: list[str]) -> str:
    insert_cols = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    if not conflict_columns:
        return f"INSERT INTO {table_name} ({insert_cols}) VALUES ({placeholders})"

    conflict_cols = ", ".join(conflict_columns)
    update_cols = [c for c in columns if c not in conflict_columns]
    if update_cols:
        update_sql = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
        return (
            f"INSERT INTO {table_name} ({insert_cols}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_sql}"
        )
    return (
        f"INSERT INTO {table_name} ({insert_cols}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_cols}) DO NOTHING"
    )


def sync_sequence(pg_conn, table_name: str):
    sql = f"""
    SELECT setval(
        pg_get_serial_sequence('{table_name}', 'id'),
        COALESCE((SELECT MAX(id) FROM {table_name}), 1),
        (SELECT MAX(id) IS NOT NULL FROM {table_name})
    )
    """
    with pg_conn.cursor() as cur:
        cur.execute(sql)


def ensure_schema(pg_conn, schema_file: str):
    schema_path = Path(schema_file)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    sql = schema_path.read_text(encoding="utf-8-sig")
    with pg_conn.cursor() as cur:
        cur.execute(sql)


def reset_target(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE listings, user_selections, user_overrides, decisions, ai_results, zakupki, users RESTART IDENTITY CASCADE"
        )


def ensure_users_for_legacy_decisions(src_conn: sqlite3.Connection, pg_conn):
    """Creates placeholder users for legacy decisions if users table is empty/incomplete."""
    if not sqlite_table_exists(src_conn, "decisions"):
        return

    rows = src_conn.execute(
        "SELECT DISTINCT user_id FROM decisions WHERE user_id IS NOT NULL"
    ).fetchall()
    if not rows:
        return

    with pg_conn.cursor() as cur:
        for row in rows:
            user_id = row["user_id"]
            cur.execute(
                """
                INSERT INTO users (id, email, role, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO NOTHING
                """,
                (user_id, f"legacy_user_{user_id}@local", "admin"),
            )


def load_target_values(pg_conn, table_name: str, column_name: str) -> set:
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT {column_name} FROM {table_name}")
        return {row[0] for row in cur.fetchall()}


def migrate(sqlite_path: str, database_url: str, schema_file: str, reset: bool = False) -> int:
    if not database_url:
        raise ValueError("DATABASE_URL is required")

    sqlite_db = Path(sqlite_path)
    if not sqlite_db.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_db}")

    src = sqlite3.connect(str(sqlite_db))
    src.row_factory = sqlite3.Row

    dst = psycopg2.connect(database_url)
    try:
        ensure_schema(dst, schema_file)
        dst.commit()
        if reset:
            reset_target(dst)
            dst.commit()

        ensure_users_for_legacy_decisions(src, dst)
        dst.commit()

        total_rows = 0
        for table in TABLES:
            name = table["name"]
            expected_columns = table["columns"]
            expected_conflict = table["conflict"]

            if not sqlite_table_exists(src, name):
                print(f"[SKIP][table] not found in SQLite: {name}")
                continue

            actual_columns = sqlite_table_columns(src, name)
            actual_set = set(actual_columns)
            selected_columns = [c for c in expected_columns if c in actual_set]
            missing_columns = [c for c in expected_columns if c not in actual_set]

            if missing_columns:
                print(
                    f"[SKIP][columns] {name}: missing in SQLite source -> "
                    + ", ".join(missing_columns)
                )

            if not selected_columns:
                print(f"[SKIP][table] {name}: no overlapping columns to migrate")
                continue

            conflict_columns = [c for c in expected_conflict if c in selected_columns]
            if expected_conflict and not conflict_columns:
                print(
                    f"[SKIP][conflict] {name}: conflict keys not found in source columns, "
                    "using plain INSERT"
                )

            select_sql = f"SELECT {', '.join(selected_columns)} FROM {name}"

            try:
                rows = src.execute(select_sql).fetchall()
            except Exception as exc:
                print(f"[WARN][table] {name}: failed to read source rows: {exc}")
                continue

            if not rows:
                print(f"[OK] {name}: 0 rows")
                continue

            upsert_sql = build_upsert_sql(name, selected_columns, conflict_columns)
            inserted = 0
            row_errors = 0
            skipped_fk = 0

            valid_zakupki = None
            if name in {"ai_results", "listings", "user_selections"}:
                valid_zakupki = load_target_values(dst, "zakupki", "reg_number")

            try:
                with dst.cursor() as cur:
                    for idx, row in enumerate(rows, start=1):
                        if name == "ai_results" and valid_zakupki is not None:
                            if "reg_number" in selected_columns and row["reg_number"] not in valid_zakupki:
                                skipped_fk += 1
                                continue
                        if name == "listings" and valid_zakupki is not None:
                            if (
                                "zakupka_reg_number" in selected_columns
                                and row["zakupka_reg_number"] not in valid_zakupki
                            ):
                                skipped_fk += 1
                                continue
                        if name == "user_selections" and valid_zakupki is not None:
                            if "reg_number" in selected_columns and row["reg_number"] not in valid_zakupki:
                                skipped_fk += 1
                                continue

                        values = [row[col] for col in selected_columns]
                        cur.execute("SAVEPOINT migrate_row")
                        try:
                            cur.execute(upsert_sql, values)
                            cur.execute("RELEASE SAVEPOINT migrate_row")
                            inserted += 1
                        except Exception as row_exc:
                            row_errors += 1
                            if row_errors <= MAX_ROW_WARNINGS_PER_TABLE:
                                print(f"[WARN][row] {name} #{idx}: {row_exc}")
                            elif row_errors == MAX_ROW_WARNINGS_PER_TABLE + 1:
                                print(
                                    f"[WARN][row] {name}: too many row errors, "
                                    "further row-level errors are suppressed"
                                )
                            cur.execute("ROLLBACK TO SAVEPOINT migrate_row")
                            cur.execute("RELEASE SAVEPOINT migrate_row")
                            continue
                dst.commit()
            except Exception as exc:
                dst.rollback()
                print(f"[WARN][table] {name}: failed to migrate table: {exc}")
                continue

            print(
                f"[OK] {name}: migrated {inserted} rows"
                + (f", skipped fk rows: {skipped_fk}" if skipped_fk else "")
                + (f", row errors: {row_errors}" if row_errors else "")
            )
            total_rows += inserted

        # Keep sequences in sync for tables with explicit id values.
        for table_name in ["users", "decisions", "user_overrides", "user_selections", "listings"]:
            try:
                sync_sequence(dst, table_name)
                dst.commit()
            except Exception as exc:
                dst.rollback()
                print(f"[WARN][sequence] {table_name}: {exc}")

        print(f"Migration completed successfully. Total rows: {total_rows}")
        return total_rows
    finally:
        src.close()
        dst.close()


def main() -> int:
    args = parse_args()
    try:
        migrate(
            sqlite_path=args.sqlite_path,
            database_url=args.database_url,
            schema_file=args.schema_file,
            reset=args.reset,
        )
        return 0
    except Exception as exc:
        print(f"Migration failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
