from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALERT_LOG = Path("/opt/airflow/logs/financial_pipeline_alerts.jsonl")


def append_pipeline_event(payload: dict[str, Any]) -> None:
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, sort_keys=True) + "\n")


def write_task_failure_alert(context: dict[str, Any]) -> None:
    task_instance = context["task_instance"]
    append_pipeline_event(
        {
            "event": "task_failed",
            "dag_id": task_instance.dag_id,
            "task_id": task_instance.task_id,
            "run_id": context.get("run_id"),
            "try_number": task_instance.try_number,
            "execution_date": str(context.get("logical_date")),
            "exception": str(context.get("exception")),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def write_dag_success_marker(context: dict[str, Any]) -> None:
    dag_run = context["dag_run"]
    append_pipeline_event(
        {
            "event": "dag_succeeded",
            "dag_id": dag_run.dag_id,
            "run_id": dag_run.run_id,
            "logical_date": str(dag_run.logical_date),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
    )
