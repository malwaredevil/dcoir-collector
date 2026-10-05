"""Canonical independent adversarial-confirmation stage for DCOIR Review.

The challenger remains an explicit hybrid-review stage, but its ownership no
longer depends on the historical v32 runtime module. Prompt policy, model-stack
selection, artifacts, and fail-closed execution are composed here directly.
"""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review import adversarial_prompt_policy as prompt_policy
from dcoir_review import review_config


DEFAULT_CONFIRMATION_MODELS = review_config.DEFAULT_CONFIRMATION_MODELS
INDEPENDENT_CONFIRMATION_BLOCK = prompt_policy.INDEPENDENT_CONFIRMATION_BLOCK


def confirmation_models(config: Any) -> list[str]:
    value = getattr(config, "adversarial_confirmation_model_stack", None)
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(DEFAULT_CONFIRMATION_MODELS)


def build_adversarial_confirmation_stage(module: Any, next_review: Any) -> Any:
    """Compose the independent challenger around the preceding review stage."""

    original = next_review
    if not callable(original):
        raise RuntimeError("DCOIR adversarial confirmation requires a callable hybrid review stage")

    def adversarial_confirmation_stage(
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
        first_result, first_model, first_tier = original(
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

        enabled = bool(getattr(config, "adversarial_confirmation_review", True))
        if not enabled or review_mode not in {"first-pass-deep", "deep-forced"}:
            return first_result, first_model, first_tier

        confirmation_config = copy.copy(config)
        models = confirmation_models(config)
        confirmation_config.model_stack = models
        confirmation_config.model = models[0]

        aggregate_prompt = module.build_prompt(
            pr,
            files,
            diff,
            confirmation_config,
            risk_sentinels,
            deep_context_block,
            review_mode,
            context_summary,
        )
        confirmation_prompt = f"{INDEPENDENT_CONFIRMATION_BLOCK}\n\n{aggregate_prompt}"
        max_chars = max(0, int(getattr(confirmation_config, "max_prompt_chars", 120000)))
        marker = "\n\n[independent adversarial confirmation prompt truncated by reviewer]"
        if len(confirmation_prompt) > max_chars:
            if max_chars <= len(marker):
                confirmation_prompt = marker[:max_chars]
            else:
                keep = max_chars - len(marker)
                confirmation_prompt = confirmation_prompt[:keep] + marker

        module.hardened.write_debug_text_artifact_safely(
            confirmation_config,
            "prompts/04-adversarial-confirmation-prompt.txt",
            confirmation_prompt,
        )
        if reporter:
            reporter.update(
                "adversarial-confirmation",
                f"running independent semantic challenger with {models[0]}",
            )

        confirmation_result, confirmation_model, confirmation_tier = module.hardened.openrouter_review(
            confirmation_prompt,
            schema,
            confirmation_config,
            reporter,
        )
        module.hardened.write_debug_json_artifact_safely(
            confirmation_config,
            "responses/04-adversarial-confirmation-result.json",
            {
                "model_used": confirmation_model,
                "service_tier": confirmation_tier,
                "result": confirmation_result,
            },
        )

        merged = module.hardened.merge_review_results(first_result, confirmation_result)
        merged["_adversarial_confirmation_attempted"] = True
        merged["_adversarial_confirmation_model"] = confirmation_model
        merged["_adversarial_confirmation_first_model"] = first_model
        module.hardened.write_debug_json_artifact_safely(
            confirmation_config,
            "responses/05-adversarial-confirmation-merged-result.json",
            {
                "first_model": first_model,
                "confirmation_model": confirmation_model,
                "merged_finding_count": len(module.hardened.result_findings(merged)),
                "result": merged,
            },
        )
        model_label = f"{first_model}; independent-confirmation={confirmation_model}"
        tier_parts = [str(first_tier or "").strip(), str(confirmation_tier or "").strip()]
        tier_label = ", ".join(item for item in tier_parts if item)
        return merged, model_label, tier_label

    return adversarial_confirmation_stage


__all__ = [
    "DEFAULT_CONFIRMATION_MODELS",
    "INDEPENDENT_CONFIRMATION_BLOCK",
    "build_adversarial_confirmation_stage",
    "confirmation_models",
]
