"""Bounded low-confidence semantic disposition for DCOIR Review v52."""

from __future__ import annotations

import copy
import math
from typing import Any

import dcoir_review_required_runtime_patch_v44_execution as v44_execution
import dcoir_review_required_runtime_patch_v44_scope as v44_scope
import dcoir_review_required_runtime_patch_v52_retry as retry

VERSION = "v52"
ALLOW_ATTR = "_dcoir_v52_allow_low_confidence_disposition"
PENDING_ATTR = "_dcoir_v52_pending_low_confidence_disposition"
_RETRY_STORAGE = "_dcoir_review_v52_prior_quality_retry_reason"
_HYBRID_STORAGE = "_dcoir_review_v52_prior_hybrid_first_pass"
_LOW_CONFIDENCE_PREFIX = (
    "model returned structured findings, but none met the configured minimum confidence"
)
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
_STRING_FINDING_FIELDS = (
    "title", "severity", "path", "body", "suggested_replacement", "validation"
)
_SEVERITIES = {"critical", "high", "medium", "low"}


def confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and 0.0 <= parsed <= 1.0 else None


def bounded_disposition_enabled(config: Any) -> bool:
    """Respect the existing Architecture-B escalation/adjudication feature gates."""
    return all(
        bool(getattr(config, name, True))
        for name in (
            "candidate_scoped_escalation_review",
            "adversarial_confirmation_review",
            "semantic_adjudication_review",
        )
    )


def eligible_low_confidence_findings(
    module: Any,
    result: dict[str, Any],
    config: Any,
    risk_sentinels: list[Any],
    line_index: dict[tuple[str, int], int] | None,
) -> tuple[list[dict[str, Any]], float]:
    """Return only anchored/actionable near-threshold findings safe to bound."""
    if (
        not bool(getattr(config, ALLOW_ATTR, False))
        or line_index is None
        or not bounded_disposition_enabled(config)
    ):
        return [], 0.0
    try:
        if module.hardened.required_risk_sentinels(risk_sentinels):
            return [], 0.0
    except Exception:
        return [], 0.0
    minimum = confidence(getattr(config, "minimum_confidence", 0.70))
    margin = confidence(getattr(config, "candidate_escalation_confidence_margin", 0.10))
    if minimum is None or margin is None:
        return [], 0.0
    floor = max(0.0, minimum - margin)
    raw_findings = result.get("findings") if isinstance(result, dict) else None
    if not isinstance(raw_findings, list) or not raw_findings:
        return [], floor
    eligible: list[dict[str, Any]] = []
    for raw in raw_findings:
        if (
            not isinstance(raw, dict)
            or any(field not in raw for field in _REQUIRED_FINDING_FIELDS)
            or any(not isinstance(raw.get(field), str) for field in _STRING_FINDING_FIELDS)
            or str(raw.get("severity", "")).lower() not in _SEVERITIES
        ):
            return [], floor
        raw_confidence = raw.get("confidence")
        raw_line = raw.get("line")
        if (
            isinstance(raw_confidence, bool)
            or not isinstance(raw_confidence, (int, float))
            or isinstance(raw_line, bool)
            or not isinstance(raw_line, int)
        ):
            return [], floor
        item = dict(raw)
        if module.hardened.non_actionable_finding_reason(item):
            return [], floor
        item_confidence = confidence(raw_confidence)
        path = str(item.get("path", "") or "").strip()
        line = raw_line
        if (
            item_confidence is None
            or item_confidence < floor
            or item_confidence >= minimum
            or not path
            or line <= 0
            or (path, line) not in line_index
        ):
            return [], floor
        eligible.append(item)
    return eligible, floor


def patch_quality_retry_reason(module: Any) -> None:
    hardened = module.hardened
    original = getattr(hardened, _RETRY_STORAGE, None)
    if original is None:
        original = getattr(hardened, "review_quality_retry_reason", None)
        if callable(original):
            setattr(hardened, _RETRY_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v52 could not locate review_quality_retry_reason")

    def review_quality_retry_reason(result, config, risk_sentinels, line_index=None):
        reason = original(result, config, risk_sentinels, line_index)
        setattr(config, PENDING_ATTR, None)
        if not str(reason or "").startswith(_LOW_CONFIDENCE_PREFIX):
            return reason
        eligible, floor = eligible_low_confidence_findings(
            module, result, config, risk_sentinels, line_index
        )
        if not eligible:
            return reason
        pending = {
            "reason": str(reason),
            "candidate_count": len(eligible),
            "candidate_floor": floor,
            "paths": sorted({str(item.get("path", "") or "") for item in eligible}),
        }
        setattr(config, PENDING_ATTR, pending)
        module.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/v52-structured-low-confidence.json",
            {"version": VERSION, "mode": "bounded-disposition-pending", **pending},
        )
        return ""

    hardened.review_quality_retry_reason = review_quality_retry_reason


def outside_paths(module: Any, result: dict[str, Any], selected_paths: set[str]) -> bool:
    return any(
        isinstance(item, dict)
        and str(item.get("path", "") or "").strip() not in selected_paths
        for item in module.hardened.result_findings(result)
    )


def independent_disposition_config(config: Any) -> Any | None:
    """Clone config with the configured independent-confirmation model stack."""
    raw_models = getattr(config, "adversarial_confirmation_model_stack", None)
    if not isinstance(raw_models, (list, tuple)):
        return None
    models = [str(item).strip() for item in raw_models if str(item).strip()]
    if not models:
        return None
    staged = copy.copy(config)
    staged.semantic_adjudication_model_stack = models
    return staged


def bounded_low_confidence_disposition(
    module: Any,
    primary: dict[str, Any],
    primary_model: str,
    primary_tier: str,
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
    risk_sentinels: list[Any],
    line_index: dict[tuple[str, int], int],
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
    gh: Any,
    pending: dict[str, Any],
) -> tuple[dict[str, Any], str, str]:
    findings = [
        dict(item)
        for item in module.hardened.result_findings(primary)
        if isinstance(item, dict)
    ]
    selected_paths = {str(item.get("path", "") or "").strip() for item in findings}
    try:
        max_paths = max(1, int(getattr(config, "candidate_escalation_max_paths", 4) or 4))
    except (TypeError, ValueError):
        max_paths = 0
    fallback = retry.broad_retry_fallback
    reason = str(pending.get("reason", ""))
    if not selected_paths or len(selected_paths) > max_paths:
        return fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, reason, "path-budget"
        )
    staged = independent_disposition_config(config)
    if staged is None:
        return fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, reason, "independent-model-stack-unavailable"
        )
    evidence, evidence_reason = v44_scope.build_bounded_evidence(
        module, gh, pr, files, config, risk_sentinels, selected_paths
    )
    if evidence is None:
        return fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, reason, evidence_reason or "bounded-evidence-unavailable"
        )

    reporter.update(
        "structured-low-confidence-disposition",
        (
            f"candidates={len(findings)}; paths={len(selected_paths)}; "
            f"floor={float(pending.get('candidate_floor', 0.0)):.2f}; "
            "scope=candidate-scoped; independent_calls=1"
        ),
    )
    adjudicated, disposition_model, disposition_tier = v44_execution.run_adjudicator(
        module, schema, staged, reporter, findings, evidence, "candidate-scoped"
    )
    if outside_paths(module, adjudicated, selected_paths):
        return fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, reason, "disposition-outside-bounded-scope"
        )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/v52-structured-low-confidence.json",
        {
            "version": VERSION,
            "mode": "bounded-disposition-complete",
            **pending,
            "input_hypotheses": len(findings),
            "output_findings": len(module.hardened.result_findings(adjudicated)),
            "independent_call_count": 1,
            "disposition_model": disposition_model,
        },
    )
    model_label = f"{primary_model}; low-confidence-disposition={disposition_model}"
    tier_label = ", ".join(
        item
        for item in (
            str(primary_tier or "").strip(),
            str(disposition_tier or "").strip(),
        )
        if item
    )
    return adjudicated, model_label, tier_label


def patch_hybrid(module: Any) -> None:
    original = getattr(module, _HYBRID_STORAGE, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, _HYBRID_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v52 could not locate active hybrid review function")

    def openrouter_review_with_hybrid_first_pass(
        pr,
        files,
        diff,
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        setattr(config, PENDING_ATTR, None)
        setattr(config, ALLOW_ATTR, review_mode == "diff")
        try:
            result, model, tier = original(
                pr,
                files,
                diff,
                schema,
                config,
                reporter,
                risk_sentinels,
                line_index,
                deep_context_block,
                review_mode,
                context_summary,
                gh,
            )
        finally:
            setattr(config, ALLOW_ATTR, False)
        pending = getattr(config, PENDING_ATTR, None)
        # v52's near-threshold disposition is intentionally ordinary-diff only;
        # first-pass/deep modes retain the existing v44 escalation contract.
        if review_mode != "diff" or not isinstance(pending, dict):
            return result, model, tier
        return bounded_low_confidence_disposition(
            module,
            result,
            model,
            tier,
            pr,
            files,
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
            pending,
        )

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass
