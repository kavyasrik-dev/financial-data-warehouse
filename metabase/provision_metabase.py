from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


METABASE_URL = os.environ.get("METABASE_URL", "http://metabase:3000").rstrip("/")
ANALYTICS_SCHEMA = "analytics"
DATABASE_NAME = "Financial Warehouse Analytics"
DASHBOARD_NAME = "Transaction Overview"

QUESTION_DEFINITIONS = [
    {
        "name": "Total transactions",
        "display": "scalar",
        "query": "select sum(total_transactions) as total_transactions from analytics.mart_daily_transaction_metrics",
        "position": {"row": 0, "col": 0, "size_x": 4, "size_y": 3},
    },
    {
        "name": "Total transaction volume",
        "display": "scalar",
        "query": "select sum(total_transaction_amount) as total_transaction_volume from analytics.mart_daily_transaction_metrics",
        "position": {"row": 0, "col": 4, "size_x": 4, "size_y": 3},
    },
    {
        "name": "Average transaction amount",
        "display": "scalar",
        "query": (
            "select round(sum(total_transaction_amount) / nullif(sum(total_transactions), 0), 2) "
            "as average_transaction_amount from analytics.mart_daily_transaction_metrics"
        ),
        "position": {"row": 0, "col": 8, "size_x": 4, "size_y": 3},
    },
    {
        "name": "Success rate",
        "display": "scalar",
        "query": (
            "select round(100.0 * sum(successful_transactions) / nullif(sum(total_transactions), 0), 2) "
            "as success_rate_percent from analytics.mart_daily_transaction_metrics"
        ),
        "position": {"row": 3, "col": 0, "size_x": 6, "size_y": 3},
    },
    {
        "name": "Failure rate",
        "display": "scalar",
        "query": (
            "select round(100.0 * sum(failed_transactions) / nullif(sum(total_transactions), 0), 2) "
            "as failure_rate_percent from analytics.mart_daily_transaction_metrics"
        ),
        "position": {"row": 3, "col": 6, "size_x": 6, "size_y": 3},
    },
    {
        "name": "Transactions by day",
        "display": "line",
        "query": (
            "select full_date, total_transactions from analytics.mart_daily_transaction_metrics "
            "order by full_date"
        ),
        "position": {"row": 6, "col": 0, "size_x": 12, "size_y": 6},
    },
    {
        "name": "Transaction volume by category",
        "display": "bar",
        "query": (
            "select merchant_category, sum(total_transaction_amount) as transaction_volume "
            "from analytics.mart_transaction_summary group by merchant_category order by transaction_volume desc"
        ),
        "position": {"row": 12, "col": 0, "size_x": 6, "size_y": 6},
    },
    {
        "name": "Success vs failed transactions",
        "display": "bar",
        "query": (
            "select transaction_status, sum(total_transactions) as total_transactions "
            "from analytics.mart_transaction_summary where transaction_status in ('success', 'failed') "
            "group by transaction_status order by transaction_status"
        ),
        "position": {"row": 12, "col": 6, "size_x": 6, "size_y": 6},
    },
]


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise RuntimeError(f"missing required environment variable {name}")
    return value


def request_json(method: str, path: str, payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Metabase-Session"] = token
    request = urllib.request.Request(f"{METABASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def wait_for_metabase() -> None:
    for _ in range(60):
        try:
            request_json("GET", "/api/health")
            return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2)
    raise RuntimeError("metabase did not become healthy")


def reporting_database_payload() -> dict[str, Any]:
    return {
        "name": DATABASE_NAME,
        "engine": "postgres",
        "details": {
            "host": env("METABASE_REPORTING_DB_HOST", "postgres"),
            "port": int(env("METABASE_REPORTING_DB_PORT", "5432")),
            "dbname": env("METABASE_REPORTING_DB_NAME", "financial_warehouse"),
            "user": env("METABASE_REPORTING_DB_USER", "metabase_reporting"),
            "password": env("METABASE_REPORTING_DB_PASSWORD"),
            "ssl": False,
            "tunnel-enabled": False,
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": ANALYTICS_SCHEMA,
        },
        "is_full_sync": True,
        "is_on_demand": False,
        "schedules": {
            "metadata_sync": {"schedule_type": "daily", "schedule_hour": 2},
            "cache_field_values": {"schedule_type": "daily", "schedule_hour": 3},
        },
    }


def setup_metabase_if_needed() -> str:
    properties = request_json("GET", "/api/session/properties")
    setup_token = properties.get("setup-token")
    if setup_token:
        payload = {
            "token": setup_token,
            "user": {
                "email": env("METABASE_ADMIN_EMAIL"),
                "password": env("METABASE_ADMIN_PASSWORD"),
                "first_name": env("METABASE_ADMIN_FIRST_NAME", "Admin"),
                "last_name": env("METABASE_ADMIN_LAST_NAME", "User"),
            },
            "database": reporting_database_payload(),
            "prefs": {"site_name": "Financial Data Warehouse", "allow_tracking": False},
        }
        response = request_json("POST", "/api/setup", payload)
        return response["id"]
    return login()


def login() -> str:
    response = request_json(
        "POST",
        "/api/session",
        {
            "username": env("METABASE_ADMIN_EMAIL"),
            "password": env("METABASE_ADMIN_PASSWORD"),
        },
    )
    return response["id"]


def ensure_analytics_database(session_id: str) -> int:
    databases = request_json("GET", "/api/database", token=session_id).get("data", [])
    payload = reporting_database_payload()
    for database in databases:
        if database.get("name") == payload["name"]:
            request_json("PUT", f"/api/database/{database['id']}", payload, token=session_id)
            return int(database["id"])
    created = request_json("POST", "/api/database", payload, token=session_id)
    return int(created["id"])


def card_payload(database_id: int, definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": definition["name"],
        "display": definition["display"],
        "dataset_query": {
            "database": database_id,
            "type": "native",
            "native": {"query": definition["query"]},
        },
        "visualization_settings": {},
    }


def ensure_card(session_id: str, database_id: int, definition: dict[str, Any]) -> int:
    cards = request_json("GET", f"/api/card?f=all&query={urllib.parse.quote(definition['name'])}", token=session_id)
    for card in cards.get("data", []):
        if card.get("name") == definition["name"]:
            request_json("PUT", f"/api/card/{card['id']}", card_payload(database_id, definition), token=session_id)
            return int(card["id"])
    created = request_json("POST", "/api/card", card_payload(database_id, definition), token=session_id)
    return int(created["id"])


def ensure_dashboard(session_id: str) -> int:
    dashboards = request_json("GET", f"/api/dashboard?query={urllib.parse.quote(DASHBOARD_NAME)}", token=session_id)
    for dashboard in dashboards.get("data", []):
        if dashboard.get("name") == DASHBOARD_NAME:
            return int(dashboard["id"])
    created = request_json("POST", "/api/dashboard", {"name": DASHBOARD_NAME}, token=session_id)
    return int(created["id"])


def dashboard_cards(session_id: str, dashboard_id: int) -> list[dict[str, Any]]:
    dashboard = request_json("GET", f"/api/dashboard/{dashboard_id}", token=session_id)
    return dashboard.get("dashcards", [])


def ensure_dashboard_card(session_id: str, dashboard_id: int, card_id: int, position: dict[str, int]) -> None:
    for dashboard_card in dashboard_cards(session_id, dashboard_id):
        if dashboard_card.get("card_id") == card_id:
            request_json("PUT", f"/api/dashboard/{dashboard_id}/cards/{dashboard_card['id']}", position, token=session_id)
            return
    created = request_json("POST", f"/api/dashboard/{dashboard_id}/cards", {"cardId": card_id}, token=session_id)
    request_json("PUT", f"/api/dashboard/{dashboard_id}/cards/{created['id']}", position, token=session_id)


def ensure_transaction_dashboard(session_id: str, database_id: int) -> None:
    dashboard_id = ensure_dashboard(session_id)
    for definition in QUESTION_DEFINITIONS:
        card_id = ensure_card(session_id, database_id, definition)
        ensure_dashboard_card(session_id, dashboard_id, card_id, definition["position"])


def main() -> None:
    wait_for_metabase()
    session_id = setup_metabase_if_needed()
    database_id = ensure_analytics_database(session_id)
    ensure_transaction_dashboard(session_id, database_id)
    print("metabase analytics-only setup completed")


if __name__ == "__main__":
    main()
