"""Public HTTP contracts and privacy boundaries for operational logging."""

import asyncio
import io
import json
import logging
import uuid

import httpx
import pytest
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import (
    BestEffortHandler,
    SafeFormatter,
    configure_logging,
    execution_id,
    observed,
    request_id,
    current_request_id,
)
from app.main import create_app


@pytest.fixture
def app_and_logs():
    app = create_app(Settings(_env_file=None))
    output = io.StringIO()
    handler = logging.getLogger().handlers[0]
    handler.setStream(output)
    handler.setFormatter(SafeFormatter("json"))

    @app.get("/logging/fail")
    def fail():
        raise RuntimeError("SECRET-EXCEPTION")

    @app.get("/logging/check/{resource}")
    async def check(resource: str):
        initial = current_request_id()
        threaded = await asyncio.to_thread(current_request_id)
        await asyncio.sleep(0)
        return {"initial": initial, "threaded": threaded}

    @app.get("/logging/business")
    def business():
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "CONFLICT", "request_id": current_request_id()}},
        )

    @app.get("/logging/stream")
    async def stream():
        async def events():
            yield b"data: first\n\n"
            await asyncio.sleep(0)
            yield b"data: second\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    yield app, output


def test_formatter_privacy_and_failed_output():
    record = logging.LogRecord("sdk", logging.ERROR, "", 1, "SECRET-BODY", (), None)
    assert "SECRET" not in SafeFormatter().format(record)
    try:
        raise ValueError("SECRET-EXCEPTION")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    payload = json.loads(SafeFormatter("json").format(record))
    assert payload["error_type"] == "ValueError"
    assert "SECRET" not in json.dumps(payload)

    class Broken:
        def write(self, value):
            raise OSError("SECRET-OUTPUT")

        def flush(self):
            pass

    handler = BestEffortHandler(Broken())
    handler.setFormatter(SafeFormatter())
    handler.emit(record)


def test_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="INVALID")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_format="INVALID")
    configure_logging("ERROR", "json")
    configure_logging("ERROR", "json")
    assert len(logging.getLogger().handlers) == 1
    assert not logging.getLogger("app.test").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    assert logging.getLogger("uvicorn.access").disabled


def test_http_contracts(app_and_logs):
    app, output = app_and_logs

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            for path, method, expected in [
                ("/api/v1/health", "GET", 200),
                ("/api/v1/auth/login", "POST", 422),
                ("/logging/business", "GET", 409),
                ("/logging/fail", "GET", 500),
            ]:
                response = await client.request(
                    method,
                    path,
                    headers={
                        "X-Request-ID": "SECRET-CLIENT",
                        "Origin": "http://localhost:5173",
                    },
                )
                assert response.status_code == expected
                identifier = response.headers["x-request-id"]
                uuid.UUID(identifier)
                assert (
                    "X-Request-ID" in response.headers["access-control-expose-headers"]
                )
                if "error" in response.json():
                    assert response.json()["error"]["request_id"] == identifier
            responses = await asyncio.gather(
                *(
                    client.get("/logging/check/SECRET-PATH?secret=SECRET-QUERY")
                    for _ in range(8)
                )
            )
            assert len({r.headers["x-request-id"] for r in responses}) == 8
            for response in responses:
                assert (
                    response.json()["initial"]
                    == response.json()["threaded"]
                    == response.headers["x-request-id"]
                )
            preflight = await client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert preflight.status_code == 200
            uuid.UUID(preflight.headers["x-request-id"])
            stream = await client.get("/logging/stream")
            assert stream.content == b"data: first\n\ndata: second\n\n"
            assert request_id.get() is None

    asyncio.run(scenario())
    assert "SECRET" not in output.getvalue()
    assert "http_failed" in output.getvalue()


def test_execution_scope(app_and_logs):
    _, output = app_and_logs
    logging.getLogger(__name__).setLevel(logging.INFO)

    @observed("agent", execution=True)
    async def agent():
        identifier = execution_id.get()
        assert await asyncio.to_thread(execution_id.get) == identifier
        from app.providers.reasoning.fake import FakeReasoningModelProvider
        from app.providers.reasoning.dto import (
            ParseMealRequest,
            ParsedMealDTO,
            ParsedMealItemDTO,
        )

        @observed("tool")
        async def tool():
            provider = FakeReasoningModelProvider()
            provider.queue_parse_result(
                ParsedMealDTO(
                    items=[ParsedMealItemDTO(item_id="item-1", food_name="SECRET-FOOD")]
                )
            )
            return await provider.parse_meal(
                ParseMealRequest(meal_description="SECRET-MEAL")
            )

        await tool()
        return identifier

    async def scenario():
        identifiers = await asyncio.gather(agent(), agent())
        assert identifiers[0] != identifiers[1]
        assert execution_id.get() is None

    asyncio.run(scenario())
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert all(record["execution_id"] for record in records)
    assert {"agent_start", "tool_start", "provider_start"} <= {
        record["event"] for record in records
    }
    assert "SECRET" not in output.getvalue()


def test_stream_forwarding_and_disconnect(app_and_logs):
    from app.core.logging import RequestLoggingMiddleware

    async def scenario():
        first_forwarded = asyncio.Event()
        messages = []

        async def application(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {"type": "http.response.body", "body": b"first", "more_body": True}
            )
            assert first_forwarded.is_set()
            assert (await receive())["type"] == "http.disconnect"

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)
            if message.get("body") == b"first":
                first_forwarded.set()

        await RequestLoggingMiddleware(application)(
            {"type": "http", "method": "GET", "state": {}}, receive, send
        )
        assert request_id.get() is None
        assert messages[1]["body"] == b"first"

        async def cancelled(scope, receive, send):
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await RequestLoggingMiddleware(cancelled)(
                {"type": "http", "method": "GET", "state": {}}, receive, send
            )
        assert request_id.get() is None

    asyncio.run(scenario())
