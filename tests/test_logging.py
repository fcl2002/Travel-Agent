from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import json
import logging

from fastapi.testclient import TestClient
import pytest

from app.core.logging import JSONFormatter, configure_logging, request_id
from app.main import create_app


@pytest.fixture
def logs():
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("app")
    logger.addHandler(handler)
    try:
        yield output
    finally:
        logger.removeHandler(handler)
        handler.close()


def entries(logs):
    return [json.loads(line) for line in logs.getvalue().splitlines()]


def test_request_logs_omit_credentials_and_use_route_template(logs):
    app = create_app()

    @app.post("/logging-test/{value}")
    async def endpoint(value: str):
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post(
            "/logging-test/private-path?token=private-query",
            headers={"Authorization": "Bearer private-token", "Cookie": "refresh=private-cookie"},
            json={"password": "PrivatePassword1!", "email": "private@example.com"},
        )
        missing = client.get("/private-unmatched-path?token=private-query")

    completed = [entry for entry in entries(logs) if entry["event"] == "request_completed"]
    entry = completed[0]
    assert entry["route"] == "/logging-test/{value}"
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["method"] == "POST" and entry["status_code"] == 200
    assert entry["level"] == "INFO" and entry["duration_ms"] >= 0
    assert completed[1]["route"] == "<unmatched>"
    assert completed[1]["status_code"] == 404 and completed[1]["level"] == "WARNING"
    assert completed[1]["request_id"] == missing.headers["X-Request-ID"]
    assert "private" not in logs.getvalue().lower()
    assert request_id.get() is None


def test_unexpected_errors_log_trace_locations_without_exception_values(logs):
    app = create_app()

    @app.get("/logging-error")
    async def endpoint():
        raise RuntimeError("private-password-and-database-url")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/logging-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    failure = next(entry for entry in entries(logs) if entry["event"] == "request_failed")
    assert failure["level"] == "ERROR" and failure["status_code"] == 500
    assert failure["request_id"] == response.headers["X-Request-ID"]
    assert failure["error_type"] == "RuntimeError"
    assert failure["traceback"][-1]["function"] == "endpoint"
    assert "private-password-and-database-url" not in logs.getvalue()
    assert request_id.get() is None


def test_concurrent_requests_have_independent_log_context(logs):
    with TestClient(create_app()) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: client.get("/health"), range(8)))

    identifiers = {response.headers["X-Request-ID"] for response in responses}
    completed = [entry for entry in entries(logs) if entry["event"] == "request_completed"]
    assert len(identifiers) == 8
    assert {entry["request_id"] for entry in completed} == identifiers


def test_logging_configuration_does_not_duplicate_handlers():
    logger = logging.getLogger("app")
    original_level = logger.level
    try:
        configure_logging("WARNING")
        configure_logging("WARNING")
        assert logger.level == logging.WARNING
        assert sum(handler.name == "travel_agent_json" for handler in logger.handlers) == 1
    finally:
        logger.setLevel(original_level)
