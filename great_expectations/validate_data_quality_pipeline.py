from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHECKPOINTS = ROOT / "checkpoints"
EXPECTATIONS = ROOT / "expectations"
RUNNER = ROOT / "run_data_quality.py"

CHECKPOINT_FILES = {
    "fact_transactions_checkpoint.yml": ("warehouse.fact_transactions", "warehouse.fact_transactions"),
    "dim_customer_checkpoint.yml": ("warehouse.dim_customer", "warehouse.dim_customer"),
    "dim_card_checkpoint.yml": ("warehouse.dim_card", "warehouse.dim_card"),
}


def assert_contains(path: Path, required: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for value in required:
        if value not in text:
            raise AssertionError(f"{path}: missing {value}")


def validate_checkpoint(name: str, asset_and_suite: tuple[str, str]) -> None:
    asset_name, suite_name = asset_and_suite
    path = CHECKPOINTS / name
    if not path.exists():
        raise AssertionError(f"missing checkpoint {path}")
    assert_contains(
        path,
        [
            "class_name: Checkpoint",
            "datasource_name: financial_warehouse",
            "data_connector_name: default_inferred_data_connector_name",
            f"data_asset_name: {asset_name}",
            f"expectation_suite_name: {suite_name}",
            "StoreValidationResultAction",
            "UpdateDataDocsAction",
        ],
    )


def validate_runner() -> None:
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    imports = {alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names}
    if "great_expectations" not in imports:
        raise AssertionError(f"{RUNNER}: must import great_expectations")

    assert_contains(
        RUNNER,
        [
            "CHECKPOINTS",
            "fact_transactions_checkpoint",
            "dim_customer_checkpoint",
            "dim_card_checkpoint",
            "run_checkpoint",
            "data_quality_failures.json",
            "return 1",
            "return 0",
        ],
    )


def validate_expectation_json() -> None:
    for _, (_, suite_name) in CHECKPOINT_FILES.items():
        path = EXPECTATIONS / f"{suite_name}.json"
        suite = json.loads(path.read_text(encoding="utf-8"))
        if suite.get("expectation_suite_name") != suite_name:
            raise AssertionError(f"{path}: suite name mismatch")
        if not suite.get("expectations"):
            raise AssertionError(f"{path}: expectations cannot be empty")


def main() -> None:
    for checkpoint, asset_and_suite in CHECKPOINT_FILES.items():
        validate_checkpoint(checkpoint, asset_and_suite)
    validate_runner()
    validate_expectation_json()
    print("data quality pipeline validation passed")


if __name__ == "__main__":
    main()
