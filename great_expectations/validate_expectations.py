from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTATIONS = ROOT / "expectations"
CONFIG = ROOT / "great_expectations.yml"

REQUIRED_SUITES = {
    "warehouse.fact_transactions.json": {
        ("expect_column_values_to_not_be_null", "transaction_id"),
        ("expect_column_values_to_be_unique", "transaction_id"),
        ("expect_column_values_to_not_be_null", "amount"),
        ("expect_column_values_to_be_between", "amount"),
        ("expect_column_values_to_not_be_null", "currency"),
        ("expect_column_values_to_be_in_set", "currency"),
        ("expect_column_values_to_not_be_null", "transaction_timestamp"),
    },
    "warehouse.dim_customer.json": {
        ("expect_column_values_to_not_be_null", "customer_id"),
        ("expect_column_values_to_not_be_null", "customer_status"),
        ("expect_column_values_to_be_in_set", "customer_status"),
    },
    "warehouse.dim_card.json": {
        ("expect_column_values_to_not_be_null", "masked_card_number"),
        ("expect_column_values_to_match_regex", "masked_card_number"),
    },
}


def read_suite(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        suite = json.load(file)
    if not isinstance(suite.get("expectations"), list):
        raise AssertionError(f"{path}: expectations must be a list")
    return suite


def expectation_keys(suite: dict) -> set[tuple[str, str]]:
    keys = set()
    for expectation in suite["expectations"]:
        expectation_type = expectation.get("expectation_type")
        column = expectation.get("kwargs", {}).get("column")
        if not expectation_type or not column:
            raise AssertionError(f"invalid expectation entry: {expectation}")
        keys.add((expectation_type, column))
    return keys


def validate_suite(name: str, required: set[tuple[str, str]]) -> None:
    path = EXPECTATIONS / name
    if not path.exists():
        raise AssertionError(f"missing expectation suite {path}")

    suite = read_suite(path)
    expected_suite_name = name.removesuffix(".json")
    if suite.get("expectation_suite_name") != expected_suite_name:
        raise AssertionError(f"{path}: expectation_suite_name must be {expected_suite_name}")

    missing = required - expectation_keys(suite)
    if missing:
        raise AssertionError(f"{path}: missing expectations {sorted(missing)}")

    if name == "warehouse.fact_transactions.json":
        amount_expectation = next(
            expectation
            for expectation in suite["expectations"]
            if expectation["expectation_type"] == "expect_column_values_to_be_between"
            and expectation["kwargs"]["column"] == "amount"
        )
        if amount_expectation["kwargs"].get("min_value") != 0 or amount_expectation["kwargs"].get("strict_min") is not True:
            raise AssertionError(f"{path}: amount expectation must enforce amount > 0")

    if name == "warehouse.dim_card.json":
        regex_expectation = next(
            expectation
            for expectation in suite["expectations"]
            if expectation["expectation_type"] == "expect_column_values_to_match_regex"
        )
        if regex_expectation["kwargs"].get("regex") != r"^\*+[0-9]{4}$":
            raise AssertionError(f"{path}: masked card regex is incorrect")


def main() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    for required_text in [
        "financial_warehouse:",
        "SqlAlchemyExecutionEngine",
        "postgresql+psycopg2://${WAREHOUSE_DB_USER}",
        "expectations_store",
        "checkpoint_store",
        "anonymous_usage_statistics:",
        "enabled: false",
    ]:
        if required_text not in config:
            raise AssertionError(f"{CONFIG}: missing {required_text}")

    for suite_name, required in REQUIRED_SUITES.items():
        validate_suite(suite_name, required)
    print("great expectations validation passed")


if __name__ == "__main__":
    main()
