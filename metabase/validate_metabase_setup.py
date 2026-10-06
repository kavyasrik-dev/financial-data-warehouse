from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    if "\t" in value:
        raise AssertionError(f"{path}: tabs are not allowed")
    return value


def assert_contains(path: Path, values: list[str]) -> None:
    source = text(path)
    for value in values:
        if value not in source:
            raise AssertionError(f"{path}: missing {value}")


def main() -> None:
    provision = ROOT / "metabase" / "provision_metabase.py"
    ast.parse(text(provision))

    assert_contains(
        ROOT / "postgres" / "init" / "00-create-app-databases.sql",
        [
            "metabase_reporting",
            "GRANT CONNECT ON DATABASE financial_warehouse TO metabase_reporting",
        ],
    )
    assert_contains(
        ROOT / "postgres" / "init" / "schemas.sql",
        [
            "GRANT USAGE ON SCHEMA analytics TO metabase_reporting",
            "GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO metabase_reporting",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics",
            "SET search_path = analytics, public",
        ],
    )
    assert_contains(
        ROOT / "docker-compose.yml",
        [
            "metabase-setup:",
            "METABASE_REPORTING_DB_USER",
            "METABASE_REPORTING_DB_PASSWORD",
            "condition: service_healthy",
            "python /opt/metabase/provision_metabase.py",
        ],
    )
    assert_contains(
        provision,
        [
            "schema-filters-type",
            "inclusion",
            "schema-filters-patterns",
            "analytics",
            "METABASE_REPORTING_DB_USER",
            "METABASE_REPORTING_DB_PASSWORD",
            "DASHBOARD_NAME",
            "Transaction Overview",
            "QUESTION_DEFINITIONS",
            "Total transactions",
            "Total transaction volume",
            "Average transaction amount",
            "Success rate",
            "Failure rate",
            "Transactions by day",
            "Transaction volume by category",
            "Success vs failed transactions",
            "analytics.mart_daily_transaction_metrics",
            "analytics.mart_transaction_summary",
            "ensure_transaction_dashboard",
            "/api/dashboard",
            "/api/card",
        ],
    )
    print("metabase setup validation passed")


if __name__ == "__main__":
    main()
