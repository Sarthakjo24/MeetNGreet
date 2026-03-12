from __future__ import annotations

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import settings

_TELEMETRY_CONFIGURED = False


def _parse_headers(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    headers: dict[str, str] = {}
    for chunk in raw.split(","):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def _telemetry_enabled() -> bool:
    enabled = os.getenv("OTEL_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    has_endpoint = bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())
    return enabled or has_endpoint


def configure_telemetry(app: Optional[object] = None) -> None:
    global _TELEMETRY_CONFIGURED
    if not _telemetry_enabled():
        return

    if not _TELEMETRY_CONFIGURED:
        resource = Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": settings.app_version,
                "deployment.environment": settings.app_env,
            }
        )
        provider = TracerProvider(resource=resource)
        endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4318/v1/traces",
        )
        headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        HTTPXClientInstrumentor().instrument()
        LoggingInstrumentor().instrument(set_logging_format=False)
        _TELEMETRY_CONFIGURED = True

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
