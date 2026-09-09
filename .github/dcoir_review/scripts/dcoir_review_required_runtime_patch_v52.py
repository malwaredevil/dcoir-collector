"""DCOIR Review v52 bounded structured-result recovery execution policy.

v52 keeps Architecture-B semantic and publication gates intact while avoiding two
avoidable broad replay classes observed in production:

* provider content that contains exactly one intact JSON object surrounded by
  incidental text; and
* otherwise actionable/anchored findings just below the publication threshold.

The provider hook preserves v48 exact-scope authorization. Low-confidence
findings are never published directly: eligible hypotheses receive bounded
independent challenger/adjudicator disposition and then continue through the
existing verifier-authoritative publication path. Any ambiguous scope or
existing fail-closed condition falls back to the historical broad quality retry.
"""

from __future__ import annotations

import copy
import json as _stdlib_json
import math
import types
from typing import Any

import dcoir_review_required_runtime_patch_v44_execution as v44_execution
import dcoir_review_required_runtime_patch_v44_scope as v44_scope
import dcoir_review_required_runtime_patch_v48_core as v48_core

VERSION = "v52"
APPLIED_MARKER = "_dcoir_review_v52_applied"
ALLOW_ATTR = "_dcoir_v52_allow_low_confidence_disposition"
PENDING_ATTR = "_dcoir_v52_pending_low_confidence_disposition"
RECOVERY_ATTR = "_dcoir_v52_last_structured_output_recovery"
_PROVIDER_STORAGE = "_dcoir_review_v52_prior_openrouter_request_once"
_REVIEW_STORAGE = "_dcoir_review_v52_prior_openrouter_review"
_RETRY_STORAGE = "_dcoir_review_v52_prior_quality_retry_reason"
_HYBRID_STORAGE = "_dcoir_review_v52_prior_hybrid_first_pass"
_V48_PROVIDER_STORAGE = "_dcoir_review_v48_original_openrouter_request_once"
_LOW_CONFIDENCE_PREFIX = "model returned structured findings, but none met the configured minimum confidence"


def _balanced_object_ranges(text: str) -> list[tuple[int, int]]:
    """Return top-level brace ranges while respecting JSON strings/escapes."""
    ranges: list[tuple[int, int]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}":
            if depth <= 0:
                return []
            depth -= 1
            if depth == 0:
                ranges.append((start, index + 1))
                start = -1
    if depth != 0 or in_string:
        return []
    return ranges


class _RecoveryJsonProxy:
    """Delegate stdlib json while conservatively recovering one object envelope."""

    def __init__(self, real_json: Any) -> None:
        self._json = real_json
        self.structured_mode = ""
        self._saw_fenced_failure = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._json, name)

    def loads(self, value: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            parsed = self._json.loads(value, *args, **kwargs)
        except self._json.JSONDecodeError as original_error:
            if not isinstance(value, str):
                raise
            # Preserve the pre-v52 fenced-object path in part_04a_provider.py.
            # Its second json.loads() call is labelled below after that path has
            # extracted the exact fenced object.
            if "```" in value:
                self._saw_fenced_failure = True
                raise
            ranges = _balanced_object_ranges(value)
            if len(ranges) != 1:
                raise original_error
            start, end = ranges[0]
            try:
                parsed = self._json.loads(value[start:end], *args, **kwargs)
            except self._json.JSONDecodeError:
                raise original_error
            if not isinstance(parsed, dict):
                raise original_error
            self.structured_mode = "balanced-envelope"
            return parsed
        if self._saw_fenced_failure and isinstance(parsed, dict):
            self.structured_mode = "fenced-object"
            self._saw_fenced_failure = False
        return parsed


def _clone_with_json_proxy(function: Any) -> tuple[Any, _RecoveryJsonProxy]:
    real_json = function.__globals__.get("json", _stdlib_json)
    proxy = _RecoveryJsonProxy(real_json)
    namespace = dict(function.__globals__)
    namespace["json"] = proxy
    clone = types.FunctionType(
        function.__code__,
        namespace,
        name=function.__name__,
        argdefs=function.__defaults__,
        closure=function.__closure__,
    )
    clone.__kwdefaults__ = getattr(function, "__kwdefaults__", None)
    return clone, proxy


def _annotate_request_telemetry(config: Any, mode: str) -> None:
    setattr(config, RECOVERY_ATTR, mode)
    history = getattr(config, "_openrouter_request_telemetry_events", None)
    if isinstance(history, list) and history:
        updated = [dict(item) if isinstance(item, dict) else item for item in history]
        if isinstance(updated[-1], dict):
            updated[-1]["structured_output_recovery"] = mode
        setattr(config, "_openrouter_request_telemetry_events", updated)
        last = getattr(config, "_openrouter_last_request_telemetry", None)
        if isinstance(last, dict):
            revised = dict(last)
            revised["structured_output_recovery"] = mode
            revised["request_events"] = [dict(item) if isinstance(item, dict) else item for item in updated]
            setattr(config, "_openrouter_last_request_telemetry", revised)


def _patch_provider(module: Any) -> None:
    hardened = module.hardened
    current = getattr(hardened, "openrouter_request_once", None)
    if not callable(current):
        raise RuntimeError("DCOIR v52 could not locate hardened openrouter_request_once")
    if not hasattr(hardened, _PROVIDER_STORAGE):
        setattr(hardened, _PROVIDER_STORAGE, current)

    core_request = getattr(hardened, _V48_PROVIDER_STORAGE, None)
    if not callable(core_request):
        raise RuntimeError("DCOIR v52 requires the v48 exact-scope provider boundary")

    def openrouter_request_once(prompt, schema, config, ignored_providers, model):
        if v48_core._guard(module) is not None:
            v48_core.assert_current_review_scope(module, f"model request ({model})", config)
            v48_core.authorize_provider_request(module, config)
        clone, proxy = _clone_with_json_proxy(core_request)
        try:
            result = clone(prompt, schema, config, ignored_providers, model)
        except Exception:
            _annotate_request_telemetry(config, "failed")
            raise
        mode = proxy.structured_mode or "direct"
        _annotate_request_telemetry(config, mode)
        if v48_core._guard(module) is not None:
            v48_core.assert_current_review_scope(module, f"model response ({model})", config)
        return result

    hardened.openrouter_request_once = openrouter_request_once
    if hasattr(module, "openrouter_request_once"):
        module.openrouter_request_once = openrouter_request_once

    current_review = getattr(hardened, "openrouter_review", None)
    if not callable(current_review):
        raise RuntimeError("DCOIR v52 could not locate hardened openrouter_review")
    if not hasattr(hardened, _REVIEW_STORAGE):
        setattr(hardened, _REVIEW_STORAGE, current_review)

    def openrouter_review(prompt, schema, config, reporter=None):
        setattr(config, RECOVERY_ATTR, "")
        result = current_review(prompt, schema, config, reporter)
        mode = str(getattr(config, RECOVERY_ATTR, "") or "")
        if reporter and mode not in {"", "direct"}:
            reporter.update(
                "structured-output-recovery",
                f"mode={mode}; deterministic envelope recovery avoided semantic replay",
            )
        return result

    hardened.openrouter_review = openrouter_review
    if hasattr(module, "openrouter_review"):
        module.openrouter_review = openrouter_review


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and 0.0 <= parsed <= 1.0 else None


def _eligible_low_confidence_findings(
    module: Any,
    result: dict[str, Any],
    config: Any,
    risk_sentinels: list[Any],
    line_index: dict[tuple[str, int], int] | None,
) -> tuple[list[dict[str, Any]], float]:
    if not bool(getattr(config, ALLOW_ATTR, False)) or line_index is None:
        return [], 0.0
    try:
        if module.hardened.required_risk_sentinels(risk_sentinels):
            return [], 0.0
    except Exception:
        return [], 0.0
    minimum = _confidence(getattr(config, "minimum_confidence", 0.70))
    margin = _confidence(getattr(config, "candidate_escalation_confidence_margin", 0.10))
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
        confidence = _confidence(item.get("confidence"))
        try:
            path = str(item.get("path", "") or "").strip()
            line = int(item.get("line", 0) or 0)
        except (TypeError, ValueError):
            return [], floor
        if (
            confidence is None
            or confidence < floor
            or confidence >= minimum
            or not path
            or line <= 0
            or (path, line) not in line_index
        ):
            return [], floor
        eligible.append(item)
    return eligible, floor


def _patch_quality_retry_reason(module: Any) -> None:
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
        eligible, floor = _eligible_low_confidence_findings(
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


def _outside_paths(module: Any, result: dict[str, Any], selected_paths: set[str]) -> bool:
    return any(
        isinstance(item, dict)
        and str(item.get("path", "") or "").strip() not in selected_paths
        for item in module.hardened.result_findings(result)
    )


def _broad_retry_fallback(
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
        f"{module.hardened.sanitize_github_output(reason, config)}; bounded disposition unavailable ({fallback_reason}); retrying with whole-PR repair prompt",
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
        {"fallback_reason": fallback_reason, "model_used": model, "service_tier": tier, "result": merged},
    )
    return merged, model, tier


def _bounded_low_confidence_disposition(
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
    max_paths = max(1, int(getattr(config, "candidate_escalation_max_paths", 4) or 4))
    if not selected_paths or len(selected_paths) > max_paths:
        return _broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")), "path-budget"
        )
    evidence, evidence_reason = v44_scope.build_bounded_evidence(
        module, gh, pr, files, config, risk_sentinels, selected_paths
    )
    if evidence is None:
        return _broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")),
            evidence_reason or "bounded-evidence-unavailable"
        )

    reporter.update(
        "structured-low-confidence-disposition",
        f"candidates={len(findings)}; paths={len(selected_paths)}; floor={float(pending.get('candidate_floor', 0.0)):.2f}; scope=candidate-scoped",
    )
    challenger, challenger_model, challenger_tier = v44_execution.run_challenger(
        module, schema, config, reporter, evidence, "candidate-scoped"
    )
    if _outside_paths(module, challenger, selected_paths):
        return _broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")), "challenger-outside-bounded-scope"
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
    if _outside_paths(module, adjudicated, selected_paths):
        return _broad_retry_fallback(
            module, primary, pr, files, diff, schema, config, reporter,
            risk_sentinels, line_index, deep_context_block, review_mode,
            context_summary, str(pending.get("reason", "")), "adjudicator-outside-bounded-scope"
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


def _patch_hybrid(module: Any) -> None:
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
                pr, files, diff, schema, config, reporter, risk_sentinels,
                line_index, deep_context_block, review_mode, context_summary, gh
            )
        finally:
            setattr(config, ALLOW_ATTR, False)
        pending = getattr(config, PENDING_ATTR, None)
        if review_mode != "diff" or not isinstance(pending, dict):
            return result, model, tier
        return _bounded_low_confidence_disposition(
            module, result, model, tier, pr, files, diff, schema, config,
            reporter, risk_sentinels, line_index, deep_context_block,
            review_mode, context_summary, gh, pending
        )

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_provider(module)
    _patch_quality_retry_reason(module)
    _patch_hybrid(module)
    setattr(module, APPLIED_MARKER, True)
