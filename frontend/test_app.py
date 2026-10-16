from __future__ import annotations

import base64
import json
import os
import unittest
from unittest.mock import patch

import app


def authorization() -> str:
    token = base64.b64encode(b"analyst:correct-horse-battery-staple").decode("ascii")
    return f"Basic {token}"


def request(path: str, query: str = "", authenticated: bool = True) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
    }
    if authenticated:
        environ["HTTP_AUTHORIZATION"] = authorization()
    body = b"".join(app.application(environ, start_response))
    return str(captured["status"]), dict(captured["headers"]), body


class FakeCursor:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self.responses = iter(responses)
        self.description: list[tuple[str]] = []
        self.rows: list[tuple[object, ...]] = []
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...] = ()) -> None:
        response = next(self.responses)
        keys = list(response[0]) if response else []
        self.description = [(key,) for key in keys]
        self.rows = [tuple(row[key] for key in keys) for row in response]
        self.executions.append((query, parameters))

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class FakeConnection:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self.cursor_instance = FakeCursor(responses)
        self.session: dict[str, bool] = {}
        self.closed = False

    def set_session(self, **values: bool) -> None:
        self.session = values

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


class ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "FRONTEND_USERNAME": "analyst",
                "FRONTEND_PASSWORD": "correct-horse-battery-staple",
            },
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()

    def test_authentication_is_required(self) -> None:
        status, headers, body = request("/", authenticated=False)
        self.assertEqual("401 Unauthorized", status)
        self.assertIn("Basic realm=", headers["WWW-Authenticate"])
        self.assertNotIn(b"correct-horse", body)

    def test_overview_is_returned_with_security_headers(self) -> None:
        payload = {"range_days": 30, "metrics": {"total_transactions": 42}}
        with patch.object(app, "overview_data", return_value=payload):
            status, headers, body = request("/api/overview", "days=30")
        self.assertEqual("200 OK", status)
        self.assertEqual(payload, json.loads(body))
        self.assertEqual("DENY", headers["X-Frame-Options"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_date_range_is_allowlisted(self) -> None:
        with patch.object(app, "overview_data") as overview:
            status, _, body = request("/api/overview", "days=365")
        self.assertEqual("400 Bad Request", status)
        self.assertEqual({"error": "days must be 7, 30, or 90"}, json.loads(body))
        overview.assert_not_called()

    def test_database_errors_are_hidden(self) -> None:
        with (
            patch.object(app, "overview_data", side_effect=RuntimeError("secret connection detail")),
            patch.object(app.LOGGER, "exception") as logged,
        ):
            status, _, body = request("/api/overview")
        self.assertEqual("503 Service Unavailable", status)
        self.assertNotIn(b"secret connection detail", body)
        logged.assert_called_once()

    def test_overview_queries_are_parameterized_and_read_only(self) -> None:
        connection = FakeConnection(
            [
                [{
                    "total_transactions": 10,
                    "successful_transactions": 8,
                    "failed_transactions": 1,
                    "active_days": 2,
                    "data_through": "2026-10-16",
                }],
                [{"full_date": "2026-10-16", "total_transactions": 10}],
                [{"merchant_category": "retail", "total_transactions": 10}],
                [{"transaction_status": "success", "total_transactions": 8}],
                [{"customer_name_masked": "A*** B***", "total_transactions": 10}],
                [{"total_customers": 4, "active_customers": 3}],
            ]
        )
        payload = app.overview_data(7, connector=lambda: connection)
        self.assertEqual({"readonly": True, "autocommit": True}, connection.session)
        self.assertTrue(connection.closed)
        self.assertEqual((7,), connection.cursor_instance.executions[0][1])
        self.assertEqual((7,), connection.cursor_instance.executions[1][1])
        self.assertEqual(80.0, payload["metrics"]["success_rate"])
        self.assertEqual(5.0, payload["metrics"]["average_daily_transactions"])


if __name__ == "__main__":
    unittest.main()
