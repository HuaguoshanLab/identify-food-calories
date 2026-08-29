"""Allowlist-only OpenTelemetry runtime for a remote Phoenix collector.

Phoenix is a collector and analysis surface, not permission to export arbitrary
application state.  This module never launches its local UI and exposes a
small span API so meal text, user identity, prompts, responses, secrets, and
chain-of-thought have no route into telemetry.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, nullcontext
from typing import Any, Protocol

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanProcessor, SimpleSpanProcessor

from app.core.config import ConfigurationError, Settings


ALLOWED_ATTRIBUTE_KEYS = frozenset(
    {
        "app.version",
        "graph.version",
        "prompt.version",
        "tool.version",
        "node.name",
        "tool.name",
        "provider.model",
        "status.code",
        "error.code",
        "count.model_calls",
        "count.tool_calls",
        "token.input",
        "token.output",
        "cost.usd",
        "latency.ms",
        "thread.fingerprint",
    }
)


class TracingRuntime(Protocol):
    """The only telemetry surface available to runtime wiring."""

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, object]) -> Iterator[None]: ...

    def scoped_hmac(self, value: str) -> str: ...

    def flush(self) -> None: ...

    def shutdown(self) -> None: ...


class DisabledTracingRuntime:
    """Do nothing when tracing is disabled; no exporter or global provider is created."""

    @contextmanager
    def span(self, _name: str, _attributes: Mapping[str, object]) -> Iterator[None]:
        with nullcontext():
            yield

    def scoped_hmac(self, _value: str) -> str:
        return "disabled"

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class AllowlistTracingRuntime:
    """Own a private provider so application instrumentation cannot mutate global state."""

    def __init__(
        self,
        *,
        settings: Settings,
        exporter: SpanExporter | None = None,
    ) -> None:
        collector = _required(settings.tracing_collector_endpoint, "TRACING_COLLECTOR_ENDPOINT")
        service_name = _required(settings.tracing_service_name, "TRACING_SERVICE_NAME")
        service_version = _required(settings.tracing_service_version, "TRACING_SERVICE_VERSION")
        if settings.tracing_hmac_key is None:
            raise ConfigurationError("TRACING_HMAC_KEY is required when tracing is enabled")
        hmac_key = settings.tracing_hmac_key.get_secret_value()
        if not hmac_key:
            raise ConfigurationError("TRACING_HMAC_KEY is required when tracing is enabled")

        resource = Resource.create({SERVICE_NAME: service_name, SERVICE_VERSION: service_version})
        self._provider = TracerProvider(resource=resource)
        self._processor: SpanProcessor = SimpleSpanProcessor(
            exporter or OTLPSpanExporter(endpoint=collector)
        )
        self._provider.add_span_processor(self._processor)
        self._tracer = self._provider.get_tracer("food-agent.runtime")
        self._hmac_key = hmac_key.encode("utf-8")

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, object]) -> Iterator[None]:
        with self._tracer.start_as_current_span(name) as active_span:
            for key, value in _allowlisted_attributes(attributes).items():
                active_span.set_attribute(key, value)
            yield

    def scoped_hmac(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def flush(self) -> None:
        self._provider.force_flush()

    def shutdown(self) -> None:
        self._provider.shutdown()


def create_tracing_runtime(
    settings: Settings, *, exporter: SpanExporter | None = None
) -> TracingRuntime:
    """Create a remote-only runtime; disabled tracing has no exporter side effect."""

    if not settings.tracing_enabled:
        return DisabledTracingRuntime()
    return AllowlistTracingRuntime(settings=settings, exporter=exporter)


def _required(value: str | None, variable: str) -> str:
    if not value or not value.strip():
        raise ConfigurationError(f"{variable} is required when tracing is enabled")
    return value


def _allowlisted_attributes(attributes: Mapping[str, object]) -> dict[str, Any]:
    """Reject undeclared and unsafe values before a span can observe them."""

    accepted: dict[str, Any] = {}
    for key, value in attributes.items():
        if key not in ALLOWED_ATTRIBUTE_KEYS:
            continue
        if isinstance(value, bool | int | float):
            accepted[key] = value
        elif isinstance(value, str) and value and len(value) <= 128:
            accepted[key] = value
    return accepted
