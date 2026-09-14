"""Allowlist-only OpenTelemetry runtime for a remote Phoenix collector.

Phoenix is a collector and analysis surface, not permission to export arbitrary
application state.  This module never launches its local UI and exposes a
small span API so meal text, user identity, prompts, responses, secrets, and
chain-of-thought have no route into telemetry.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, nullcontext
from typing import Any, Protocol, cast

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
        "retrieval.version",
        "match.channel",
        "fallback.code",
        "latency.bucket",
        "index.health",
        "index.version",
    }
)


class TracingRuntime(Protocol):
    """The only telemetry surface available to runtime wiring."""

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, object]) -> Iterator[TracingSpan]: ...

    def scoped_hmac(self, value: str) -> str: ...

    def flush(self) -> None: ...

    def shutdown(self) -> None: ...


class LangfuseClient(Protocol):
    def start_as_current_observation(self, **payload: object) -> Any: ...

    def flush(self) -> None: ...

    def shutdown(self) -> None: ...


class TracingSpan(Protocol):
    """Narrow mutation surface for structured, sanitized observation payloads."""

    def update(
        self,
        *,
        input: object | None = None,
        output: object | None = None,
        usage_details: Mapping[str, int] | None = None,
        cost_details: Mapping[str, float] | None = None,
    ) -> None: ...


class _NoopTracingSpan:
    def update(
        self,
        *,
        input: object | None = None,
        output: object | None = None,
        usage_details: Mapping[str, int] | None = None,
        cost_details: Mapping[str, float] | None = None,
    ) -> None:
        return None


class _LangfuseTracingSpan:
    def __init__(self, observation: Any) -> None:
        self._observation = observation

    def update(
        self,
        *,
        input: object | None = None,
        output: object | None = None,
        usage_details: Mapping[str, int] | None = None,
        cost_details: Mapping[str, float] | None = None,
    ) -> None:
        payload: dict[str, object] = {}
        if input is not None:
            payload["input"] = _sanitize_trace_payload(input)
        if output is not None:
            payload["output"] = _sanitize_trace_payload(output)
        if usage_details is not None:
            payload["usage_details"] = dict(usage_details)
        if cost_details is not None:
            payload["cost_details"] = dict(cost_details)
        if payload:
            self._observation.update(**payload)


class DisabledTracingRuntime:
    """Do nothing when tracing is disabled; no exporter or global provider is created."""

    @contextmanager
    def span(self, _name: str, _attributes: Mapping[str, object]) -> Iterator[TracingSpan]:
        with nullcontext():
            yield _NoopTracingSpan()

    def scoped_hmac(self, _value: str) -> str:
        return "disabled"

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class TracedNutritionToolAdapter:
    """Add fixed, payload-free spans around the graph's deterministic tool port.

    Core tracing deliberately stays independent from nutrition schemas.  The graph already
    receives the narrow tool adapter port, so this structural wrapper can instrument its three
    methods without observing food names, grams, catalog identifiers, or returned nutrients.
    """

    def __init__(self, *, delegate: object, tracing: TracingRuntime) -> None:
        self._delegate = delegate
        self._tracing = tracing

    async def search_food_catalog(self, request: object) -> Any:
        return await self._acall("nutrition.search_food_catalog", "search_food_catalog", request)

    def calculate_nutrition(self, request: object) -> Any:
        return self._call("nutrition.calculate_nutrition", "calculate_nutrition", request)

    def validate_nutrition_result(self, request: object) -> Any:
        return self._call("nutrition.validate_nutrition_result", "validate_nutrition_result", request)

    def _call(self, span_name: str, method_name: str, request: object) -> Any:
        method = getattr(self._delegate, method_name)
        with self._tracing.span(
            span_name,
            {"tool.name": method_name, "tool.version": "nutrition-tools-v1"},
        ):
            return method(request)

    async def _acall(self, span_name: str, method_name: str, request: object) -> Any:
        method = getattr(self._delegate, method_name)
        with self._tracing.span(
            span_name,
            {"tool.name": method_name, "tool.version": "nutrition-tools-v1"},
        ):
            return await method(request)


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
    def span(self, name: str, attributes: Mapping[str, object]) -> Iterator[TracingSpan]:
        with self._tracer.start_as_current_span(name) as active_span:
            for key, value in _allowlisted_attributes(attributes).items():
                active_span.set_attribute(key, value)
            yield _NoopTracingSpan()

    def scoped_hmac(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def flush(self) -> None:
        self._provider.force_flush()

    def shutdown(self) -> None:
        self._provider.shutdown()


class LangfuseTracingRuntime:
    """Send the same payload-free spans to one development Langfuse project."""

    def __init__(
        self,
        *,
        settings: Settings,
        client: LangfuseClient | None = None,
    ) -> None:
        service_name = _required(settings.tracing_service_name, "TRACING_SERVICE_NAME")
        service_version = _required(settings.tracing_service_version, "TRACING_SERVICE_VERSION")
        if settings.tracing_hmac_key is None:
            raise ConfigurationError("TRACING_HMAC_KEY is required when tracing is enabled")
        hmac_key = settings.tracing_hmac_key.get_secret_value()
        if not hmac_key:
            raise ConfigurationError("TRACING_HMAC_KEY is required when tracing is enabled")
        if client is None:
            if (
                not settings.langfuse_public_key
                or settings.langfuse_secret_key is None
                or not settings.langfuse_base_url
            ):
                raise ConfigurationError("Langfuse tracing credentials are incomplete")
            try:
                from langfuse import Langfuse
            except ImportError as error:
                raise ConfigurationError(
                    "Langfuse tracing requires the backend dev dependency group"
                ) from error
            self._provider: TracerProvider | None = TracerProvider(
                resource=Resource.create(
                    {SERVICE_NAME: service_name, SERVICE_VERSION: service_version}
                )
            )
            client = cast(
                LangfuseClient,
                Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key.get_secret_value(),
                    base_url=settings.langfuse_base_url,
                    environment=settings.langfuse_environment,
                    release=service_version,
                    tracer_provider=self._provider,
                ),
            )
        else:
            self._provider = None
        self._client = cast(LangfuseClient, client)
        self._hmac_key = hmac_key.encode("utf-8")
        self._resource_metadata = {
            "service.name": service_name,
            "service.version": service_version,
        }

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, object]) -> Iterator[TracingSpan]:
        metadata = {**self._resource_metadata, **_allowlisted_attributes(attributes)}
        observation_type = "generation" if name == "agent.provider" else "span"
        model = metadata.get("provider.model") if observation_type == "generation" else None
        with self._client.start_as_current_observation(
            name=name,
            as_type=observation_type,
            metadata=metadata,
            **({"model": model} if isinstance(model, str) else {}),
        ) as observation:
            yield _LangfuseTracingSpan(observation)

    def scoped_hmac(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def flush(self) -> None:
        self._client.flush()

    def shutdown(self) -> None:
        self._client.shutdown()


def create_tracing_runtime(
    settings: Settings,
    *,
    exporter: SpanExporter | None = None,
    langfuse_client: LangfuseClient | None = None,
) -> TracingRuntime:
    """Create a remote-only runtime; disabled tracing has no exporter side effect."""

    if not settings.tracing_enabled:
        return DisabledTracingRuntime()
    if settings.tracing_backend == "langfuse":
        return LangfuseTracingRuntime(settings=settings, client=langfuse_client)
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


_SENSITIVE_KEY = re.compile(
    r"(?:password|secret|authorization|api[_-]?key|chain[_-]?of[_-]?thought|reasoning_content)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)


def _sanitize_trace_payload(value: object, *, depth: int = 0) -> object:
    """Bound Langfuse payloads and remove credentials and common direct identifiers."""

    if depth >= 5:
        return "[truncated]"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if value.startswith("data:image/") or (len(value) > 4096 and "base64" in value[:64].lower()):
            return "[image omitted]"
        redacted = _BEARER.sub("Bearer [redacted]", value)
        redacted = _EMAIL.sub("[email redacted]", redacted)
        redacted = _PHONE.sub("[phone redacted]", redacted)
        return redacted[:2000] + ("…" if len(redacted) > 2000 else "")
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 30:
                sanitized["[truncated]"] = "too many fields"
                break
            safe_key = str(key)[:128]
            sanitized[safe_key] = (
                "[redacted]"
                if _SENSITIVE_KEY.search(safe_key)
                else _sanitize_trace_payload(item, depth=depth + 1)
            )
        return sanitized
    if isinstance(value, (list, tuple)):
        items = [_sanitize_trace_payload(item, depth=depth + 1) for item in value[:20]]
        if len(value) > 20:
            items.append("[truncated]")
        return items
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _sanitize_trace_payload(model_dump(mode="json"), depth=depth + 1)
    return _sanitize_trace_payload(str(value), depth=depth + 1)
