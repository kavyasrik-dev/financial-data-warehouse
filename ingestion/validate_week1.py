from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import ingest_data


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(command: list[str], *, required: bool = True, stdout_only: bool = False) -> tuple[bool, str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    combined_output = (result.stdout + result.stderr).strip()
    if result.returncode and required:
        raise RuntimeError(f"{' '.join(command)} failed\n{combined_output}")
    output = result.stdout.strip() if stdout_only else combined_output
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


def check_docker(require_running: bool) -> bool:
    run(["docker", "compose", "config", "--quiet"])
    engine_ready, engine_output = run(["docker", "info"], required=False)
    if not engine_ready:
        if require_running:
            raise RuntimeError(f"Docker engine is not reachable\n{engine_output}")
        print("WARN docker engine is not reachable; skipped live security checks")
        return False

    ps_ready, ps_output = run(
        ["docker", "compose", "ps", "--services", "--status", "running"],
        required=False,
    )
    required_services = {"postgres", "airflow-api-server", "metabase"}
    running_services = set(ps_output.splitlines()) if ps_ready else set()
    missing_services = required_services - running_services
    if missing_services:
        message = f"required Docker services are not running: {', '.join(sorted(missing_services))}"
        if require_running:
            raise RuntimeError(message)
        print(f"WARN {message}; skipped live security checks")
        return False

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
        print("WARN PostgreSQL container is not ready; skipped live security checks")
        return False
    return True


def check_untrusted_access() -> None:
    anonymous_requests = [
        ("Airflow", "airflow-api-server", "http://localhost:8080/api/v2/dags?limit=1"),
        ("Metabase", "metabase", "http://localhost:3000/api/database"),
    ]
    for name, service, url in anonymous_requests:
        _, output = run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                service,
                "curl",
                "--silent",
                "--show-error",
                "--output",
                "/dev/null",
                "--write-out",
                "HTTP_STATUS:%{http_code}",
                "--max-time",
                "10",
                url,
            ],
            stdout_only=True,
        )
        statuses = [
            line.removeprefix("HTTP_STATUS:")
            for line in output.splitlines()
            if line.startswith("HTTP_STATUS:")
        ]
        if len(statuses) != 1:
            raise AssertionError(f"{name} anonymous request did not return one HTTP status")
        status = statuses[0]
        if status not in {"401", "403"}:
            raise AssertionError(f"{name} anonymous request returned HTTP {status}, expected 401 or 403")

    _, config_output = run(
        ["docker", "compose", "config", "--format", "json"],
        stdout_only=True,
    )
    config = json.loads(config_output)
    postgres_env = config["services"]["postgres"]["environment"]
    bootstrap_env = config["services"]["postgres-bootstrap"]["environment"]
    postgres_user = postgres_env["POSTGRES_USER"]
    warehouse_database = bootstrap_env["WAREHOUSE_DB_NAME"]
    reporting_user = bootstrap_env["METABASE_REPORTING_DB_USER"]
    access_granted, access_output = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-X",
            "--set",
            "ON_ERROR_STOP=1",
            "--set",
            f"reporting_user={reporting_user}",
            "--username",
            postgres_user,
            "--dbname",
            warehouse_database,
            "--command",
            'SET ROLE :"reporting_user"; SELECT customer_id FROM raw.customers LIMIT 1;',
        ],
        required=False,
    )
    if access_granted or "permission denied" not in access_output.lower():
        raise AssertionError("metabase reporting role was not conclusively denied access to raw customer PII")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Week 1 project setup.")
    parser.add_argument("--require-running-docker", action="store_true")
    args = parser.parse_args()

    if check_docker(args.require_running_docker):
        check_untrusted_access()
    check_python()
    check_duplicate_handling()
    print("Week 1 validation passed")


if __name__ == "__main__":
    main()
