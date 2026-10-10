"""Stable bounded low-confidence semantic disposition for DCOIR Review."""

from __future__ import annotations

import copy
import math
from typing import Any

from dcoir_review import candidate_escalation_execution as candidate_execution
from dcoir_review import candidate_escalation_quality_retry as candidate_retry
from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import candidate_escalation_scope as candidate_scope
from dcoir_review import structured_result_retry as retry
from dcoir_review import structured_result_disposition_state as disposition_state
from dcoir_review.structured_result_disposition_state import ALLOW_ATTR

VERSION = "v52"
# A diff-mode result that is still entirely sub-floor after the whole-PR
# quality retry is adjudicated independently instead of failing the run, the
# same final disposition first-pass-deep reviews receive through escalation.
EXHAUSTED_RETRY_MODE = "exhausted-quality-retry"
LOW_CONFIDENCE_RETRY_PREFIX = (
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
    exhausted: bool = False,
) -> tuple[list[dict[str, Any]], float]:
    """Return only anchored/actionable near-threshold findings safe to bound.

    ``exhausted`` admits any sub-floor confidence once the whole-PR quality
    retry has already run; it is evaluated outside the inner allow window.
    """
    if (
        not (exhausted or bool(getattr(config, ALLOW_ATTR, False)))
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
    floor = 0.0 if exhausted else max(0.0, minimum - margin)
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



def exhausted_retry_pending(
    module: Any, result: Any, config: Any, risk_sentinels: list[Any], line_index: Any,
) -> dict[str, Any] | None:
    if not isinstance(result, dict) or result.get("_quality_retry_attempted") is not True:
        return None
    eligible, floor = eligible_low_confidence_findings(
        module, result, config, risk_sentinels, line_index, exhausted=True
    )
    if not eligible:
        return None
    return {
        "mode": EXHAUSTED_RETRY_MODE,
        "reason": "whole-PR quality retry left only sub-floor findings",
        "candidate_count": len(eligible),
        "candidate_floor": floor,
        "paths": sorted({str(item.get("path", "") or "") for item in eligible}),
    }


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
    exhausted = pending.get("mode") == EXHAUSTED_RETRY_MODE
    fallback = retry.broad_retry_fallback
    if exhausted:
        # The whole-PR retry already ran; never repeat it. Unavailable bounded
        # evidence widens to broad evidence, and anything else keeps the
        # result for the existing fail-closed publication gates.
        def fallback(*_args: Any) -> tuple[dict[str, Any], str, str]:
            return primary, primary_model, primary_tier
    reason = str(pending.get("reason", ""))
    staged = independent_disposition_config(config)
    if staged is None:
        return fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, reason, "independent-model-stack-unavailable"
        )
    context_scope = "candidate-scoped"
    evidence, evidence_reason = None, "path-budget"
    if selected_paths and len(selected_paths) <= max_paths:
        evidence, evidence_reason = candidate_scope.build_bounded_evidence(
            module, gh, pr, files, config, risk_sentinels, selected_paths
        )
    if evidence is None and exhausted:
        evidence = candidate_execution.broad_evidence(
            module, pr, files, diff, config, risk_sentinels,
            deep_context_block, review_mode, context_summary,
        )
        context_scope = "broader-context"
        selected_paths = {
            str(item.get("filename", "") or "").strip() for item in files
        } - {""}
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
            f"scope={context_scope}; independent_calls=1"
        ),
    )
    adjudicated, disposition_model, disposition_tier = candidate_execution.run_adjudicator(
        module, schema, staged, reporter, findings, evidence, context_scope
    )
    if outside_paths(module, adjudicated, selected_paths):
        return fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, reason, "disposition-outside-bounded-scope"
        )
    # Same bounded final-quality repair as the first-pass v44 adjudicator; a
    # retry that escapes the candidate paths keeps the first adjudication.
    first_adjudication = adjudicated
    adjudicated, retry_model, retry_tier = candidate_retry.retry_candidate_escalation(
        module, adjudicated, schema, staged, reporter, risk_sentinels, line_index,
        findings, evidence, context_scope,
    )
    if retry_model and outside_paths(module, adjudicated, selected_paths):
        candidate_retry.reject_out_of_scope(module, config, reporter, retry_model, adjudicated)
        adjudicated, retry_model, retry_tier = first_adjudication, None, None
    # Every candidate was adjudicated, so the result is the whole disposition.
    adjudicated[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR] = (
        adjudication.FINAL_ADJUDICATION_COMPLETION_TOKEN
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
            "independent_call_count": 2 if retry_model else 1,
            "disposition_model": disposition_model,
        },
    )
    model_label = f"{primary_model}; low-confidence-disposition={disposition_model}" + (
        f"; low-confidence-disposition-retry={retry_model}" if retry_model else ""
    )
    tier_label = ", ".join(
        item
        for item in (
            str(primary_tier or "").strip(),
            str(disposition_tier or "").strip(),
            str(retry_tier or "").strip(),
        )
        if item
    )
    return adjudicated, model_label, tier_label


def build_structured_result_disposition_stage(module: Any, next_review: Any) -> Any:
    original = next_review
    if not callable(original):
        raise RuntimeError("DCOIR structured-result disposition requires a callable hybrid review stage")

    def structured_result_disposition_stage(
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
        disposition_state.begin_pending(config)
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
        pending = disposition_state.get_pending(config)
        # Near-threshold structured-result disposition is intentionally ordinary-diff only;
        # first-pass/deep modes retain the existing v44 escalation contract.
        if review_mode != "diff":
            return result, model, tier
        if not isinstance(pending, dict):
            pending = exhausted_retry_pending(module, result, config, risk_sentinels, line_index)
        if not isinstance(pending, dict):
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

    return structured_result_disposition_stage
