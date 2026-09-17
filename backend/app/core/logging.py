"""Allowlisted, best-effort operational logs; never an audit store."""

from __future__ import annotations

import functools
import inspect
import json
import logging
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
execution_id: ContextVar[str | None] = ContextVar("execution_id", default=None)
FIELDS = frozenset(
    {
        "event",
        "method",
        "route",
        "status",
        "elapsed_ms",
        "tool",
        "error_type",
        "stack",
        "metrics",
        "policy",
        "action",
        "reason",
        "model",
        "tokens",
        "cost",
        "provider_request_id",
        "image_digest",
    }
)


def current_request_id() -> str:
    return request_id.get() or str(uuid.uuid4())


class SafeFormatter(logging.Formatter):
    def __init__(self, format_name: str = "text") -> None:
        super().__init__()
        self.format_name = format_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "version": "operational-log.v1",
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "request_id": request_id.get(),
            "execution_id": execution_id.get(),
        }
        # Unstructured messages and exception strings are untrusted, including SDK logs.
        payload["event"] = "unstructured_log"
        payload.update(
            {key: record.__dict__[key] for key in FIELDS if key in record.__dict__}
        )
        if record.exc_info and record.exc_info[0]:
            payload["error_type"] = record.exc_info[0].__name__
            payload["stack"] = [
                {
                    "file": frame.filename.rsplit("/", 1)[-1],
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        if self.format_name == "json":
            return json.dumps(payload, ensure_ascii=False)
        return " ".join(
            f"{key}={json.dumps(value, ensure_ascii=False)}"
            for key, value in payload.items()
        )


class BestEffortHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:
            pass

    def handleError(self, record: logging.LogRecord) -> None:
        # logging's default handler prints the raw record on output failure.
        pass


def configure_logging(level: str = "INFO", format_name: str = "text") -> None:
    handler = BestEffortHandler(sys.stdout)
    handler.setFormatter(SafeFormatter(format_name))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(level)
    planning = logging.getLogger("app.planning.diagnostics")
    planning.handlers.clear()
    planning.setLevel(logging.NOTSET)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True


def observed(
    event: str, *, execution: bool = False
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Scope execution identities without modifying persisted graph state."""

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        logger = logging.getLogger(function.__module__)

        def begin():
            token = execution_id.set(str(uuid.uuid4())) if execution else None
            logger.info(
                "", extra={"event": event + "_start", "tool": function.__name__}
            )
            return token, time.perf_counter()

        def finish(token, started, failed):
            logger.log(
                logging.ERROR if failed else logging.INFO,
                "",
                extra={
                    "event": event + ("_failed" if failed else "_complete"),
                    "tool": function.__name__,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                },
            )
            if token is not None:
                execution_id.reset(token)

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def asynchronous(*args, **kwargs):
                token, started = begin()
                failed = True
                try:
                    result = await function(*args, **kwargs)
                    failed = False
                    return result
                finally:
                    finish(token, started, failed)

            return asynchronous

        @functools.wraps(function)
        def synchronous(*args, **kwargs):
            token, started = begin()
            failed = True
            try:
                result = function(*args, **kwargs)
                failed = False
                return result
            finally:
                finish(token, started, failed)

        return synchronous

    return decorate


class RequestLoggingMiddleware:
    def __init__(self, app, cors_origins: list[str] | None = None) -> None:
        self.app = app
        self.cors_origins = cors_origins or []

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identifier = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = identifier
        token = request_id.set(identifier)
        started = time.perf_counter()
        status = 500
        response_started = False
        logger = logging.getLogger(__name__)

        async def forward(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                message = dict(message)
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", identifier.encode())]
            await send(message)

        try:
            await self.app(scope, receive, forward)
        except Exception:
            logger.error("", extra={"event": "http_failed"}, exc_info=True)
            if response_started:
                # A stream already sent its headers: never append a second response.
                raise
            from starlette.responses import JSONResponse

            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "服务暂时不可用，请稍后重试。",
                        "request_id": identifier,
                    }
                },
            )
            from starlette.middleware.cors import CORSMiddleware

            await CORSMiddleware(
                response,
                allow_origins=self.cors_origins,
                allow_credentials=True,
                expose_headers=["X-Request-ID"],
            )(scope, receive, forward)
        finally:
            route = scope.get("route")
            logger.info(
                "",
                extra={
                    "event": "http_complete",
                    "method": scope["method"]
                    if scope["method"]
                    in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
                    else "OTHER",
                    "route": getattr(route, "path", "unmatched"),
                    "status": status,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                },
            )
            request_id.reset(token)
