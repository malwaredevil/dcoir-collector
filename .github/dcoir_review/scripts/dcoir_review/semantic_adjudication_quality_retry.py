"""Single bounded post-adjudication repair without relaxing publication gates."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review import semantic_adjudication_confidence as confidence_policy
from dcoir_review import semantic_adjudication_normalization as normalization

# Explicit marker on the retry provider config. The final-adjudication policy
# reads it to inject the publication floor, label telemetry, and choose the
# projected prompt artifact path.
FINAL_ADJUDICATION_RETRY_ATTR = "_semantic_adjudication_quality_retry_call"
PROJECTED_PROMPT_ARTIFACT_PATH = (
    "prompts/07-semantic-adjudication-quality-retry-projected-prompt.txt"
)

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
    "_quality_retry_provider_result_keys",
    "_quality_retry_model",
}


def valid_retry_summary(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(character.isprintable() or character.isspace() for character in value)
    )


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
    if not isinstance(result.get("_quality_retry_initial_summary"), str):
        return False
    if not valid_retry_summary(result.get("_quality_retry_retry_summary")):
        return False
    if not str(result.get("_quality_retry_initial_raw_digest", "") or "").strip():
        return False
    provider_keys = result.get("_quality_retry_provider_result_keys")
    if not isinstance(provider_keys, (list, tuple)) or any(
        not isinstance(key, str) for key in provider_keys
    ):
        return False
    if not str(result.get("_quality_retry_model", "") or "").strip():
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
    """Validate every first-pass finding before the retry can filter it.

    The retry merge drops first-pass findings that fail its publication
    contract, so a malformed one would vanish behind a clean retry. Run the
    canonical confidence policy over the whole result first: invalid provided
    confidence and partial missing-confidence findings fail closed, while
    complete missing-confidence findings are admitted at the configured floor.
    """

    candidate = dict(result)
    candidate["_semantic_adjudication_attempted"] = True
    normalized, count, _floor = confidence_policy._normalize_semantic_adjudication_confidence(
        module, candidate, config
    )
    if not count:
        return result
    normalized_result = dict(result)
    normalized_result["findings"] = normalized["findings"]
    normalized_result[confidence_policy.NORMALIZATION_MARKER] = (
        confidence_policy.NORMALIZATION_VALUE
    )
    normalized_result[confidence_policy.NORMALIZATION_COUNT] = count
    return normalized_result


def _retry_reason(
    module: Any, reason_fn: Any, result: dict[str, Any], config: Any,
    risk_sentinels: Any, line_index: Any,
) -> str:
    """Ask the quality predicate for a retry reason without disposition side effects.

    The quality-gate predicate also plans the diff-mode bounded low-confidence
    disposition on ``config``. That state belongs to the first-pass gate and
    is read by the outermost disposition stage, so this final-stage check must
    neither overwrite it nor divert final findings away from this retry.
    """

    # Imported lazily: the disposition module imports candidate escalation,
    # which imports semantic adjudication, which imports this module.
    from dcoir_review import structured_result_disposition as disposition

    saved_pending = getattr(config, disposition.PENDING_ATTR, None)
    saved_allow = getattr(config, disposition.ALLOW_ATTR, False)
    setattr(config, disposition.ALLOW_ATTR, False)
    try:
        return str(reason_fn(result, config, risk_sentinels, line_index) or "")
    finally:
        setattr(config, disposition.ALLOW_ATTR, saved_allow)
        setattr(config, disposition.PENDING_ATTR, saved_pending)


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
    # Validate and floor-admit first: complete missing-confidence findings
    # are publishable candidates for the verifier and must not spend a retry.
    merge_initial = _normalize_retry_initial_confidence(module, adjudicated, config)
    reason = _retry_reason(
        module, reason_fn, merge_initial, config, risk_sentinels, line_index
    )
    if not reason:
        return adjudicated, None, None
    if reporter:
        safe_reason = module.hardened.sanitize_github_output(reason, config)
        reporter.update(
            "semantic-adjudication-quality-retry",
            f"{safe_reason}; requesting one evidence-backed final-adjudication repair",
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
    retry_config = copy.copy(adjudication_config)
    setattr(retry_config, FINAL_ADJUDICATION_RETRY_ATTR, True)
    retry_result, retry_model, retry_tier = module.hardened.openrouter_review(
        retry_prompt, schema, retry_config, reporter
    )
    retry_provider_keys = (
        sorted(str(key) for key in retry_result) if isinstance(retry_result, dict) else []
    )
    # Normalize first: a complete flat single finding is an accepted
    # adjudicator shape and carries no summary. Canonical envelopes must still
    # supply a valid summary; a flat retry leaves the retry summary empty, so
    # terminal clean disposition stays unavailable and fails closed.
    retry_result = normalize_result(module, retry_result)
    if normalization.FLAT_SHAPE_MARKER not in retry_result and not valid_retry_summary(
        retry_result.get("summary")
    ):
        raise module.hardened.ReviewQualityError(
            "DCOIR semantic-adjudication retry returned a missing or invalid summary"
        )
    retry_findings = retry_result.get("findings")
    if not isinstance(retry_findings, list) or any(
        not isinstance(finding, dict) for finding in retry_findings
    ):
        raise module.hardened.ReviewQualityError(
            "DCOIR semantic-adjudication retry returned missing or invalid findings"
        )
    module.hardened.write_debug_json_artifact_safely(
        config,
        "responses/07-semantic-adjudication-quality-retry-result.json",
        {"model_used": retry_model, "service_tier": retry_tier, "result": retry_result},
    )
    raw_initial_digest = None
    if merge_initial is not adjudicated:
        digest_fn = getattr(module.hardened, "raw_findings_digest", None)
        if not callable(digest_fn):
            raise RuntimeError(
                "DCOIR semantic-adjudication retry could not preserve the raw initial finding digest"
            )
        raw_initial_digest = digest_fn(adjudicated)
    merged = module.hardened.merge_quality_retry_results(
        initial_result=merge_initial,
        retry_result=retry_result,
        config=config,
        line_index=line_index,
        retry_reason=reason,
    )
    if raw_initial_digest is not None:
        merged["_quality_retry_initial_raw_digest"] = raw_initial_digest
        merged[confidence_policy.NORMALIZATION_MARKER] = (
            confidence_policy.NORMALIZATION_VALUE
        )
        merged[confidence_policy.NORMALIZATION_COUNT] = merge_initial[
            confidence_policy.NORMALIZATION_COUNT
        ]
    merged["_quality_retry_provider_result_keys"] = retry_provider_keys
    merged["_quality_retry_model"] = str(retry_model or "")
    capped = cap_findings(module, merged, max_findings)
    # Never lose the original overflow signal during retry-result merging:
    # the terminal low-confidence disposition must remain fail-closed.
    overflow_key = "_semantic_adjudication_overflow_trimmed"
    if overflow_key in adjudicated:
        capped[overflow_key] = max(
            adjudicated[overflow_key], capped.get(overflow_key, 0)
        )
    return capped, retry_model, retry_tier
