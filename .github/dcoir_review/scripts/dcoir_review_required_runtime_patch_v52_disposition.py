"""Bounded low-confidence semantic disposition for DCOIR Review v52."""

from __future__ import annotations

import math
from typing import Any

import dcoir_review_required_runtime_patch_v44_execution as v44_execution
import dcoir_review_required_runtime_patch_v44_scope as v44_scope

VERSION = "v52"
ALLOW_ATTR = "_dcoir_v52_allow_low_confidence_disposition"
PENDING_ATTR = "_dcoir_v52_pending_low_confidence_disposition"
_RETRY_STORAGE = "_dcoir_review_v52_prior_quality_retry_reason"
_HYBRID_STORAGE = "_dcoir_review_v52_prior_hybrid_first_pass"
_LOW_CONFIDENCE_PREFIX = (
    "model returned structured findings, but none met the configured minimum confidence"
)


def confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and 0.0 <= parsed <= 1.0 else None


def eligible_low_confidence_findings(
    module: Any,
    result: dict[str, Any],
    config: Any,
    risk_sentinels: list[Any],
    line_index: dict[tuple[str, int], int] | None,
) -> tuple[list[dict[str, Any]], float]:
    """Return only anchored/actionable near-threshold findings safe to bound."""
    if not bool(getattr(config, ALLOW_ATTR, False)) or line_index is None:
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
    findings = module.hardened.result_findings(result)
    if not findings:
        return [], floor
    eligible: list[dict[str, Any]] = []
    for raw in findings:
        if not isinstance(raw, dict):
            return [], floor
        item = dict(raw)
        if module.hardened.non_actionable_finding_reason(item):
            return [], floor
        item_confidence = confidence(item.get("confidence"))
        try:
            path = str(item.get("path", "") or "").strip()
            line = int(item.get("line", 0) or 0)
        except (TypeError, ValueError):
            return [], floor
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


def broad_retry_fallback(
    module: Any,
    primary: dict[str, Any],
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
    reason: str,
    fallback_reason: str,
) -> tuple[dict[str, Any], str, str]:
    reporter.update(
        "quality-retry",
        (
            f"{module.hardened.sanitize_github_output(reason, config)}; "
            f"bounded disposition unavailable ({fallback_reason}); "
            "retrying with whole-PR repair prompt"
        ),
    )
    aggregate_prompt = module.build_prompt(
        pr,
        files,
        diff,
        config,
        risk_sentinels,
        deep_context_block,
        review_mode,
        context_summary,
    )
    retry_sentinels = module.hardened.required_risk_sentinels(risk_sentinels) or risk_sentinels
    retry_prompt = module.hardened.build_quality_retry_prompt(
        aggregate_prompt, primary, retry_sentinels, config, reason
    )
    module.hardened.write_debug_text_artifact_safely(
        config, "prompts/10-v52-broad-quality-retry.txt", retry_prompt
    )
    retry_result, model, tier = module.hardened.openrouter_review(
        retry_prompt, schema, config, reporter
    )
    merged = module.hardened.merge_quality_retry_results(
        initial_result=primary,
        retry_result=retry_result,
        config=config,
        line_index=line_index,
        retry_reason=reason,
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "responses/10-v52-broad-quality-retry.json",
        {
            "fallback_reason": fallback_reason,
            "model_used": model,
            "service_tier": tier,
            "result": merged,
        },
    )
    return merged, model, tier


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
    if not selected_paths or len(selected_paths) > max_paths:
        return broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")), "path-budget"
        )
    evidence, evidence_reason = v44_scope.build_bounded_evidence(
        module, gh, pr, files, config, risk_sentinels, selected_paths
    )
    if evidence is None:
        return broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")),
            evidence_reason or "bounded-evidence-unavailable"
        )

    reporter.update(
        "structured-low-confidence-disposition",
        (
            f"candidates={len(findings)}; paths={len(selected_paths)}; "
            f"floor={float(pending.get('candidate_floor', 0.0)):.2f}; "
            "scope=candidate-scoped"
        ),
    )
    challenger, challenger_model, challenger_tier = v44_execution.run_challenger(
        module, schema, config, reporter, evidence, "candidate-scoped"
    )
    if outside_paths(module, challenger, selected_paths):
        return broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")),
            "challenger-outside-bounded-scope"
        )
    hypotheses = v44_scope.dedupe_exact_findings(
        findings
        + [
            dict(item)
            for item in module.hardened.result_findings(challenger)
            if isinstance(item, dict)
        ]
    )
    adjudicated, adjudicator_model, adjudicator_tier = v44_execution.run_adjudicator(
        module, schema, config, reporter, hypotheses, evidence, "candidate-scoped"
    )
    if outside_paths(module, adjudicated, selected_paths):
        return broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")),
            "adjudicator-outside-bounded-scope"
        )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "metadata/v52-structured-low-confidence.json",
        {
            "version": VERSION,
            "mode": "bounded-disposition-complete",
            **pending,
            "input_hypotheses": len(hypotheses),
            "output_findings": len(module.hardened.result_findings(adjudicated)),
            "challenger_model": challenger_model,
            "adjudicator_model": adjudicator_model,
        },
    )
    model_label = (
        f"{primary_model}; low-confidence-challenger={challenger_model}; "
        f"low-confidence-adjudicator={adjudicator_model}"
    )
    tier_label = ", ".join(
        item
        for item in (
            str(primary_tier or "").strip(),
            str(challenger_tier or "").strip(),
            str(adjudicator_tier or "").strip(),
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
        setattr(config, ALLOW_ATTR, review_mode in {"diff", "first-pass-deep"})
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
        # In first-pass-deep mode v44 consumes the eligible hypotheses itself.
        # v52 only adds this post-primary disposition step to ordinary diff mode.
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
