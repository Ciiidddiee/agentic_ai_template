from __future__ import annotations

from typing import Any

_provider_configured = False


class _NoopSpan:
    def set(self, **attributes: Any) -> None:
        return None

    def end(self, **attributes: Any) -> None:
        return None


class _OtelSpan:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set(self, **attributes: Any) -> None:
        for key, value in attributes.items():
            if value is not None:
                self._span.set_attribute(key, value)

    def end(self, **attributes: Any) -> None:
        self.set(**attributes)
        self._span.end()


class Tracer:
    """OpenTelemetry spans when enabled and the `otel` extra is installed; otherwise no-ops."""

    def __init__(
        self, enabled: bool = False, service_name: str = "aikit", endpoint: str | None = None
    ) -> None:
        self._tracer: Any = None
        if enabled:
            self._tracer = self._setup(service_name, endpoint)

    @property
    def enabled(self) -> bool:
        return self._tracer is not None

    @staticmethod
    def _setup(service_name: str, endpoint: str | None) -> Any:
        global _provider_configured
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
                SpanExporter,
            )
        except ImportError:
            return None
        if not _provider_configured:
            exporter: SpanExporter
            if endpoint:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
            else:
                exporter = ConsoleSpanExporter()
            provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            _provider_configured = True
        return trace.get_tracer("aikit")

    def start(self, name: str, **attributes: Any) -> _NoopSpan | _OtelSpan:
        if self._tracer is None:
            return _NoopSpan()
        span = _OtelSpan(self._tracer.start_span(name))
        span.set(**attributes)
        return span
