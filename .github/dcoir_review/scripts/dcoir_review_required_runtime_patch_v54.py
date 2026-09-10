"""DCOIR Review v54 run-level OpenRouter execution telemetry.

Issue #519 closes an execution-observability gap under #457. The canonical
provider already records rich request metadata when capture is enabled, but that
history was stage-local and normally available only to the v47 per-file path.

v54 is deliberately behavior-neutral:
- every semantic model call receives a shallow config copy with telemetry capture
  enabled, preserving the caller's model/provider/retry configuration;
- a shared thread-safe sink survives the existing shallow stage projections;
- only whitelisted returned execution metadata is retained (never prompts,
  source text, headers, response bodies, or secrets);
- terminal progress reporting emits one bounded aggregate through the existing
  status/step-summary surface even when debug artifacts are disabled.

This overlay does not alter model selection, provider preferences, reasoning,
retry policy, concurrency, verifier authority, repair safety, or publication.

Scoped exemption: issue #519 keeps this maintained source above the 15,000-byte
connector-safe policy threshold because it centralizes one runtime patch surface.
"""

from __future__ import annotations

import copy
import inspect
import math
import threading
from collections import Counter
from typing import Any


VERSION = "v54"
APPLIED_MARKER = "_dcoir_review_v54_applied"
SINK_ATTR = "_dcoir_v54_run_telemetry_sink"
SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"
ERROR_COUNT_ATTR = "_dcoir_v54_telemetry_error_count"
PATCH_ERRORS_ATTR = "_dcoir_v54_patch_errors"
STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"
LOAD_STORAGE = "_dcoir_review_v54_original_load_pareto_context_config"
REVIEW_STORAGE = "_dcoir_review_v54_original_openrouter_review"
REPORTER_STORAGE = "_dcoir_review_v54_original_progress_reporter"
SCHEMA_VERSION = "dcoir_openrouter_run_telemetry_v1"


class RunTelemetrySink:
    """Shared, thread-safe request/call evidence for one loaded review config."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []

    def add_call(self, call: dict[str, Any], events: list[dict[str, Any]]) -> None:
        with self._lock:
            self._calls.append(dict(call))
            self._events.extend(dict(item) for item in events)

    def snapshot(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        with self._lock:
            return (
                [dict(item) for item in self._calls],
                [dict(item) for item in self._events],
            )


def _ensure_sink(config: Any) -> RunTelemetrySink:
    sink = getattr(config, SINK_ATTR, None)
    if isinstance(sink, RunTelemetrySink):
        return sink
    sink = RunTelemetrySink()
    setattr(config, SINK_ATTR, sink)
    return sink


def _telemetry_error_count(config: Any) -> int:
    try:
        value = int(getattr(config, ERROR_COUNT_ATTR, 0) or 0)
    except Exception:
        return 0
    return max(0, value)


def _note_telemetry_error(config: Any) -> None:
    """Best-effort error accounting that must itself never affect review behavior."""
    try:
        setattr(config, ERROR_COUNT_ATTR, _telemetry_error_count(config) + 1)
    except Exception:
        # Error accounting is advisory; never let it alter review behavior.
        return


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


def _schema_properties(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    return properties if isinstance(properties, dict) else {}


def _explicit_stage_label(config: Any) -> str:
    value = getattr(config, STAGE_LABEL_ATTR, "")
    return str(value or "").strip()


def _callsite_stage_label(prompt: Any) -> str:
    frame = inspect.currentframe()
    current = frame.f_back if frame is not None else None
    try:
        while current is not None:
            filename = current.f_code.co_filename.rsplit("/", 1)[-1]
            function = current.f_code.co_name
            locals_map = current.f_locals
            if (
                filename == "part_05a_hybrid_review.py"
                and function == "openrouter_review_with_hybrid_first_pass"
                and locals_map.get("retry_prompt") is prompt
            ):
                return "broad-quality-retry"
            if (
                filename == "part_05_debug_and_merge.py"
                and function == "openrouter_review_with_quality_retry"
                and locals_map.get("retry_prompt") is prompt
            ):
                return "broad-quality-retry"
            if (
                filename == "dcoir_review_required_runtime_patch_v22.py"
                and function == "openrouter_review_with_hybrid_first_pass"
                and locals_map.get("retry_prompt") is prompt
            ):
                return "broad-quality-retry"
            if (
                filename == "dcoir_review_required_runtime_patch_v52_retry.py"
                and function == "broad_retry_fallback"
            ):
                return "broad-quality-retry"
            if (
                filename in (
                    "dcoir_review_required_runtime_patch_v32.py",
                    "dcoir_review_required_runtime_patch_v44_execution.py",
                )
                and function in ("openrouter_review_with_hybrid_first_pass", "run_challenger")
            ):
                return "independent-challenger"
            if (
                filename in (
                    "dcoir_review_required_runtime_patch_v35.py",
                    "dcoir_review_required_runtime_patch_v44_execution.py",
                )
                and function in ("openrouter_review_with_hybrid_first_pass", "run_adjudicator")
            ):
                return "semantic-adjudicator"
            current = current.f_back
    finally:
        del frame
    return ""


def classify_stage(prompt: Any, schema: Any, config: Any) -> str:
    """Classify a model call without retaining the prompt itself."""
    explicit = _explicit_stage_label(config)
    if explicit:
        if explicit == "semantic-adjudicator":
            pending = getattr(config, "_dcoir_v52_pending_low_confidence_disposition", None)
            if isinstance(pending, dict) and pending:
                return "bounded-low-confidence-disposition"
        return explicit
    if bool(getattr(config, "dcoir_v47_per_file_projection", False)):
        return "per-file-first-pass"

    callsite = _callsite_stage_label(prompt)
    if callsite:
        if callsite == "semantic-adjudicator":
            pending = getattr(config, "_dcoir_v52_pending_low_confidence_disposition", None)
            if isinstance(pending, dict) and pending:
                return "bounded-low-confidence-disposition"
        return callsite

    properties = _schema_properties(schema)
    action = properties.get("action") if isinstance(properties.get("action"), dict) else {}
    action_enum = action.get("enum") if isinstance(action, dict) else None
    if isinstance(action_enum, list) and "repair_set" in action_enum:
        return "repair-author"
    if "supported" in properties:
        return "verifier"
    if "accepted" in properties and "reason" in properties:
        return "repair-critic"
    if "summary" in properties and "findings" in properties:
        return "primary-semantic"
    return "unclassified"


def normalize_event(raw: Any, stage: str, call_outcome: str) -> dict[str, Any]:
    """Whitelist returned execution metadata; never copy arbitrary response data."""
    item = raw if isinstance(raw, dict) else {}
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
    cost = _finite_number(item.get("cost"))
    if cost is None:
        cost = _usage_metric(usage, "cost")
    return {
        "stage": stage,
        "call_outcome": call_outcome,
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


def _drain_call(config: Any, sink: RunTelemetrySink, stage: str, outcome: str) -> None:
    history = getattr(config, "_openrouter_request_telemetry_events", None)
    raw_events = history if isinstance(history, list) else []
    events = [normalize_event(item, stage, outcome) for item in raw_events]
    try:
        attempts = int(getattr(config, "_openrouter_request_attempt_count", 0) or 0)
    except (TypeError, ValueError):
        attempts = 0
    attempts = max(0, attempts)
    attempt_map: dict[int, dict[str, Any]] = {}
    for event in events:
        raw_attempt = _finite_number(event.get("request_attempt_count"))
        if isinstance(raw_attempt, int) and 1 <= raw_attempt <= attempts:
            attempt_map.setdefault(raw_attempt, event)
    attempt_records: list[dict[str, Any]] = []
    for attempt_number in range(1, attempts + 1):
        event = attempt_map.get(attempt_number)
        if isinstance(event, dict):
            attempt_records.append(
                {
                    "attempt": attempt_number,
                    "outcome": "response_telemetry_observed",
                    "requested_model": str(event.get("requested_model", "") or ""),
                    "served_model": str(event.get("served_model", "") or ""),
                    "provider": str(event.get("provider", "") or ""),
                    "service_tier": str(event.get("service_tier", "") or ""),
                    "finish_reason": str(event.get("finish_reason", "") or ""),
                }
            )
        else:
            attempt_records.append(
                {
                    "attempt": attempt_number,
                    "outcome": "response_telemetry_missing",
                }
            )
    observed_attempts = len(attempt_map)
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


def summarize_sink(config: Any) -> dict[str, Any]:
    sink = _ensure_sink(config)
    calls, events = sink.snapshot()
    stage_calls = Counter(str(item.get("stage", "unclassified")) for item in calls)
    stage_attempts: Counter[str] = Counter()
    stage_responses: Counter[str] = Counter()
    stage_missing: Counter[str] = Counter()
    stage_attempt_outcomes: dict[str, Counter[str]] = {}
    stage_events: dict[str, list[dict[str, Any]]] = {}
    for item in calls:
        stage = str(item.get("stage", "unclassified"))
        stage_attempts[stage] += int(item.get("request_attempts", 0) or 0)
        stage_responses[stage] += int(item.get("response_events", 0) or 0)
        stage_missing[stage] += int(item.get("attempts_without_response_telemetry", 0) or 0)
        attempts = item.get("attempt_records")
        counter = stage_attempt_outcomes.setdefault(stage, Counter())
        if isinstance(attempts, list):
            for attempt in attempts:
                if isinstance(attempt, dict):
                    counter[str(attempt.get("outcome", "unclassified"))] += 1
    for event in events:
        stage = str(event.get("stage", "unclassified"))
        stage_events.setdefault(stage, []).append(event)
    providers = Counter(
        str(item.get("provider", "")) for item in events if str(item.get("provider", ""))
    )
    service_tiers = Counter(
        str(item.get("service_tier", "") or "").strip() or "unknown"
        for item in events
    )
    requested_models = Counter(
        str(item.get("requested_model", ""))
        for item in events
        if str(item.get("requested_model", ""))
    )
    served_models = Counter(
        str(item.get("served_model", ""))
        for item in events
        if str(item.get("served_model", ""))
    )
    finish_reasons = Counter(
        str(item.get("finish_reason", ""))
        for item in events
        if str(item.get("finish_reason", ""))
    )
    recoveries = Counter(
        str(item.get("structured_output_recovery", ""))
        for item in events
        if str(item.get("structured_output_recovery", ""))
    )
    total_attempts = sum(int(item.get("request_attempts", 0) or 0) for item in calls)
    total_responses = sum(int(item.get("response_events", 0) or 0) for item in calls)
    return {
        "schema_version": SCHEMA_VERSION,
        "telemetry_status": "ok" if _telemetry_error_count(config) == 0 else "partial",
        "telemetry_error_count": _telemetry_error_count(config),
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
                "providers": dict(
                    sorted(
                        Counter(
                            str(item.get("provider", ""))
                            for item in stage_events.get(stage, [])
                            if str(item.get("provider", ""))
                        ).items()
                    )
                ),
                "requested_models": dict(
                    sorted(
                        Counter(
                            str(item.get("requested_model", ""))
                            for item in stage_events.get(stage, [])
                            if str(item.get("requested_model", ""))
                        ).items()
                    )
                ),
                "served_models": dict(
                    sorted(
                        Counter(
                            str(item.get("served_model", ""))
                            for item in stage_events.get(stage, [])
                            if str(item.get("served_model", ""))
                        ).items()
                    )
                ),
                "finish_reasons": dict(
                    sorted(
                        Counter(
                            str(item.get("finish_reason", ""))
                            for item in stage_events.get(stage, [])
                            if str(item.get("finish_reason", ""))
                        ).items()
                    )
                ),
                "service_tiers": dict(
                    sorted(
                        Counter(
                            str(item.get("service_tier", "") or "").strip() or "unknown"
                            for item in stage_events.get(stage, [])
                        ).items()
                    )
                ),
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
            f"providers={provider_text}",
            f"service_tiers={service_tier_text}",
            f"requested_models={requested_model_text}",
            f"served_models={served_model_text}",
            f"finish_reasons={finish_reason_text}",
            f"structured_output_recovery={recovery_text}",
        ]
    )
    return text[:limit]


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, LOAD_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, LOAD_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v54 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        try:
            _ensure_sink(config)
        except Exception:
            _note_telemetry_error(config)
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _patch_openrouter_review(module: Any) -> None:
    hardened = module.hardened
    original = getattr(hardened, REVIEW_STORAGE, None)
    if original is None:
        original = getattr(hardened, "openrouter_review", None)
        if callable(original):
            setattr(hardened, REVIEW_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v54 could not locate hardened openrouter_review")

    def openrouter_review(prompt, schema, config, reporter=None):
        try:
            sink = _ensure_sink(config)
            stage = classify_stage(prompt, schema, config)
            staged = copy.copy(config)
            setattr(staged, SINK_ATTR, sink)
            staged.openrouter_capture_request_telemetry = True
            staged._openrouter_request_telemetry_events = []
            staged._openrouter_request_attempt_count = 0
            staged._openrouter_last_request_telemetry = {}
        except Exception:
            _note_telemetry_error(config)
            return original(prompt, schema, config, reporter)

        try:
            result = original(prompt, schema, staged, reporter)
        except Exception:
            try:
                _drain_call(staged, sink, stage, "failed")
            except Exception:
                _note_telemetry_error(config)
            try:
                if bool(getattr(config, "dcoir_v47_per_file_projection", False)):
                    _copy_stage_local_telemetry(staged, config)
            except Exception:
                _note_telemetry_error(config)
            raise

        try:
            _drain_call(staged, sink, stage, "success")
        except Exception:
            _note_telemetry_error(config)
        try:
            if bool(getattr(config, "dcoir_v47_per_file_projection", False)):
                _copy_stage_local_telemetry(staged, config)
        except Exception:
            _note_telemetry_error(config)
        return result

    hardened.openrouter_review = openrouter_review
    if hasattr(module, "openrouter_review"):
        module.openrouter_review = openrouter_review


def _copy_stage_local_telemetry(source: Any, target: Any) -> None:
    """Preserve v47's documented per-file telemetry readback contract."""
    for name in (
        "_openrouter_request_telemetry_events",
        "_openrouter_request_attempt_count",
        "_openrouter_last_request_telemetry",
    ):
        if hasattr(source, name):
            setattr(target, name, copy.deepcopy(getattr(source, name)))


def _patch_progress_reporter(module: Any) -> None:
    hardened = module.hardened
    original = getattr(hardened, REPORTER_STORAGE, None)
    if original is None:
        original = getattr(hardened, "ProgressReporter", None)
        if isinstance(original, type):
            setattr(hardened, REPORTER_STORAGE, original)
    if not isinstance(original, type):
        raise RuntimeError("DCOIR v54 could not locate ProgressReporter")

    class TelemetryProgressReporter(original):
        def _emit_run_telemetry(self) -> None:
            config = getattr(self, "config", None)
            if config is None:
                return
            try:
                summary = summarize_sink(config)
                setattr(config, SUMMARY_ATTR, summary)
                message = compact_summary(summary)
            except Exception:
                _note_telemetry_error(config)
                summary = {
                    "schema_version": SCHEMA_VERSION,
                    "telemetry_status": "unavailable",
                    "telemetry_error_count": _telemetry_error_count(config),
                }
                try:
                    setattr(config, SUMMARY_ATTR, summary)
                except Exception:
                    # The bounded status message remains usable without persistence.
                    _note_telemetry_error(config)
                message = (
                    f"schema={SCHEMA_VERSION}; telemetry_status=unavailable; "
                    f"telemetry_error_count={_telemetry_error_count(config)}"
                )
            try:
                self.update("openrouter-telemetry", message)
                return
            except Exception:
                _note_telemetry_error(config)
            try:
                emit = getattr(getattr(module, "base", None), "emit_status", None)
                if callable(emit):
                    emit("openrouter-telemetry", message)
            except Exception:
                _note_telemetry_error(config)

        def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
            try:
                self._emit_run_telemetry()
            except Exception:
                _note_telemetry_error(getattr(self, "config", None))
            super().complete(model_used, findings_count, review_event)

        def fail(self, message: str) -> None:
            try:
                self._emit_run_telemetry()
            except Exception:
                _note_telemetry_error(getattr(self, "config", None))
            super().fail(message)

    TelemetryProgressReporter.__name__ = getattr(original, "__name__", "ProgressReporter")
    hardened.ProgressReporter = TelemetryProgressReporter
    if hasattr(module, "ProgressReporter"):
        module.ProgressReporter = TelemetryProgressReporter


def _capture_attr(target: Any, name: str) -> tuple[bool, Any]:
    if target is None:
        return (False, None)
    if hasattr(target, name):
        return (True, getattr(target, name))
    return (False, None)


def _restore_attr(target: Any, name: str, state: tuple[bool, Any]) -> None:
    if target is None:
        return
    exists, value = state
    if exists:
        setattr(target, name, value)
        return
    if hasattr(target, name):
        delattr(target, name)


def _restore_patch_state(module: Any, hardened: Any, snapshot: dict[str, tuple[bool, Any]]) -> None:
    for target, name, key in (
        (module, "load_pareto_context_config", "module.load_pareto_context_config"),
        (module, LOAD_STORAGE, "module.load-storage"),
        (module, "openrouter_review", "module.openrouter_review"),
        (module, "ProgressReporter", "module.ProgressReporter"),
        (hardened, REVIEW_STORAGE, "hardened.review-storage"),
        (hardened, REPORTER_STORAGE, "hardened.reporter-storage"),
        (hardened, "openrouter_review", "hardened.openrouter_review"),
        (hardened, "ProgressReporter", "hardened.ProgressReporter"),
    ):
        try:
            _restore_attr(target, name, snapshot[key])
        except Exception:
            _note_telemetry_error(module)


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    hardened = getattr(module, "hardened", None)
    snapshot = {
        "module.load_pareto_context_config": _capture_attr(module, "load_pareto_context_config"),
        "module.load-storage": _capture_attr(module, LOAD_STORAGE),
        "module.openrouter_review": _capture_attr(module, "openrouter_review"),
        "module.ProgressReporter": _capture_attr(module, "ProgressReporter"),
        "hardened.review-storage": _capture_attr(hardened, REVIEW_STORAGE),
        "hardened.reporter-storage": _capture_attr(hardened, REPORTER_STORAGE),
        "hardened.openrouter_review": _capture_attr(hardened, "openrouter_review"),
        "hardened.ProgressReporter": _capture_attr(hardened, "ProgressReporter"),
    }
    errors: list[str] = []
    for name, patcher in (
        ("config-loader", _patch_config_loader),
        ("openrouter-review", _patch_openrouter_review),
        ("progress-reporter", _patch_progress_reporter),
    ):
        try:
            patcher(module)
        except Exception:
            errors.append(name)
    if errors:
        _restore_patch_state(module, hardened, snapshot)
    try:
        setattr(module, PATCH_ERRORS_ATTR, tuple(errors))
    except Exception:
        # Patch-error metadata is advisory and must not block module startup.
        _note_telemetry_error(module)
    try:
        setattr(module, APPLIED_MARKER, not errors)
    except Exception:
        # Some proxy modules may reject attributes; review behavior still proceeds.
        _note_telemetry_error(module)
