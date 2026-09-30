from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import great_expectations as gx


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "uncommitted" / "reports"
REPORT_PATH = REPORT_DIR / "data_quality_failures.json"

CHECKPOINTS = [
    "fact_transactions_checkpoint",
    "dim_customer_checkpoint",
    "dim_card_checkpoint",
]


def get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def checkpoint_failures(checkpoint_name: str, result: Any) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    run_results = get_value(result, "run_results", {})

    for validation_result in run_results.values():
        suite_result = get_value(validation_result, "validation_result", validation_result)
        for expectation_result in get_value(suite_result, "results", []):
            if get_value(expectation_result, "success"):
                continue
            expectation_config = get_value(expectation_result, "expectation_config", {})
            result_payload = get_value(expectation_result, "result", {})
            failures.append(
                {
                    "checkpoint": checkpoint_name,
                    "expectation_type": get_value(expectation_config, "expectation_type"),
                    "column": get_value(get_value(expectation_config, "kwargs", {}), "column"),
                    "observed_value": get_value(result_payload, "observed_value"),
                    "unexpected_count": get_value(result_payload, "unexpected_count"),
                }
            )
    return failures


def write_report(failures: list[dict[str, Any]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if failures else "passed",
        "failure_count": len(failures),
        "failures": failures,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    context = gx.get_context(context_root_dir=str(ROOT))
    failures: list[dict[str, Any]] = []

    for checkpoint_name in CHECKPOINTS:
        result = context.run_checkpoint(checkpoint_name=checkpoint_name)
        failures.extend(checkpoint_failures(checkpoint_name, result))

    write_report(failures)
    if failures:
        print(f"data quality failed: {len(failures)} failure(s); report={REPORT_PATH}")
        return 1

    print(f"data quality passed; report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
