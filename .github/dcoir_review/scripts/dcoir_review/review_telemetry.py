"""Canonical run-level OpenRouter execution telemetry for DCOIR Review.

The public API lives here; connector-safe support modules own state, event
normalization, and summary rendering. Telemetry is observational and fail-soft.
"""

from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass
from typing import Any

from dcoir_review.per_file_routing import PER_FILE_PROJECTION_ATTR
from dcoir_review import structured_result_disposition as structured_disposition
from dcoir_review.review_telemetry_state import (
    LEGACY_STAGE_LABEL_ATTR,
    SCHEMA_VERSION,
    SINK_ATTR,
    STAGE_LABEL_ATTR,
    SUMMARY_ATTR,
    RunTelemetrySink,
    ensure_sink,
    note_telemetry_error,
    telemetry_error_count,
)
from dcoir_review import review_telemetry_events as _telemetry_events

# Stable facade retained for telemetry contract tests and external diagnostic callers.
_drain_call = _telemetry_events._drain_call

def normalize_event(raw: Any, stage: str, attempt_outcome: str = "attempt_outcome_missing") -> dict[str, Any]:
    return _telemetry_events.normalize_event(raw, stage, attempt_outcome)

def normalize_attempt(raw: Any) -> dict[str, Any]:
    return _telemetry_events.normalize_attempt(raw)
from dcoir_review.review_telemetry_summary import compact_summary, summarize_sink


@dataclass(frozen=True)
class ReviewTelemetryCall:
    root_config: Any
    staged_config: Any
    sink: RunTelemetrySink
    stage: str

def _schema_properties(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    return properties if isinstance(properties, dict) else {}


def _explicit_stage_label(config: Any) -> str:
    value = getattr(config, STAGE_LABEL_ATTR, "")
    if not value:
        value = getattr(config, LEGACY_STAGE_LABEL_ATTR, "")
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
                filename == "structured_result_retry.py"
                and function == "broad_retry_fallback"
            ):
                return "broad-quality-retry"
            if (
                filename == "dcoir_review_required_runtime_patch_v32.py"
                and function in (
                    "openrouter_review_with_hybrid_first_pass",
                    "adversarial_confirmation_stage",
                )
                and locals_map.get("confirmation_prompt") is prompt
            ):
                return "independent-challenger"
            if (
                filename == "dcoir_review_required_runtime_patch_v35.py"
                and function in (
                    "openrouter_review_with_hybrid_first_pass",
                    "semantic_adjudication_stage",
                )
                and locals_map.get("prompt") is prompt
            ):
                return "semantic-adjudicator"
            if (
                filename in (
                    "dcoir_review_required_runtime_patch_v32.py",
                    "dcoir_review_required_runtime_patch_v44_execution.py",
                )
                and function == "run_challenger"
            ):
                return "independent-challenger"
            if (
                filename in (
                    "dcoir_review_required_runtime_patch_v35.py",
                    "dcoir_review_required_runtime_patch_v44_execution.py",
                )
                and function == "run_adjudicator"
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
            pending = getattr(config, structured_disposition.PENDING_ATTR, None)
            if isinstance(pending, dict) and pending:
                return "bounded-low-confidence-disposition"
        return explicit
    if bool(getattr(config, PER_FILE_PROJECTION_ATTR, False)):
        return "per-file-first-pass"

    callsite = _callsite_stage_label(prompt)
    if callsite:
        if callsite == "semantic-adjudicator":
            pending = getattr(config, structured_disposition.PENDING_ATTR, None)
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

def _copy_stage_local_telemetry(source: Any, target: Any) -> None:
    """Preserve v47's documented per-file telemetry readback contract."""
    for name in (
        "_openrouter_request_telemetry_events",
        "_openrouter_request_attempt_telemetry_events",
        "_openrouter_request_telemetry_error_count",
        "_openrouter_request_attempt_count",
        "_openrouter_last_request_telemetry",
    ):
        if hasattr(source, name):
            setattr(target, name, copy.deepcopy(getattr(source, name)))


def emit_run_telemetry(module: Any, reporter: Any) -> None:
    """Emit one bounded terminal run-telemetry summary without changing review flow."""

    config = getattr(reporter, "config", None)
    if config is None:
        return
    try:
        summary = summarize_sink(config)
        setattr(config, SUMMARY_ATTR, summary)
        message = compact_summary(summary)
    except Exception:
        note_telemetry_error(config)
        summary = {
            "schema_version": SCHEMA_VERSION,
            "telemetry_status": "unavailable",
            "telemetry_error_count": telemetry_error_count(config),
        }
        try:
            setattr(config, SUMMARY_ATTR, summary)
        except Exception:
            note_telemetry_error(config)
        message = (
            f"schema={SCHEMA_VERSION}; telemetry_status=unavailable; "
            f"telemetry_error_count={telemetry_error_count(config)}"
        )
    try:
        reporter.update("openrouter-telemetry", message)
        return
    except Exception:
        note_telemetry_error(config)
    try:
        emit = getattr(getattr(module, "base", None), "emit_status", None)
        if callable(emit):
            emit("openrouter-telemetry", message)
    except Exception:
        note_telemetry_error(config)



def prepare_review_call(prompt: Any, schema: Any, config: Any) -> ReviewTelemetryCall | None:
    try:
        sink = ensure_sink(config)
        stage = classify_stage(prompt, schema, config)
        staged = copy.copy(config)
        setattr(staged, SINK_ATTR, sink)
        staged.openrouter_capture_request_telemetry = True
        staged._openrouter_request_telemetry_events = []
        staged._openrouter_request_attempt_telemetry_events = []
        staged._openrouter_request_telemetry_error_count = 0
        staged._openrouter_request_attempt_count = 0
        staged._openrouter_last_request_telemetry = {}
        return ReviewTelemetryCall(config, staged, sink, stage)
    except Exception:
        note_telemetry_error(config)
        return None


def finish_review_call(state: ReviewTelemetryCall | None, outcome: str) -> None:
    if state is None:
        return
    try:
        _drain_call(state.staged_config, state.sink, state.stage, outcome)
    except Exception:
        note_telemetry_error(state.root_config)
    try:
        if bool(getattr(state.root_config, PER_FILE_PROJECTION_ATTR, False)):
            _copy_stage_local_telemetry(state.staged_config, state.root_config)
    except Exception:
        note_telemetry_error(state.root_config)
