"""Aggregation and bounded rendering for DCOIR Review telemetry."""

from __future__ import annotations

from collections import Counter
from typing import Any

from dcoir_review.review_telemetry_events import _finite_number
from dcoir_review.review_telemetry_state import (
    SCHEMA_VERSION,
    ensure_sink,
    telemetry_error_count,
)

def _sum_metric(events: list[dict[str, Any]], key: str) -> dict[str, Any]:
    observed = [item.get(key) for item in events if _finite_number(item.get(key)) is not None]
    total = sum(float(value) for value in observed) if observed else None
    if total is not None and key != "cost" and all(float(value).is_integer() for value in observed):
        total = int(total)
    return {
        "observed_total": total,
        "observed_events": len(observed),
        "missing_events": len(events) - len(observed),
    }


def _category_counts(events: list[dict[str, Any]], key: str) -> Counter[str]:
    return Counter(str(item.get(key, "") or "").strip() or "unknown" for item in events)


def _category_coverage(events: list[dict[str, Any]], key: str) -> dict[str, int]:
    observed = sum(1 for item in events if str(item.get(key, "") or "").strip())
    return {"observed_events": observed, "missing_events": len(events) - observed}


def summarize_sink(config: Any) -> dict[str, Any]:
    sink = ensure_sink(config)
    calls, events = sink.snapshot()
    stage_calls = Counter(str(item.get("stage", "unclassified")) for item in calls)
    stage_attempts: Counter[str] = Counter()
    stage_responses: Counter[str] = Counter()
    stage_missing: Counter[str] = Counter()
    stage_attempt_outcomes: dict[str, Counter[str]] = {}
    stage_attempt_models: dict[str, Counter[str]] = {}
    stage_attempt_failure_classes: dict[str, Counter[str]] = {}
    stage_attempt_http_statuses: dict[str, Counter[str]] = {}
    attempt_requested_models: Counter[str] = Counter()
    attempt_failure_classes: Counter[str] = Counter()
    attempt_http_statuses: Counter[str] = Counter()
    stage_events: dict[str, list[dict[str, Any]]] = {}
    for item in calls:
        stage = str(item.get("stage", "unclassified"))
        stage_attempts[stage] += int(item.get("request_attempts", 0) or 0)
        stage_responses[stage] += int(item.get("response_events", 0) or 0)
        stage_missing[stage] += int(item.get("attempts_without_response_telemetry", 0) or 0)
        attempts = item.get("attempt_records")
        counter = stage_attempt_outcomes.setdefault(stage, Counter())
        if isinstance(attempts, list):
            model_counter = stage_attempt_models.setdefault(stage, Counter())
            failure_counter = stage_attempt_failure_classes.setdefault(stage, Counter())
            status_counter = stage_attempt_http_statuses.setdefault(stage, Counter())
            for attempt in attempts:
                if isinstance(attempt, dict):
                    counter[str(attempt.get("outcome", "unclassified"))] += 1
                    requested_model = str(attempt.get("requested_model", "") or "").strip() or "unknown"
                    model_counter[requested_model] += 1
                    attempt_requested_models[requested_model] += 1
                    failure_class = str(attempt.get("failure_class", "") or "").strip()
                    if failure_class:
                        failure_counter[failure_class] += 1
                        attempt_failure_classes[failure_class] += 1
                    http_status = attempt.get("http_status")
                    if isinstance(http_status, int) and not isinstance(http_status, bool):
                        status = str(http_status)
                        status_counter[status] += 1
                        attempt_http_statuses[status] += 1
    for event in events:
        stage = str(event.get("stage", "unclassified"))
        stage_events.setdefault(stage, []).append(event)
    providers = _category_counts(events, "provider")
    service_tiers = _category_counts(events, "service_tier")
    requested_models = _category_counts(events, "requested_model")
    served_models = _category_counts(events, "served_model")
    finish_reasons = _category_counts(events, "finish_reason")
    recoveries = Counter(
        str(item.get("structured_output_recovery", ""))
        for item in events
        if str(item.get("structured_output_recovery", ""))
    )
    total_attempts = sum(int(item.get("request_attempts", 0) or 0) for item in calls)
    total_responses = sum(int(item.get("response_events", 0) or 0) for item in calls)
    return {
        "schema_version": SCHEMA_VERSION,
        "telemetry_status": "ok" if telemetry_error_count(config) == 0 else "partial",
        "telemetry_error_count": telemetry_error_count(config),
        "review_calls": len(calls),
        "request_attempts": total_attempts,
        "provider_response_events": total_responses,
        "attempts_without_response_telemetry": sum(
            int(item.get("attempts_without_response_telemetry", 0) or 0)
            for item in calls
        ),
        "failed_review_calls": sum(1 for item in calls if item.get("outcome") == "failed"),
        "stages": {
            stage: {
                "calls": stage_calls[stage],
                "request_attempts": stage_attempts[stage],
                "provider_response_events": stage_responses[stage],
                "attempts_without_response_telemetry": stage_missing[stage],
                "attempt_outcomes": dict(sorted(stage_attempt_outcomes.get(stage, Counter()).items())),
                "attempt_requested_models": dict(sorted(stage_attempt_models.get(stage, Counter()).items())),
                "attempt_failure_classes": dict(sorted(stage_attempt_failure_classes.get(stage, Counter()).items())),
                "attempt_http_statuses": dict(sorted(stage_attempt_http_statuses.get(stage, Counter()).items())),
                "metrics": {
                    key: _sum_metric(stage_events.get(stage, []), key)
                    for key in (
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                        "reasoning_tokens",
                        "cached_tokens",
                        "cache_write_tokens",
                        "cost",
                    )
                },
                "providers": dict(sorted(_category_counts(stage_events.get(stage, []), "provider").items())),
                "requested_models": dict(sorted(_category_counts(stage_events.get(stage, []), "requested_model").items())),
                "served_models": dict(sorted(_category_counts(stage_events.get(stage, []), "served_model").items())),
                "finish_reasons": dict(sorted(_category_counts(stage_events.get(stage, []), "finish_reason").items())),
                "service_tiers": dict(sorted(_category_counts(stage_events.get(stage, []), "service_tier").items())),
                "metadata_coverage": {
                    key: _category_coverage(stage_events.get(stage, []), key)
                    for key in ("provider", "service_tier", "requested_model", "served_model", "finish_reason")
                },
                "structured_output_recovery": dict(
                    sorted(
                        Counter(
                            str(item.get("structured_output_recovery", ""))
                            for item in stage_events.get(stage, [])
                            if str(item.get("structured_output_recovery", ""))
                        ).items()
                    )
                ),
            }
            for stage in sorted(stage_calls)
        },
        "metrics": {
            key: _sum_metric(events, key)
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "reasoning_tokens",
                "cached_tokens",
                "cache_write_tokens",
                "cost",
            )
        },
        "providers": dict(sorted(providers.items())),
        "service_tiers": dict(sorted(service_tiers.items())),
        "requested_models": dict(sorted(requested_models.items())),
        "served_models": dict(sorted(served_models.items())),
        "finish_reasons": dict(sorted(finish_reasons.items())),
        "attempt_requested_models": dict(sorted(attempt_requested_models.items())),
        "attempt_failure_classes": dict(sorted(attempt_failure_classes.items())),
        "attempt_http_statuses": dict(sorted(attempt_http_statuses.items())),
        "metadata_coverage": {
            key: _category_coverage(events, key)
            for key in ("provider", "service_tier", "requested_model", "served_model", "finish_reason")
        },
        "structured_output_recovery": dict(sorted(recoveries.items())),
        "response_healing_events": sum(
            1 for item in events if item.get("response_healing_observed") is True
        ),
        "served_model_mismatch_events": sum(
            1 for item in events if item.get("served_model_differs_from_requested") is True
        ),
    }


def compact_summary(summary: dict[str, Any], limit: int = 1800) -> str:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    stages = summary.get("stages") if isinstance(summary.get("stages"), dict) else {}
    providers = summary.get("providers") if isinstance(summary.get("providers"), dict) else {}
    service_tiers = summary.get("service_tiers") if isinstance(summary.get("service_tiers"), dict) else {}
    requested_models = (
        summary.get("requested_models") if isinstance(summary.get("requested_models"), dict) else {}
    )
    served_models = summary.get("served_models") if isinstance(summary.get("served_models"), dict) else {}
    finish_reasons = summary.get("finish_reasons") if isinstance(summary.get("finish_reasons"), dict) else {}
    attempt_requested_models = (
        summary.get("attempt_requested_models")
        if isinstance(summary.get("attempt_requested_models"), dict)
        else {}
    )
    attempt_failure_classes = (
        summary.get("attempt_failure_classes")
        if isinstance(summary.get("attempt_failure_classes"), dict)
        else {}
    )
    attempt_http_statuses = (
        summary.get("attempt_http_statuses")
        if isinstance(summary.get("attempt_http_statuses"), dict)
        else {}
    )
    metadata_coverage = (
        summary.get("metadata_coverage") if isinstance(summary.get("metadata_coverage"), dict) else {}
    )
    recoveries = (
        summary.get("structured_output_recovery")
        if isinstance(summary.get("structured_output_recovery"), dict)
        else {}
    )

    def metric(name: str) -> str:
        data = metrics.get(name) if isinstance(metrics.get(name), dict) else {}
        value = data.get("observed_total")
        observed = int(data.get("observed_events", 0) or 0)
        missing = int(data.get("missing_events", 0) or 0)
        shown = "unknown" if value is None else str(value)
        return f"{name}={shown} (observed={observed}, missing={missing})"

    def category(data: dict[str, Any]) -> str:
        return ",".join(f"{name}:{count}" for name, count in sorted(data.items())) or "unknown"

    stage_text = ",".join(
        f"{name}:{int(data.get('calls', 0) or 0)}/{int(data.get('request_attempts', 0) or 0)}"
        for name, data in sorted(stages.items())
        if isinstance(data, dict)
    ) or "none"
    provider_text = category(providers)
    service_tier_text = category(service_tiers)
    requested_model_text = category(requested_models)
    served_model_text = category(served_models)
    finish_reason_text = category(finish_reasons)
    recovery_text = category(recoveries)
    attempt_model_text = category(attempt_requested_models)
    failure_class_text = category(attempt_failure_classes)
    http_status_text = category(attempt_http_statuses)
    metadata_missing_text = ",".join(
        f"{name}:{int(data.get('missing_events', 0) or 0)}"
        for name, data in sorted(metadata_coverage.items())
        if isinstance(data, dict)
    ) or "none"
    attempt_outcome_text = (
        ",".join(
            f"{stage}:{'|'.join(f'{name}:{count}' for name, count in sorted(attempt_outcomes.items())) or 'none'}"
            for stage, data in sorted(stages.items())
            if isinstance(data, dict)
            for attempt_outcomes in [
                data.get("attempt_outcomes")
                if isinstance(data.get("attempt_outcomes"), dict)
                else {}
            ]
        )
        or "none"
    )
    text = "; ".join(
        [
            f"schema={SCHEMA_VERSION}",
            f"telemetry_status={str(summary.get('telemetry_status', 'ok') or 'ok')}",
            f"telemetry_error_count={int(summary.get('telemetry_error_count', 0) or 0)}",
            f"calls={int(summary.get('review_calls', 0) or 0)}",
            f"attempts={int(summary.get('request_attempts', 0) or 0)}",
            f"responses={int(summary.get('provider_response_events', 0) or 0)}",
            f"attempts_without_response_telemetry={int(summary.get('attempts_without_response_telemetry', 0) or 0)}",
            metric("prompt_tokens"),
            metric("completion_tokens"),
            metric("total_tokens"),
            metric("reasoning_tokens"),
            metric("cached_tokens"),
            metric("cache_write_tokens"),
            metric("cost"),
            f"response_healing_events={int(summary.get('response_healing_events', 0) or 0)}",
            f"model_mismatch_events={int(summary.get('served_model_mismatch_events', 0) or 0)}",
            f"stages(calls/attempts)={stage_text}",
            f"attempt_outcomes={attempt_outcome_text}",
            f"attempt_models={attempt_model_text}",
            f"failure_classes={failure_class_text}",
            f"http_statuses={http_status_text}",
            f"metadata_missing={metadata_missing_text}",
            f"providers={provider_text}",
            f"service_tiers={service_tier_text}",
            f"requested_models={requested_model_text}",
            f"served_models={served_model_text}",
            f"finish_reasons={finish_reason_text}",
            f"structured_output_recovery={recovery_text}",
        ]
    )
    return text[:limit]
