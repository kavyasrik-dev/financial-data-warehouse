from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:  # pragma: no cover - lets --self-check run without a DB driver.
    psycopg2 = None
    execute_values = None


LOGGER = logging.getLogger("financial_ingestion")


@dataclass(frozen=True)
class RawTable:
    name: str
    path: Path
    table: str
    fields: tuple[str, ...]
    timestamp_fields: tuple[str, ...] = ()
    date_fields: tuple[str, ...] = ()
    numeric_fields: tuple[str, ...] = ()


RAW_TABLES = (
    RawTable(
        name="customers",
        path=Path("data/customers/customers.csv"),
        table="raw.customers",
        fields=(
            "customer_id",
            "customer_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "customer_status",
            "created_at",
        ),
        timestamp_fields=("created_at",),
    ),
    RawTable(
        name="cards",
        path=Path("data/cards/cards.csv"),
        table="raw.cards",
        fields=("card_id", "customer_id", "card_number", "card_type", "expiry_date", "card_status"),
        date_fields=("expiry_date",),
    ),
    RawTable(
        name="transactions",
        path=Path("data/transactions/transactions.csv"),
        table="raw.transactions",
        fields=(
            "transaction_id",
            "customer_id",
            "card_id",
            "transaction_timestamp",
            "amount",
            "currency",
            "merchant_name",
            "merchant_category",
            "transaction_type",
            "transaction_status",
        ),
        timestamp_fields=("transaction_timestamp",),
        numeric_fields=("amount",),
    ),
)


def db_config(args: argparse.Namespace) -> dict[str, str | int]:
    return {
        "host": args.host or os.getenv("WAREHOUSE_DB_HOST", "localhost"),
        "port": int(args.port or os.getenv("WAREHOUSE_DB_PORT", "5432")),
        "dbname": args.database or os.getenv("WAREHOUSE_DB_NAME", "financial_warehouse"),
        "user": args.user or os.getenv("WAREHOUSE_DB_USER", "warehouse_app"),
        "password": args.password or os.getenv("WAREHOUSE_DB_PASSWORD", "warehouse_app"),
    }


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def row_hash(row: dict[str, str], fields: Iterable[str]) -> str:
    payload = "|".join(row[field].strip() for field in fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_value(row: dict[str, str], table: RawTable) -> None:
    for field in table.fields:
        if row.get(field, "").strip() == "":
            raise ValueError(f"{table.name}: empty required field {field}")
    for field in table.timestamp_fields:
        datetime.fromisoformat(row[field].replace("Z", "+00:00"))
    for field in table.date_fields:
        datetime.fromisoformat(row[field])
    for field in table.numeric_fields:
        if float(row[field]) < 0:
            raise ValueError(f"{table.name}: {field} must be non-negative")


def read_rows(table: RawTable, source_system: str) -> list[tuple]:
    if not table.path.exists():
        raise FileNotFoundError(f"Missing source file: {table.path}")

    source_extracted_at = iso_utc(table.path.stat().st_mtime)
    rows = []
    with table.path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = set(table.fields) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{table.name}: missing columns {sorted(missing)}")

        for row in reader:
            validate_value(row, table)
            rows.append(
                tuple(row[field].strip() for field in table.fields)
                + (
                    source_system,
                    str(table.path),
                    source_extracted_at,
                    row_hash(row, table.fields),
                )
            )
    return rows


def chunks(rows: list[tuple], size: int) -> Iterable[list[tuple]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def create_ingestion_batch(cursor, table: RawTable, source_system: str) -> str:
    load_batch_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO raw.ingestion_batches (load_batch_id, source_system, source_name, pipeline_name)
        VALUES (%s, %s, %s, %s)
        """,
        (load_batch_id, source_system, str(table.path), "python_csv_ingestion"),
    )
    return load_batch_id


def insert_batch(cursor, table: RawTable, rows: list[tuple], load_batch_id: str, batch_size: int) -> int:
    columns = table.fields + (
        "source_system",
        "source_file",
        "source_extracted_at",
        "source_record_hash",
        "load_batch_id",
    )
    sql = f"""
        INSERT INTO {table.table} ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (source_record_hash) DO NOTHING
    """

    inserted = 0
    for batch in chunks(rows, batch_size):
        execute_values(cursor, sql, [row + (load_batch_id,) for row in batch])
        inserted += cursor.rowcount

    cursor.execute(
        """
        UPDATE raw.ingestion_batches
        SET completed_at = now(), status = 'completed', records_loaded = %s
        WHERE load_batch_id = %s
        """,
        (inserted, load_batch_id),
    )
    return inserted


def ingest(args: argparse.Namespace) -> None:
    selected = [table for table in RAW_TABLES if args.only in ("all", table.name)]

    if args.dry_run:
        for table in selected:
            LOGGER.info("validated %s rows from %s", len(read_rows(table, args.source_system)), table.path)
        return

    if psycopg2 is None or execute_values is None:
        raise RuntimeError("psycopg2 is required for database ingestion")

    config = db_config(args)
    with psycopg2.connect(**config) as conn:
        for table in selected:
            LOGGER.info("reading %s", table.path)
            rows = read_rows(table, args.source_system)
            LOGGER.info("loading %s rows into %s", len(rows), table.table)

            with conn.cursor() as cursor:
                load_batch_id = create_ingestion_batch(cursor, table, args.source_system)
            conn.commit()

            try:
                with conn.cursor() as cursor:
                    inserted = insert_batch(cursor, table, rows, load_batch_id, args.batch_size)
                conn.commit()
                LOGGER.info("loaded %s new %s rows", inserted, table.name)
            except Exception as error:
                conn.rollback()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE raw.ingestion_batches
                        SET completed_at = now(), status = 'failed', error_message = %s
                        WHERE load_batch_id = %s
                        """,
                        (str(error)[:1000], load_batch_id),
                    )
                conn.commit()
                LOGGER.exception("failed loading %s", table.name)
                raise


def self_check() -> None:
    row = {"id": "1", "amount": "10.50", "created_at": "2026-01-01T00:00:00+00:00"}
    table = RawTable("demo", Path("demo.csv"), "raw.demo", ("id", "amount", "created_at"), ("created_at",), (), ("amount",))
    validate_value(row, table)
    assert row_hash(row, table.fields) == row_hash(dict(row), table.fields)
    assert list(chunks([(1,), (2,), (3,)], 2)) == [[(1,), (2,)], [(3,)]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Load generated CSV files into PostgreSQL raw tables.")
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--database")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--source-system", default="generated")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--only", choices=["all", "customers", "cards", "transactions"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="Validate source CSV files without loading PostgreSQL.")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.self_check:
        self_check()
        return

    ingest(args)


if __name__ == "__main__":
    main()
