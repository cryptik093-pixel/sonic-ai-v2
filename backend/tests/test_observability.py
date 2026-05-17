import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JSONFormatter
from app.main import create_app


def test_request_id_header_is_generated_for_success_responses() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {
        "status": "ok",
        "service": "sonic-ai-v2-backend",
        "version": "0.1.0",
    }


def test_request_id_header_echoes_client_value_for_validation_errors() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/analyze",
        headers={"X-Request-ID": "contract-test-request"},
    )

    assert response.status_code == 422
    assert response.headers["x-request-id"] == "contract-test-request"
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "invalid_request",
            "message": "Request validation failed.",
        },
    }


def test_request_id_header_echoes_client_value_for_http_errors() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v2/does-not-exist",
        headers={"X-Request-ID": "missing-route-request"},
    )

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "missing-route-request"
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "not_found",
            "message": "Not Found",
        },
    }


def test_unhandled_errors_return_contract_safe_json_with_request_id() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom", headers={"X-Request-ID": "boom-request"})

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "boom-request"
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "internal_server_error",
            "message": "Internal server error.",
        },
    }


def test_json_formatter_includes_structured_context() -> None:
    record = logging.LogRecord(
        name="sonic.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "formatter-request"
    record.path = "/health"
    record.method = "GET"
    record.status_code = 200

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "sonic.test"
    assert payload["message"] == "request complete"
    assert payload["request_id"] == "formatter-request"
    assert payload["path"] == "/health"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["timestamp"].endswith("Z")
