"""Request-event normalization and draining for DCOIR Review telemetry."""

from __future__ import annotations

import math
from typing import Any

from dcoir_review.review_telemetry_state import RunTelemetrySink

def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        return None
    if isinstance(value, int):
        return int(value)
    return parsed


def _nested_number(mapping: Any, *path: str) -> int | float | None:
    current = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _finite_number(current)


def _usage_metric(usage: dict[str, Any], name: str) -> int | float | None:
    direct = _nested_number(usage, name)
    if direct is not None:
        return direct
    if name == "reasoning_tokens":
        return _nested_number(usage, "completion_tokens_details", "reasoning_tokens")
    if name == "cached_tokens":
        return _nested_number(usage, "prompt_tokens_details", "cached_tokens")
    if name == "cache_write_tokens":
        for path in (
            ("prompt_tokens_details", "cache_write_tokens"),
            ("prompt_tokens_details", "cache_creation_tokens"),
        ):
            value = _nested_number(usage, *path)
            if value is not None:
                return value
    return None

def normalize_event(raw: Any, stage: str, attempt_outcome: str = "attempt_outcome_missing") -> dict[str, Any]:
    """Whitelist returned execution metadata; never copy arbitrary response data."""
    item = raw if isinstance(raw, dict) else {}
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
    cost = _finite_number(item.get("cost"))
    if cost is None:
        cost = _usage_metric(usage, "cost")
    return {
        "stage": stage,
        "attempt_outcome": attempt_outcome,
        "requested_model": str(item.get("requested_model", "") or "")[:160],
        "served_model": str(item.get("served_model", "") or "")[:160],
        "served_model_differs_from_requested": bool(
            item.get("served_model_differs_from_requested", False)
        ),
        "provider": str(item.get("provider", "") or "")[:120],
        "service_tier": str(item.get("service_tier", "") or "")[:80],
        "finish_reason": str(item.get("finish_reason", "") or "")[:80],
        "prompt_tokens": _usage_metric(usage, "prompt_tokens"),
        "completion_tokens": _usage_metric(usage, "completion_tokens"),
        "total_tokens": _usage_metric(usage, "total_tokens"),
        "reasoning_tokens": _usage_metric(usage, "reasoning_tokens"),
        "cached_tokens": _usage_metric(usage, "cached_tokens"),
        "cache_write_tokens": _usage_metric(usage, "cache_write_tokens"),
        "cost": cost,
        "request_attempt_count": _finite_number(item.get("request_attempt_count")),
        "response_healing_observed": bool(item.get("response_healing_observed", False)),
        "structured_output_recovery": str(
            item.get("structured_output_recovery", "") or ""
        )[:80],
    }


def normalize_attempt(raw: Any) -> dict[str, Any]:
    item = raw if isinstance(raw, dict) else {}
    try:
        attempt = int(item.get("request_attempt_count", 0) or 0)
    except (TypeError, ValueError):
        attempt = 0
    outcome = str(item.get("outcome", "") or "").strip()
    if outcome not in {"success", "retry", "fallback", "terminal_failure"}:
        outcome = "unclassified"
    normalized = {
        "attempt": max(0, attempt),
        "outcome": outcome,
        "requested_model": str(item.get("requested_model", "") or "")[:160],
        "provider": str(item.get("provider", "") or "")[:120],
        "failure_class": str(item.get("failure_class", "") or "")[:80],
    }
    for key in ("model_index", "model_count", "attempt_in_model", "attempt_limit"):
        try:
            normalized[key] = max(0, int(item.get(key, 0) or 0))
        except (TypeError, ValueError):
            normalized[key] = 0
    http_status = item.get("http_status")
    if isinstance(http_status, int) and not isinstance(http_status, bool):
        normalized["http_status"] = http_status
    return normalized


def _drain_call(config: Any, sink: RunTelemetrySink, stage: str, outcome: str) -> None:
    history = getattr(config, "_openrouter_request_telemetry_events", None)
    raw_events = history if isinstance(history, list) else []
    events = [normalize_event(item, stage) for item in raw_events]
    attempt_history = getattr(config, "_openrouter_request_attempt_telemetry_events", None)
    raw_attempts = attempt_history if isinstance(attempt_history, list) else []
    detailed_attempts = [normalize_attempt(item) for item in raw_attempts]
    try:
        provider_errors = int(getattr(config, "_openrouter_request_telemetry_error_count", 0) or 0)
    except (TypeError, ValueError):
        provider_errors = 0
    if provider_errors > 0:
        sink.add_errors(provider_errors)
    try:
        attempts = int(getattr(config, "_openrouter_request_attempt_count", 0) or 0)
    except (TypeError, ValueError):
        attempts = 0
    attempts = max(0, attempts)

    response_map: dict[int, dict[str, Any]] = {}
    for event in events:
        raw_attempt = _finite_number(event.get("request_attempt_count"))
        if isinstance(raw_attempt, int) and 1 <= raw_attempt <= attempts:
            response_map.setdefault(raw_attempt, event)

    detailed_map: dict[int, dict[str, Any]] = {}
    for attempt in detailed_attempts:
        attempt_number = attempt.get("attempt")
        if isinstance(attempt_number, int) and 1 <= attempt_number <= attempts:
            detailed_map[attempt_number] = attempt

    attempt_records: list[dict[str, Any]] = []
    for attempt_number in range(1, attempts + 1):
        response = response_map.get(attempt_number)
        detailed = detailed_map.get(attempt_number)
        if isinstance(detailed, dict):
            record = dict(detailed)
        else:
            record = {
                "attempt": attempt_number,
                "outcome": "attempt_outcome_missing",
                "requested_model": "",
                "provider": "",
                "failure_class": "",
                "model_index": 0,
                "model_count": 0,
                "attempt_in_model": 0,
                "attempt_limit": 0,
            }
        if isinstance(response, dict):
            response["attempt_outcome"] = str(record.get("outcome", "attempt_outcome_missing"))
            for key in ("requested_model", "served_model", "provider", "service_tier", "finish_reason"):
                value = str(response.get(key, "") or "")
                if value:
                    record[key] = value
        attempt_records.append(record)

    for event in events:
        raw_attempt = _finite_number(event.get("request_attempt_count"))
        if not isinstance(raw_attempt, int) or raw_attempt not in response_map:
            event["attempt_outcome"] = "attempt_outcome_missing"

    observed_attempts = len(response_map)
    sink.add_call(
        {
            "stage": stage,
            "outcome": outcome,
            "request_attempts": attempts,
            "response_events": observed_attempts,
            "attempts_without_response_telemetry": max(0, attempts - observed_attempts),
            "attempt_records": attempt_records,
        },
        events,
    )
