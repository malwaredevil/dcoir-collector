"""Shared state primitives for stable DCOIR Review run telemetry."""

from __future__ import annotations

import threading
from typing import Any

SINK_ATTR = "_dcoir_run_telemetry_sink"
SUMMARY_ATTR = "_dcoir_run_telemetry_summary"
ERROR_COUNT_ATTR = "_dcoir_telemetry_error_count"
STAGE_LABEL_ATTR = "_dcoir_stage_label"
LEGACY_SINK_ATTR = "_dcoir_v54_run_telemetry_sink"
LEGACY_SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"
LEGACY_ERROR_COUNT_ATTR = "_dcoir_v54_telemetry_error_count"
LEGACY_STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"
SCHEMA_VERSION = "dcoir_openrouter_run_telemetry_v1"

class RunTelemetrySink:
    """Shared, thread-safe request/call evidence for one loaded review config."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._error_count = 0

    def add_call(self, call: dict[str, Any], events: list[dict[str, Any]]) -> None:
        with self._lock:
            self._calls.append(dict(call))
            self._events.extend(dict(item) for item in events)

    def add_errors(self, count: int = 1) -> None:
        try:
            parsed = int(count)
        except (TypeError, ValueError):
            parsed = 1
        if parsed <= 0:
            return
        with self._lock:
            self._error_count += parsed

    def error_count(self) -> int:
        with self._lock:
            return max(0, int(self._error_count))

    def snapshot(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        with self._lock:
            return (
                [dict(item) for item in self._calls],
                [dict(item) for item in self._events],
            )




def ensure_sink(config: Any) -> RunTelemetrySink:
    sink = getattr(config, SINK_ATTR, None)
    if not isinstance(sink, RunTelemetrySink):
        sink = getattr(config, LEGACY_SINK_ATTR, None)
    if isinstance(sink, RunTelemetrySink):
        setattr(config, SINK_ATTR, sink)
        return sink
    sink = RunTelemetrySink()
    setattr(config, SINK_ATTR, sink)
    setattr(config, LEGACY_SINK_ATTR, sink)
    return sink


def telemetry_error_count(config: Any) -> int:
    try:
        sink = getattr(config, SINK_ATTR, None)
        if not isinstance(sink, RunTelemetrySink):
            sink = getattr(config, LEGACY_SINK_ATTR, None)
    except Exception:
        sink = None
    if isinstance(sink, RunTelemetrySink):
        try:
            return sink.error_count()
        except Exception:
            return 0
    try:
        value = int(getattr(config, ERROR_COUNT_ATTR, getattr(config, LEGACY_ERROR_COUNT_ATTR, 0)) or 0)
    except Exception:
        return 0
    return max(0, value)


def note_telemetry_error(config: Any) -> None:
    """Best-effort shared error accounting that must never affect review behavior."""
    try:
        sink = getattr(config, SINK_ATTR, None)
        if not isinstance(sink, RunTelemetrySink):
            sink = getattr(config, LEGACY_SINK_ATTR, None)
    except Exception:
        sink = None
    if isinstance(sink, RunTelemetrySink):
        try:
            sink.add_errors(1)
            return
        except Exception:
            return
    try:
        next_count = telemetry_error_count(config) + 1
        setattr(config, ERROR_COUNT_ATTR, next_count)
        setattr(config, LEGACY_ERROR_COUNT_ATTR, next_count)
    except Exception:
        # Error accounting is advisory; never let it alter review behavior.
        return
