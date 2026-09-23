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
    ROOT / "models" / "warehouse" / "int_customer_scd_events.sql",
    ROOT / "models" / "warehouse" / "dim_customer.sql",
    ROOT / "models" / "warehouse" / "dim_card.sql",
    ROOT / "models" / "warehouse" / "schema.yml",
    ROOT / "macros" / "generate_schema_name.sql",
    ROOT / "macros" / "pii_masking.sql",
    ROOT / "macros" / "scd_type2.sql",
    ROOT / "tests" / "assert_dim_customer_current_open_ended.sql",
    ROOT / "tests" / "assert_dim_card_masked_numbers.sql",
    ROOT / "tests" / "assert_dim_card_customer_referential_integrity.sql",
    ROOT / "tests" / "assert_dim_customer_history_coverage.sql",
    ROOT / "tests" / "assert_dim_customer_masked_pii.sql",
    ROOT / "tests" / "assert_dim_customer_no_overlaps.sql",
    ROOT / "tests" / "assert_dim_customer_one_current_record.sql",
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

    masking = text(ROOT / "macros" / "pii_masking.sql")
    for macro_name in ["mask_email", "mask_phone", "mask_card", "mask_name"]:
        assert f"macro {macro_name}" in masking, f"pii_masking.sql missing {macro_name}"

    customers_sql = text(ROOT / "models" / "staging" / "stg_customers.sql")
    cards_sql = text(ROOT / "models" / "staging" / "stg_cards.sql")
    for expected in ["customer_name_masked", "email_masked", "phone_masked"]:
        assert expected in customers_sql, f"stg_customers.sql missing {expected}"
    assert "card_number_masked" in cards_sql, "stg_cards.sql missing card_number_masked"

    scd_macro = text(ROOT / "macros" / "scd_type2.sql")
    scd_model = text(ROOT / "models" / "warehouse" / "int_customer_scd_events.sql")
    warehouse_schema = text(ROOT / "models" / "warehouse" / "schema.yml")
    assert "macro customer_scd_record_hash" in scd_macro, "scd_type2.sql missing customer SCD hash macro"
    for tracked_attribute in ["email", "phone", "address", "customer_status"]:
        assert tracked_attribute in scd_macro, f"SCD hash missing {tracked_attribute}"
    for required_sql in [
        "ref('stg_customers')",
        "customer_scd_record_hash()",
        "lag(record_hash) over",
        "lead(created_at) over",
        "effective_from",
        "effective_to",
        "is_current",
    ]:
        assert required_sql in scd_model, f"int_customer_scd_events.sql missing {required_sql}"
    for tested_column in ["customer_id", "effective_from", "effective_to", "is_current", "record_hash"]:
        assert f"name: {tested_column}" in warehouse_schema, f"warehouse schema missing {tested_column} test"

    dim_customer = text(ROOT / "models" / "warehouse" / "dim_customer.sql")
    for required_sql in [
        "ref('int_customer_scd_events')",
        "customer_sk",
        "customer_name_masked",
        "email_masked",
        "phone_masked",
        "effective_from",
        "effective_to",
        "is_current",
        "record_hash",
    ]:
        assert required_sql in dim_customer, f"dim_customer.sql missing {required_sql}"
    for sensitive_column in ["customer_name,", "email,", "phone,"]:
        assert sensitive_column not in dim_customer, f"dim_customer.sql exposes raw PII column {sensitive_column}"
    for test_name in [
        "assert_dim_customer_current_open_ended.sql",
        "assert_dim_customer_history_coverage.sql",
        "assert_dim_customer_masked_pii.sql",
        "assert_dim_customer_no_overlaps.sql",
        "assert_dim_customer_one_current_record.sql",
    ]:
        assert "ref('dim_customer')" in text(ROOT / "tests" / test_name), f"{test_name} missing dim_customer ref"

    dim_card = text(ROOT / "models" / "warehouse" / "dim_card.sql")
    for required_sql in [
        "ref('stg_cards')",
        "card_sk",
        "card_id",
        "customer_id",
        "card_number_masked as masked_card_number",
        "card_type",
        "expiry_date",
        "card_status",
    ]:
        assert required_sql in dim_card, f"dim_card.sql missing {required_sql}"
    for line in dim_card.splitlines():
        selected_column = line.strip().lower()
        assert selected_column not in {"card_number", "card_number,"}, "dim_card.sql exposes raw card number"
        assert not selected_column.startswith("card_number as "), "dim_card.sql exposes raw card number"
    for tested_column in ["card_sk", "card_id", "masked_card_number", "card_type", "card_status"]:
        assert f"name: {tested_column}" in warehouse_schema, f"warehouse schema missing {tested_column} test"
    card_mask_test = text(ROOT / "tests" / "assert_dim_card_masked_numbers.sql")
    assert "ref('dim_card')" in card_mask_test, "assert_dim_card_masked_numbers.sql missing dim_card ref"
    assert "masked_card_number" in card_mask_test, "assert_dim_card_masked_numbers.sql missing masked_card_number check"
    card_ri_test = text(ROOT / "tests" / "assert_dim_card_customer_referential_integrity.sql")
    assert "ref('dim_card')" in card_ri_test, "card referential integrity test missing dim_card ref"
    assert "ref('dim_customer')" in card_ri_test, "card referential integrity test missing dim_customer ref"
    customer_history_test = text(ROOT / "tests" / "assert_dim_customer_history_coverage.sql")
    assert "ref('stg_customers')" in customer_history_test, "customer history coverage test missing stg_customers ref"
    customer_mask_test = text(ROOT / "tests" / "assert_dim_customer_masked_pii.sql")
    for masked_column in ["email_masked", "phone_masked", "customer_name_masked"]:
        assert masked_column in customer_mask_test, f"customer masking test missing {masked_column}"


def run_dbt_command(*args: str) -> None:
    if shutil.which("dbt") is None:
        raise RuntimeError("dbt is not installed on PATH")
    subprocess.run(
        ["dbt", *args, "--project-dir", str(ROOT), "--profiles-dir", str(ROOT)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dbt setup and Week 2 integration checks.")
    parser.add_argument("--run-dbt-debug", action="store_true")
    parser.add_argument("--run-dbt-integration", action="store_true")
    args = parser.parse_args()

    validate_files()
    if args.run_dbt_debug:
        run_dbt_command("debug")
    if args.run_dbt_integration:
        run_dbt_command("run")
        run_dbt_command("test")
    print("dbt setup validation passed")


if __name__ == "__main__":
    main()
