"""Single bounded post-adjudication repair without relaxing publication gates."""

from __future__ import annotations

from typing import Any

from dcoir_review import semantic_adjudication_confidence as confidence_policy


QUALITY_RETRY_RESULT_KEYS = {
    "_quality_retry_attempted",
    "_quality_retry_reason",
    "_quality_retry_initial_summary",
    "_quality_retry_retry_summary",
    "_quality_retry_merge_contract",
    "_quality_retry_initial_finding_count",
    "_quality_retry_initial_survivor_count",
    "_quality_retry_initial_rejected_count",
    "_quality_retry_retry_finding_count",
    "_quality_retry_initial_raw_digest",
}


def quality_retry_metadata_is_valid(result: dict[str, Any]) -> bool:
    present = QUALITY_RETRY_RESULT_KEYS.intersection(result)
    if not present:
        return True
    if present != QUALITY_RETRY_RESULT_KEYS:
        return False
    if result.get("_quality_retry_attempted") is not True:
        return False
    if result.get("_quality_retry_merge_contract") != "filtered-initial-v1":
        return False
    if not str(result.get("_quality_retry_reason", "") or "").strip():
        return False
    if not all(
        isinstance(result.get(key), str)
        for key in ("_quality_retry_initial_summary", "_quality_retry_retry_summary")
    ):
        return False
    if not str(result.get("_quality_retry_initial_raw_digest", "") or "").strip():
        return False

    count_keys = (
        "_quality_retry_initial_finding_count",
        "_quality_retry_initial_survivor_count",
        "_quality_retry_initial_rejected_count",
        "_quality_retry_retry_finding_count",
    )
    counts = [result.get(key) for key in count_keys]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
        return False
    initial_count, survivor_count, rejected_count, _retry_count = counts
    return survivor_count + rejected_count == initial_count


def _normalize_retry_initial_confidence(
    module: Any, result: dict[str, Any], config: Any
) -> dict[str, Any]:
    findings = result.get("findings")
    if not isinstance(findings, list):
        return result

    normalized_findings = list(findings)
    normalized_count = 0
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict) or (
            "confidence" in finding and finding.get("confidence") is not None
        ):
            continue
        candidate = {
            "_semantic_adjudication_attempted": True,
            "findings": [finding],
        }
        try:
            normalized, count, _floor = confidence_policy._normalize_semantic_adjudication_confidence(
                module, candidate, config
            )
        except module.hardened.ReviewQualityError:
            continue
        if count:
            normalized_findings[index] = normalized["findings"][0]
            normalized_count += count

    if not normalized_count:
        return result

    normalized_result = dict(result)
    normalized_result["findings"] = normalized_findings
    normalized_result[confidence_policy.NORMALIZATION_MARKER] = (
        confidence_policy.NORMALIZATION_VALUE
    )
    normalized_result[confidence_policy.NORMALIZATION_COUNT] = normalized_count
    return normalized_result


def retry_rejected_adjudication(
    module: Any, adjudicated: dict[str, Any], config: Any,
    risk_sentinels: Any, line_index: Any, prompt: str, schema: dict[str, Any],
    adjudication_config: Any, reporter: Any, max_findings: int,
    cap_findings: Any, normalize_result: Any,
) -> tuple[dict[str, Any], str | None, str | None]:
    # The earlier quality gate runs before final adjudication, so re-check
    # newly adjudicated findings and grant exactly one bounded repair attempt.
    reason_fn = getattr(module.hardened, "review_quality_retry_reason", None)
    if not callable(reason_fn):
        return adjudicated, None, None
    reason = reason_fn(adjudicated, config, risk_sentinels, line_index)
    if not reason:
        return adjudicated, None, None
    if reporter:
        reporter.update(
            "semantic-adjudication-quality-retry",
            "Final adjudication produced no actionable findings; requesting one evidence-backed repair",
        )
    retry_prompt = module.hardened.build_quality_retry_prompt(
        prompt, adjudicated, risk_sentinels, config, reason
    )
    module.hardened.write_debug_text_artifact_safely(
        config, "prompts/07-semantic-adjudication-quality-retry.txt", retry_prompt
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "responses/07-semantic-adjudication-quality-retry-initial-result.json",
        {"result": adjudicated},
    )
    retry_result, retry_model, retry_tier = module.hardened.openrouter_review(
        retry_prompt, schema, adjudication_config, reporter
    )
    retry_result = normalize_result(module, retry_result)
    module.hardened.write_debug_json_artifact_safely(
        config,
        "responses/07-semantic-adjudication-quality-retry-result.json",
        {"model_used": retry_model, "service_tier": retry_tier, "result": retry_result},
    )
    merge_initial = _normalize_retry_initial_confidence(module, adjudicated, config)
    merged = module.hardened.merge_quality_retry_results(
        initial_result=merge_initial,
        retry_result=retry_result,
        config=config,
        line_index=line_index,
        retry_reason=reason,
    )
    return cap_findings(module, merged, max_findings), retry_model, retry_tier
