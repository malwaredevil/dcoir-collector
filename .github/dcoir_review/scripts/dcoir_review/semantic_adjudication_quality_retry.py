"""Single bounded post-adjudication repair without relaxing publication gates."""

from __future__ import annotations

from typing import Any


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
    retry_result, retry_model, retry_tier = module.hardened.openrouter_review(
        retry_prompt, schema, adjudication_config, reporter
    )
    retry_result = normalize_result(module, retry_result)
    module.hardened.write_debug_json_artifact_safely(
        config,
        "responses/07-semantic-adjudication-quality-retry-result.json",
        {"model_used": retry_model, "service_tier": retry_tier, "result": retry_result},
    )
    merged = module.hardened.merge_quality_retry_results(
        initial_result=adjudicated,
        retry_result=retry_result,
        config=config,
        line_index=line_index,
        retry_reason=reason,
    )
    return cap_findings(module, merged, max_findings), retry_model, retry_tier
