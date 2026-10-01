from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DAG_PATH = ROOT / "dags" / "financial_pipeline.py"

REQUIRED_TASKS = [
    "generate_customers",
    "generate_transactions",
    "ingest_raw_data",
    "run_dbt_models",
    "test_dbt_models",
    "run_data_quality",
]


def text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    if "\t" in value:
        raise AssertionError(f"{path}: tabs are not allowed")
    return value


def main() -> None:
    dag_source = text(DAG_PATH)
    ast.parse(dag_source)

    for required in [
        "financial_data_warehouse_pipeline",
        "schedule=\"@daily\"",
        "catchup=False",
        "max_active_runs=1",
        "retries",
        "retry_delay",
        "execution_timeout",
        "dbt run",
        "dbt test",
        "run_data_quality.py",
        ">>",
    ]:
        if required not in dag_source:
            raise AssertionError(f"{DAG_PATH}: missing {required}")

    for task_id in REQUIRED_TASKS:
        if f"\"{task_id}\"" not in dag_source:
            raise AssertionError(f"{DAG_PATH}: missing task {task_id}")

    expected_order = "generate_customers >> generate_transactions >> ingest_raw_data >> run_dbt_models >> test_dbt_models >> run_data_quality"
    if expected_order not in dag_source:
        raise AssertionError(f"{DAG_PATH}: task dependency order is incorrect")

    print("airflow dag validation passed")


if __name__ == "__main__":
    main()
