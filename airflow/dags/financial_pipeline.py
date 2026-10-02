
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

from pipeline_callbacks import write_dag_success_marker, write_task_failure_alert


PROJECT_HOME = "/opt/airflow"
DBT_PROJECT_DIR = f"{PROJECT_HOME}/dbt_project"
INGESTION_DIR = f"{PROJECT_HOME}/ingestion"
GREAT_EXPECTATIONS_DIR = f"{PROJECT_HOME}/great_expectations"

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": write_task_failure_alert,
}


def airflow_bash_task(task_id: str, command: str) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=f"set -euo pipefail; cd {PROJECT_HOME}; {command}",
    )


with DAG(
    dag_id="financial_data_warehouse_pipeline",
    description="Generate, ingest, transform, and validate financial warehouse data.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=2),
    on_success_callback=write_dag_success_marker,
    tags=["financial-warehouse", "dbt", "data-quality"],
) as dag:
    generate_customers = airflow_bash_task(
        "generate_customers",
        f"python {INGESTION_DIR}/generate_customers.py",
    )

    generate_transactions = airflow_bash_task(
        "generate_transactions",
        f"python {INGESTION_DIR}/generate_transactions.py",
    )

    ingest_raw_data = airflow_bash_task(
        "ingest_raw_data",
        f"python {INGESTION_DIR}/ingest_data.py",
    )

    run_dbt_models = airflow_bash_task(
        "run_dbt_models",
        f"dbt run --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}",
    )

    test_dbt_models = airflow_bash_task(
        "test_dbt_models",
        f"dbt test --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}",
    )

    run_data_quality = airflow_bash_task(
        "run_data_quality",
        f"python {GREAT_EXPECTATIONS_DIR}/run_data_quality.py",
    )

    generate_customers >> generate_transactions >> ingest_raw_data >> run_dbt_models >> test_dbt_models >> run_data_quality
