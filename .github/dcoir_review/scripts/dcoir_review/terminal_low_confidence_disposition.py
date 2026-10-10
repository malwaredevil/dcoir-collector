"""Terminal disposition of final adjudication results that are entirely sub-floor.

A complete final adjudication whose every finding is anchored, actionable, and
below the publication floor is reported as a clean review instead of failing
the run. When required deterministic risk sentinels exist, the same sub-floor
shape instead yields to the sentinel fallback findings.
"""

from __future__ import annotations

import math
from typing import Any

from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import semantic_adjudication_quality_retry as quality_retry


VERSION = "v57"
DISPOSITION_MARKER = "_dcoir_v57_terminal_low_confidence_disposition"
SENTINEL_FALLBACK_MARKER = "_dcoir_v57_required_sentinel_fallback_disposition"
SENTINEL_FALLBACK_SUMMARY = (
    "No model finding met the publication confidence floor; required deterministic "
    "high-risk findings are reported from exact head evidence."
)
CLEAN_SUMMARY = "No high confidence findings were found after semantic adjudication."
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_MAX_TITLE_LENGTH = 120
_REQUIRED_FINDING_FIELDS = (
    "title",
    "severity",
    "confidence",
    "path",
    "line",
    "body",
    "suggested_replacement",
    "validation",
)
_STRING_FINDING_FIELDS = ("title", "severity", "path", "body", "suggested_replacement", "validation")
_RESULT_ALLOWED_KEYS = {
    "summary",
    "findings",
    "_semantic_adjudication_attempted",
    "_semantic_adjudication_model",
    "_semantic_adjudication_input_candidates",
    "_semantic_adjudication_output_findings",
    "_semantic_adjudication_context_scope",
    "_semantic_adjudication_overflow_trimmed",
    "_semantic_adjudication_result_shape",
    "_semantic_adjudication_shape_recovery",
    "_semantic_adjudication_confidence_normalization",
    "_semantic_adjudication_confidence_normalized_count",
    adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR,
    "_candidate_escalation",
    "_semantic_context_package_id",
    "_adaptive_semantic_budget_mode",
    adjudication.PROVIDER_RESULT_KEYS_ATTR,
}



def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        parsed = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        return None
    return parsed


def publication_floor(config: Any) -> float | None:
    return _confidence(getattr(config, "minimum_confidence", None))


def _complete_subthreshold_candidate(
    module: Any,
    item: Any,
    floor: float,
    line_index: dict[tuple[str, int], int],
) -> tuple[dict[str, Any], float] | None:
    """Return a schema-valid final finding whose confidence is below the floor.

    Nothing below the floor is ever published, so advisory content (a suggested
    replacement, an empty body or validation, an informational framing, or an
    anchor outside the changed lines) does not block the terminal disposition.
    Malformed shapes and publishable confidences keep the fail-closed split.
    """

    if not isinstance(item, dict):
        return None
    keys = set(item.keys())
    if not set(_REQUIRED_FINDING_FIELDS) <= keys:
        return None
    if any(not key.startswith("_") for key in keys - set(_REQUIRED_FINDING_FIELDS)):
        return None  # The provider schema forbids additional finding fields.
    if any(not isinstance(item.get(field), str) for field in _STRING_FINDING_FIELDS):
        return None
    for field in ("title", "severity", "path"):
        if not str(item.get(field) or "").strip():
            return None
    if len(str(item.get("title", "") or "")) > _MAX_TITLE_LENGTH:
        return None
    if item.get("severity") not in _VALID_SEVERITIES:
        return None

    raw_line = item.get("line")
    if isinstance(raw_line, bool) or not isinstance(raw_line, int) or raw_line <= 0:
        return None

    confidence = _confidence(item.get("confidence"))
    if confidence is None or confidence >= floor:
        return None
    return dict(item), confidence


def _required_sentinels_absent(module: Any, risk_sentinels: list[Any]) -> bool:
    try:
        required = module.hardened.required_risk_sentinels(risk_sentinels)
    except Exception:
        return False
    return not bool(required)


def _summary_allows_clean(module: Any, result: dict[str, Any], config: Any) -> bool:
    """Honor existing summary-only problem gating before clearing findings."""

    raw_summary = result.get("summary")
    if not isinstance(raw_summary, str) or not raw_summary.strip():
        return False
    if not bool(getattr(config, "fail_on_summary_only_problem", True)):
        return True
    try:
        return not bool(module.hardened.summary_suggests_problem(raw_summary.strip()))
    except Exception:
        return False


def _completed_final_adjudication_matches_result(result: dict[str, Any], raw_findings: list[Any]) -> bool:
    """Require internally recorded final semantic-adjudication evidence.

    v35 and candidate-escalation (v44/v52) stages set the completion token only
    when their result is the complete adjudication of every candidate.
    """

    if result.get("_semantic_adjudication_attempted") is not True:
        return False
    model = result.get("_semantic_adjudication_model")
    if not isinstance(model, str) or not model.strip():
        return False
    input_count = result.get("_semantic_adjudication_input_candidates")
    if isinstance(input_count, bool) or not isinstance(input_count, int) or input_count <= 0:
        return False

    if "_semantic_adjudication_overflow_trimmed" in result:
        return False

    output_count = result.get("_semantic_adjudication_output_findings")
    if isinstance(output_count, bool) or not isinstance(output_count, int):
        return False
    if output_count != len(raw_findings):
        return False

    if result.get(adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR) is not adjudication.FINAL_ADJUDICATION_COMPLETION_TOKEN:
        return False
    return True


def _provider_envelope_matches_schema(result: dict[str, Any]) -> bool:
    raw_provider_keys = result.get(adjudication.PROVIDER_RESULT_KEYS_ATTR)
    if not isinstance(raw_provider_keys, (list, tuple)):
        return False
    provider_keys = {str(key) for key in raw_provider_keys}
    if provider_keys != {"summary", "findings"}:
        return False
    # A bounded quality retry is a second provider response; its envelope
    # must match the schema too before a clean terminal disposition.
    if result.get("_quality_retry_attempted") is True:
        retry_keys = result.get("_quality_retry_provider_result_keys")
        if not isinstance(retry_keys, (list, tuple)):
            return False
        return {str(key) for key in retry_keys} == {"summary", "findings"}
    return True


def terminal_disposition(
    module: Any,
    result: Any,
    config: Any,
    line_index: dict[tuple[str, int], int],
    risk_sentinels: list[Any] | None,
) -> dict[str, Any] | None:
    """Classify only the final semantic-adjudication all-sub-threshold terminal shape."""

    if not isinstance(result, dict) or not isinstance(line_index, dict):
        return None
    if not set(result.keys()).issubset(
        _RESULT_ALLOWED_KEYS | quality_retry.QUALITY_RETRY_RESULT_KEYS
    ):
        return None
    if not quality_retry.quality_retry_metadata_is_valid(result):
        return None
    if not _provider_envelope_matches_schema(result):
        return None

    raw_findings = result.get("findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        return None
    if not _completed_final_adjudication_matches_result(result, raw_findings):
        return None
    if not _summary_allows_clean(module, result, config):
        return None

    sentinels = list(risk_sentinels or [])
    if not _required_sentinels_absent(module, sentinels):
        return None

    disposition = _subthreshold_disposition(module, raw_findings, config, line_index)
    if disposition is None:
        return None
    scope = str(result.get("_semantic_adjudication_context_scope", "") or "")
    disposition["adjudication_model"] = str(result.get("_semantic_adjudication_model", "") or "")
    disposition["adjudication_scope"] = f"final-{scope}" if scope else "final-v35"
    return disposition


def _subthreshold_disposition(
    module: Any, raw_findings: Any, config: Any, line_index: Any,
) -> dict[str, Any] | None:
    """Describe a non-empty finding set that is entirely complete, anchored, sub-floor."""

    floor = publication_floor(config)
    if floor is None or not isinstance(raw_findings, list) or not raw_findings:
        return None
    if not isinstance(line_index, dict):
        return None
    candidates: list[dict[str, Any]] = []
    confidences: list[float] = []
    for raw in raw_findings:
        qualified = _complete_subthreshold_candidate(module, raw, floor, line_index)
        if qualified is None:
            return None
        item, confidence = qualified
        candidates.append(item)
        confidences.append(confidence)
    return {
        "version": VERSION,
        "candidate_count": len(candidates),
        "minimum_confidence": floor,
        "lowest_confidence": min(confidences),
        "highest_confidence": max(confidences),
        "candidates": [
            {
                "path": str(item.get("path", "") or ""),
                "line": int(item.get("line", 0) or 0),
                "severity": str(item.get("severity", "") or ""),
                "confidence": confidence,
                "title": str(item.get("title", "") or "")[:_MAX_TITLE_LENGTH],
            }
            for item, confidence in zip(candidates, confidences)
        ],
    }


def sentinel_fallback_disposition(
    module: Any, result: Any, config: Any, line_index: Any, risk_sentinels: Any,
) -> dict[str, Any] | None:
    """Classify an all-sub-floor model result that must not hide sentinel findings.

    Required deterministic risk sentinels are published from exact head
    evidence by the downstream fallback, so a sub-floor-only model result must
    not abort the run and suppress them. This is never a clean claim, so the
    model summary (which naturally names the flagged risk) does not gate it.
    The result must already have been repaired: either a completed final
    adjudication with matching evidence, or a whole-PR quality retry with
    valid retry metadata. Partial or unrepaired results, malformed findings,
    and publishable findings keep the fail-closed split.
    """

    if not isinstance(result, dict) or not set(result.keys()).issubset(
        _RESULT_ALLOWED_KEYS | quality_retry.QUALITY_RETRY_RESULT_KEYS
    ):
        return None
    if not quality_retry.quality_retry_metadata_is_valid(result):
        return None
    findings = result.get("findings")
    if not isinstance(findings, list):
        return None
    if adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR in result:
        if not (
            _provider_envelope_matches_schema(result)
            and _completed_final_adjudication_matches_result(result, findings)
        ):
            return None
    elif result.get("_quality_retry_attempted") is not True:
        return None
    if _required_sentinels_absent(module, list(risk_sentinels or [])):
        return None
    disposition = _subthreshold_disposition(module, findings, config, line_index)
    if disposition is not None:
        disposition["mode"] = "required-sentinel-fallback"
    return disposition


def record_terminal_disposition(
    module: Any, result: dict[str, Any], disposition: dict[str, Any], config: Any,
    marker: str = DISPOSITION_MARKER, summary: str = CLEAN_SUMMARY,
) -> None:
    result[marker] = disposition
    result["findings"] = []
    result["summary"] = summary

    try:
        module.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/v57-terminal-low-confidence-disposition.json",
            disposition,
        )
    except Exception as exc:
        emit = getattr(module.base, "emit_status", None)
        if callable(emit):
            emit(
                "terminal-low-confidence-disposition",
                f"version={VERSION}; artifact_write_failed={exc.__class__.__name__}",
            )

    try:
        emit = getattr(module.base, "emit_status", None)
        if callable(emit):
            emit(
                "terminal-low-confidence-disposition",
                (
                    f"version={VERSION}; candidates={disposition['candidate_count']}; "
                    f"publication_floor={float(disposition['minimum_confidence']):.2f}; "
                    f"confidence_range={float(disposition['lowest_confidence']):.2f}-"
                    f"{float(disposition['highest_confidence']):.2f}; "
                    f"result={disposition.get('mode', 'clean')}"
                ),
            )
    except Exception as exc:
        print(f"[dcoir {VERSION}] terminal-low-confidence-disposition emit failed: {exc.__class__.__name__}")
