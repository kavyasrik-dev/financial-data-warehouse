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


def request(
    path: str,
    query: str = "",
    authenticated: bool = True,
    method: str = "GET",
    authorization_header: str | None = None,
) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
    }
    if authorization_header is not None:
        environ["HTTP_AUTHORIZATION"] = authorization_header
    elif authenticated:
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

    def test_malformed_authentication_is_rejected(self) -> None:
        status, _, body = request("/", authorization_header="Basic not-base64")
        self.assertEqual("401 Unauthorized", status)
        self.assertEqual(b"Authentication required", body)

    def test_static_endpoints_and_head(self) -> None:
        expected_types = {
            "/": "text/html; charset=utf-8",
            "/assets/styles.css": "text/css; charset=utf-8",
            "/assets/app.js": "text/javascript; charset=utf-8",
            "/assets/favicon.svg": "image/svg+xml",
        }
        for path, content_type in expected_types.items():
            with self.subTest(path=path):
                status, headers, body = request(path)
                self.assertEqual("200 OK", status)
                self.assertEqual(content_type, headers["Content-Type"])
                self.assertTrue(body)

        status, headers, body = request("/assets/app.js", method="HEAD")
        self.assertEqual("200 OK", status)
        self.assertEqual(b"", body)
        self.assertGreater(int(headers["Content-Length"]), 0)

    @patch.object(app, "database_ready", return_value=True)
    def test_health_endpoint_reports_ready(self, _database_ready: object) -> None:
        status, headers, body = request("/health", authenticated=False)
        self.assertEqual("200 OK", status)
        self.assertEqual({"status": "ok"}, json.loads(body))
        self.assertEqual("noindex, nofollow", headers["X-Robots-Tag"])

    @patch.object(app, "database_ready", return_value=False)
    def test_health_endpoint_reports_unavailable(self, _database_ready: object) -> None:
        status, _, body = request("/health", authenticated=False)
        self.assertEqual("503 Service Unavailable", status)
        self.assertEqual({"status": "unavailable"}, json.loads(body))

    def test_health_endpoint_requires_configured_credentials(self) -> None:
        with patch.dict(os.environ, {"FRONTEND_PASSWORD": ""}):
            status, _, body = request("/health", authenticated=False)
        self.assertEqual("503 Service Unavailable", status)
        self.assertEqual({"status": "unavailable"}, json.loads(body))

    def test_unknown_endpoint_and_unsupported_method(self) -> None:
        status, _, body = request("/does-not-exist")
        self.assertEqual("404 Not Found", status)
        self.assertEqual({"error": "not found"}, json.loads(body))

        status, headers, body = request("/api/overview", method="POST")
        self.assertEqual("405 Method Not Allowed", status)
        self.assertEqual("GET, HEAD", headers["Allow"])
        self.assertEqual({"error": "method not allowed"}, json.loads(body))

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
