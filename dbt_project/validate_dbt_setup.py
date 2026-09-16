from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = [
    ROOT / "dbt_project.yml",
    ROOT / "profiles.yml",
    ROOT / "models" / "staging" / "sources.yml",
    ROOT / "models" / "staging" / "schema.yml",
    ROOT / "models" / "staging" / "stg_customers.sql",
    ROOT / "models" / "staging" / "stg_cards.sql",
    ROOT / "models" / "staging" / "stg_transactions.sql",
    ROOT / "macros" / "generate_schema_name.sql",
]


def text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    if "\t" in value:
        raise AssertionError(f"{path}: tabs are not allowed in dbt YAML/SQL config")
    return value


def validate_files() -> None:
    for path in REQUIRED_FILES:
        if not path.exists():
            raise AssertionError(f"missing {path}")

    project = text(ROOT / "dbt_project.yml")
    profile = text(ROOT / "profiles.yml")
    sources = text(ROOT / "models" / "staging" / "sources.yml")

    assert "profile: financial_data_warehouse" in project
    assert "financial_data_warehouse:" in profile
    assert "type: postgres" in profile
    for env_name in ["WAREHOUSE_DB_HOST", "WAREHOUSE_DB_PORT", "WAREHOUSE_DB_NAME", "WAREHOUSE_DB_USER", "WAREHOUSE_DB_PASSWORD"]:
        assert env_name in profile, f"profiles.yml missing {env_name}"

    assert "schema: raw" in sources
    for source_name in ["customers", "cards", "transactions"]:
        assert f"name: {source_name}" in sources, f"sources.yml missing raw.{source_name}"

    for model_name, source_name in [
        ("stg_customers", "customers"),
        ("stg_cards", "cards"),
        ("stg_transactions", "transactions"),
    ]:
        model_sql = text(ROOT / "models" / "staging" / f"{model_name}.sql")
        assert f"source('raw', '{source_name}')" in model_sql, f"{model_name}.sql missing raw source ref"
        assert "row_number() over" in model_sql, f"{model_name}.sql missing duplicate handling"
        assert "nullif(trim(" in model_sql, f"{model_name}.sql missing null/trim cleanup"


def run_dbt_debug() -> None:
    if shutil.which("dbt") is None:
        raise RuntimeError("dbt is not installed on PATH")
    subprocess.run(
        ["dbt", "debug", "--project-dir", str(ROOT), "--profiles-dir", str(ROOT)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Day 8 dbt setup.")
    parser.add_argument("--run-dbt-debug", action="store_true")
    args = parser.parse_args()

    validate_files()
    if args.run_dbt_debug:
        run_dbt_debug()
    print("dbt setup validation passed")


if __name__ == "__main__":
    main()
