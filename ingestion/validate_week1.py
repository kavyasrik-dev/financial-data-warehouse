from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections import Counter
from pathlib import Path

import ingest_data


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(command: list[str], *, required: bool = True) -> tuple[bool, str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output = (result.stdout + result.stderr).strip()
    if result.returncode and required:
        raise RuntimeError(f"{' '.join(command)} failed\n{output}")
    return result.returncode == 0, output


def check_python() -> None:
    scripts = [
        "ingestion/generate_customers.py",
        "ingestion/generate_transactions.py",
        "ingestion/ingest_data.py",
    ]
    run([PYTHON, "-m", "py_compile", *scripts])
    run([PYTHON, "ingestion/generate_customers.py", "--self-check"])
    run([PYTHON, "ingestion/generate_transactions.py", "--self-check"])
    run([PYTHON, "ingestion/ingest_data.py", "--self-check"])
    run([PYTHON, "ingestion/ingest_data.py", "--dry-run"])


def check_duplicate_handling() -> None:
    for table in ingest_data.RAW_TABLES:
        rows = ingest_data.read_rows(table, "generated")
        hashes = [row[-1] for row in rows]
        duplicates = [item for item, count in Counter(hashes).items() if count > 1]
        assert not duplicates, f"{table.name}: duplicate source_record_hash values found"

    with (ROOT / "data/transactions/transactions.csv").open(newline="", encoding="utf-8") as file:
        transaction_ids = [row["transaction_id"] for row in csv.DictReader(file)]
    assert len(transaction_ids) == len(set(transaction_ids)), "transactions: duplicate transaction_id values found"


def check_docker(require_running: bool) -> None:
    run(["docker", "compose", "config", "--quiet"])
    engine_ready, engine_output = run(["docker", "info"], required=False)
    if not engine_ready:
        if require_running:
            raise RuntimeError(f"Docker engine is not reachable\n{engine_output}")
        print("WARN docker engine is not reachable; skipped live Docker/PostgreSQL checks")
        return

    ps_ready, ps_output = run(["docker", "compose", "ps"], required=False)
    if require_running and not ps_ready:
        raise RuntimeError(f"Docker services are not reachable\n{ps_output}")

    postgres_ready, postgres_output = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            "postgres",
            "-d",
            "financial_warehouse",
        ],
        required=False,
    )
    if require_running and not postgres_ready:
        raise RuntimeError(f"PostgreSQL is not ready\n{postgres_output}")
    if not postgres_ready:
        print("WARN PostgreSQL container is not ready; skipped live DB connection check")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Week 1 project setup.")
    parser.add_argument("--require-running-docker", action="store_true")
    args = parser.parse_args()

    check_docker(args.require_running_docker)
    check_python()
    check_duplicate_handling()
    print("Week 1 validation passed")


if __name__ == "__main__":
    main()
