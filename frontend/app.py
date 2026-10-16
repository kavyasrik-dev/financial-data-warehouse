from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
ALLOWED_DAYS = {7, 30, 90}
LOGGER = logging.getLogger("frontend")

SECURITY_HEADERS = [
    (
        "Content-Security-Policy",
        "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    ),
    ("Permissions-Policy", "camera=(), geolocation=(), microphone=()"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
]

METRICS_SQL = """
select
    coalesce(sum(total_transactions), 0)::bigint as total_transactions,
    coalesce(sum(successful_transactions), 0)::bigint as successful_transactions,
    coalesce(sum(failed_transactions), 0)::bigint as failed_transactions,
    count(*)::integer as active_days,
    max(full_date) as data_through
from analytics.mart_daily_transaction_metrics
where full_date >= current_date - (%s - 1)
"""

DAILY_SQL = """
select
    full_date,
    total_transactions,
    successful_transactions,
    failed_transactions,
    pending_transactions
from analytics.mart_daily_transaction_metrics
where full_date >= current_date - (%s - 1)
order by full_date
"""

CATEGORY_SQL = """
select
    merchant_category,
    sum(total_transactions)::bigint as total_transactions
from analytics.mart_transaction_summary
group by merchant_category
order by total_transactions desc, merchant_category
limit 7
"""

STATUS_SQL = """
select
    transaction_status,
    sum(total_transactions)::bigint as total_transactions
from analytics.mart_transaction_summary
group by transaction_status
order by total_transactions desc, transaction_status
"""

CUSTOMERS_SQL = """
select
    customer_name_masked,
    customer_status,
    city,
    country,
    total_transactions,
    successful_transactions,
    failed_transactions,
    last_transaction_at
from analytics.mart_customer_activity
order by total_transactions desc, last_transaction_at desc
limit 8
"""

CUSTOMER_METRICS_SQL = """
select
    count(*)::integer as total_customers,
    count(*) filter (where lower(customer_status) = 'active')::integer as active_customers
from analytics.mart_customer_activity
"""


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def database_connection() -> Any:
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2 is required to connect to PostgreSQL") from error

    return psycopg2.connect(
        host=os.environ.get("WAREHOUSE_DB_HOST", "postgres"),
        port=int(os.environ.get("WAREHOUSE_DB_PORT", "5432")),
        dbname=os.environ.get("WAREHOUSE_DB_NAME", "financial_warehouse"),
        user=os.environ.get("WAREHOUSE_DB_USER", "metabase_reporting"),
        password=os.environ.get("WAREHOUSE_DB_PASSWORD"),
        connect_timeout=5,
        application_name="financial-warehouse-frontend",
        options="-c statement_timeout=5000 -c default_transaction_read_only=on",
    )


def fetch_rows(cursor: Any, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, parameters)
    columns = [getattr(column, "name", column[0]) for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def overview_data(days: int, connector: Callable[[], Any] = database_connection) -> dict[str, Any]:
    connection = connector()
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            metrics = fetch_rows(cursor, METRICS_SQL, (days,))[0]
            daily = fetch_rows(cursor, DAILY_SQL, (days,))
            categories = fetch_rows(cursor, CATEGORY_SQL)
            statuses = fetch_rows(cursor, STATUS_SQL)
            customers = fetch_rows(cursor, CUSTOMERS_SQL)
            customer_metrics = fetch_rows(cursor, CUSTOMER_METRICS_SQL)[0]
    finally:
        connection.close()

    total_transactions = int(metrics["total_transactions"])
    successful_transactions = int(metrics["successful_transactions"])
    active_days = int(metrics["active_days"])
    metrics.update(customer_metrics)
    metrics["success_rate"] = round(100 * successful_transactions / total_transactions, 1) if total_transactions else 0
    metrics["average_daily_transactions"] = round(total_transactions / active_days, 1) if active_days else 0

    return {
        "range_days": days,
        "generated_at": datetime.now(timezone.utc),
        "metrics": metrics,
        "daily": daily,
        "categories": categories,
        "statuses": statuses,
        "customers": customers,
        "links": {
            "airflow": os.environ.get("AIRFLOW_PUBLIC_URL", "http://localhost:8080"),
            "metabase": os.environ.get("METABASE_PUBLIC_URL", "http://localhost:3000"),
        },
    }


def database_ready(connector: Callable[[], Any] = database_connection) -> bool:
    connection = connector()
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute(
                "select "
                "to_regclass('analytics.mart_daily_transaction_metrics') is not null "
                "and to_regclass('analytics.mart_transaction_summary') is not null "
                "and to_regclass('analytics.mart_customer_activity') is not null"
            )
            return cursor.fetchone() == (True,)
    finally:
        connection.close()


def authorized(environ: dict[str, Any]) -> bool:
    expected_username = os.environ.get("FRONTEND_USERNAME")
    expected_password = os.environ.get("FRONTEND_PASSWORD")
    if not expected_username or not expected_password:
        return False

    scheme, _, token = environ.get("HTTP_AUTHORIZATION", "").partition(" ")
    if scheme.lower() != "basic" or not token:
        return False
    try:
        username, separator, password = base64.b64decode(token, validate=True).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return bool(
        separator
        and hmac.compare_digest(username, expected_username)
        and hmac.compare_digest(password, expected_password)
    )


def response(
    start_response: Callable[[str, list[tuple[str, str]]], Any],
    status: str,
    body: bytes,
    content_type: str,
    extra_headers: Iterable[tuple[str, str]] = (),
    head_only: bool = False,
) -> list[bytes]:
    headers = [
        ("Cache-Control", "no-store"),
        ("Content-Length", str(len(body))),
        ("Content-Type", content_type),
        *SECURITY_HEADERS,
        *extra_headers,
    ]
    start_response(status, headers)
    return [b"" if head_only else body]


def json_response(
    start_response: Callable[[str, list[tuple[str, str]]], Any],
    status: str,
    payload: dict[str, Any],
    head_only: bool = False,
) -> list[bytes]:
    body = json.dumps(payload, default=json_default, separators=(",", ":")).encode("utf-8")
    return response(start_response, status, body, "application/json; charset=utf-8", head_only=head_only)


def application(environ: dict[str, Any], start_response: Callable[[str, list[tuple[str, str]]], Any]) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    head_only = method == "HEAD"

    if method not in {"GET", "HEAD"}:
        return json_response(start_response, "405 Method Not Allowed", {"error": "method not allowed"}, head_only)

    if path == "/health":
        if not os.environ.get("FRONTEND_USERNAME") or not os.environ.get("FRONTEND_PASSWORD"):
            return json_response(start_response, "503 Service Unavailable", {"status": "unavailable"}, head_only)
        try:
            ready = database_ready()
        except Exception:
            LOGGER.exception("frontend database health check failed")
            ready = False
        status = "200 OK" if ready else "503 Service Unavailable"
        return json_response(start_response, status, {"status": "ok" if ready else "unavailable"}, head_only)

    if not authorized(environ):
        return response(
            start_response,
            "401 Unauthorized",
            b"Authentication required",
            "text/plain; charset=utf-8",
            [("WWW-Authenticate", 'Basic realm="Financial Warehouse", charset="UTF-8"')],
            head_only,
        )

    static_files = {
        "/": (STATIC_ROOT / "index.html", "text/html; charset=utf-8"),
        "/assets/styles.css": (STATIC_ROOT / "styles.css", "text/css; charset=utf-8"),
        "/assets/app.js": (STATIC_ROOT / "app.js", "text/javascript; charset=utf-8"),
    }
    if path in static_files:
        file_path, content_type = static_files[path]
        return response(start_response, "200 OK", file_path.read_bytes(), content_type, head_only=head_only)

    if path == "/api/overview":
        values = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        try:
            days = int(values.get("days", ["30"])[0])
        except ValueError:
            days = 0
        if days not in ALLOWED_DAYS:
            return json_response(start_response, "400 Bad Request", {"error": "days must be 7, 30, or 90"}, head_only)
        try:
            payload = overview_data(days)
        except Exception:
            LOGGER.exception("frontend overview query failed")
            return json_response(
                start_response,
                "503 Service Unavailable",
                {"error": "analytics temporarily unavailable"},
                head_only,
            )
        return json_response(start_response, "200 OK", payload, head_only)

    return json_response(start_response, "404 Not Found", {"error": "not found"}, head_only)

