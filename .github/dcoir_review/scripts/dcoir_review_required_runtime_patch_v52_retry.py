"""Fail-closed broad quality-retry fallback for DCOIR Review v52."""

from __future__ import annotations

from typing import Any


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
    """Preserve the historical whole-PR retry whenever bounding is unsafe."""
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
    retry_sentinels = (
        module.hardened.required_risk_sentinels(risk_sentinels) or risk_sentinels
    )
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
