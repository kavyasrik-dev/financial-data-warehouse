from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


METABASE_URL = os.environ.get("METABASE_URL", "http://metabase:3000").rstrip("/")
ANALYTICS_SCHEMA = "analytics"


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
        "name": "Financial Warehouse Analytics",
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


def ensure_analytics_database(session_id: str) -> None:
    databases = request_json("GET", "/api/database", token=session_id).get("data", [])
    payload = reporting_database_payload()
    for database in databases:
        if database.get("name") == payload["name"]:
            request_json("PUT", f"/api/database/{database['id']}", payload, token=session_id)
            return
    request_json("POST", "/api/database", payload, token=session_id)


def main() -> None:
    wait_for_metabase()
    session_id = setup_metabase_if_needed()
    ensure_analytics_database(session_id)
    print("metabase analytics-only setup completed")


if __name__ == "__main__":
    main()
