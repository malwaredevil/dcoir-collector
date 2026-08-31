#!/usr/bin/env python3
"""Regression checks for DCOIR Review v32 adversarial semantic recall."""

from __future__ import annotations

import importlib
from pathlib import Path

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v32" in entrypoint.patch_module_names
    assert entrypoint.patch_module_names[-1] == "dcoir_review_required_runtime_patch_v31"
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v32") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v32 = importlib.import_module("dcoir_review_required_runtime_patch_v32")

    assert getattr(review, v32.APPLIED_MARKER, False) is True
    for required_phrase in (
        "minimal counterexamples",
        "semantic scope binding",
        "assertion polarity",
        "representation variants",
        "helper consistency",
        "passing tests as evidence, not proof",
    ):
        assert required_phrase in v32.ADVERSARIAL_SEMANTIC_BLOCK

    system_prompt = Path(".github/dcoir_review/prompts/openrouter-pr-review-system.md").read_text(encoding="utf-8")
    assert "adversarial" in system_prompt.lower()
    assert "counterexample" in system_prompt.lower()
    assert "scope binding" in system_prompt.lower()

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.model_stack[0] == "anthropic/claude-opus-5"
    assert "openai/gpt-5.6-sol-pro" in config.model_stack
    assert config.per_file_review_max_files >= config.max_files
    assert config.max_files >= 100
    assert config.adversarial_confirmation_review is True
    assert config.adversarial_confirmation_model_stack == ["openai/gpt-5.6-sol-pro"]
    assert config.review_reasoning_effort == "xhigh"

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    }
    payload = review.hardened.build_openrouter_payload(
        "probe",
        schema,
        config,
        [],
        config.model_stack[0],
    )
    assert payload["model"] == "anthropic/claude-opus-5"
    assert payload["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}

    # OpenRouter's OpenAI *-pro SKUs already encode reasoning.mode=pro.  The
    # reviewer must not add a second effort selector that can make the provider
    # endpoint ineligible, while normal OpenAI SKUs still receive the governed
    # explicit reasoning effort.
    assert v32._model_owns_fixed_pro_reasoning("openai/gpt-5.6-sol-pro") is True
    assert v32._model_owns_fixed_pro_reasoning("openai/gpt-5.6-sol-pro-20260709") is True
    assert v32._model_owns_fixed_pro_reasoning("openai/gpt-5.6-sol") is False
    assert v32._model_owns_fixed_pro_reasoning("anthropic/claude-opus-5") is False

    pro_payload = review.hardened.build_openrouter_payload(
        "probe",
        schema,
        config,
        [],
        "openai/gpt-5.6-sol-pro",
    )
    assert pro_payload["model"] == "openai/gpt-5.6-sol-pro"
    assert "reasoning" not in pro_payload

    regular_openai_payload = review.hardened.build_openrouter_payload(
        "probe",
        schema,
        config,
        [],
        "openai/gpt-5.6-sol",
    )
    assert regular_openai_payload["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}

    # Prove that a clean primary pass cannot become the final deep result without
    # an independent challenger and that challenger findings are preserved.
    storage = "_dcoir_review_v32_original_hybrid_first_pass"
    original_first_pass = getattr(review, storage)
    original_build_prompt = review.build_prompt
    original_openrouter_review = review.hardened.openrouter_review
    original_write_text = review.hardened.write_debug_text_artifact_safely
    original_write_json = review.hardened.write_debug_json_artifact_safely
    observed: dict[str, object] = {}

    def fake_first_pass(*args, **kwargs):
        return {"summary": "Primary detector found nothing actionable.", "findings": []}, "primary-test", "tier-primary"

    def fake_build_prompt(*args, **kwargs):
        return "aggregate PR context"

    def fake_openrouter_review(prompt, schema_arg, config_arg, reporter):
        observed["prompt"] = prompt
        observed["models"] = list(config_arg.model_stack)
        return (
            {
                "summary": "Independent challenger found a semantic bypass.",
                "findings": [
                    {
                        "title": "Scope binding bypass",
                        "severity": "medium",
                        "confidence": 0.93,
                        "path": "probe.py",
                        "line": 10,
                        "body": "Required evidence can be supplied in the wrong semantic lane.",
                        "suggested_replacement": "",
                        "validation": "Run focused regression.",
                    }
                ],
            },
            "openai/gpt-5.6-sol-pro",
            "tier-confirmation",
        )

    try:
        setattr(review, storage, fake_first_pass)
        review.build_prompt = fake_build_prompt
        review.hardened.openrouter_review = fake_openrouter_review
        review.hardened.write_debug_text_artifact_safely = lambda *args, **kwargs: None
        review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
        result, model_used, service_tier = review.openrouter_review_with_hybrid_first_pass(
            {},
            [],
            "",
            schema,
            config,
            None,
            [],
            {},
            "",
            "deep-forced",
            "",
            None,
        )
    finally:
        setattr(review, storage, original_first_pass)
        review.build_prompt = original_build_prompt
        review.hardened.openrouter_review = original_openrouter_review
        review.hardened.write_debug_text_artifact_safely = original_write_text
        review.hardened.write_debug_json_artifact_safely = original_write_json

    assert observed["models"] == ["openai/gpt-5.6-sol-pro"]
    assert "Independent adversarial confirmation pass" in str(observed["prompt"])
    assert len(result.get("findings", [])) == 1
    assert result.get("_adversarial_confirmation_attempted") is True
    assert result.get("_adversarial_confirmation_model") == "openai/gpt-5.6-sol-pro"
    assert "primary-test" in model_used and "openai/gpt-5.6-sol-pro" in model_used
    assert "tier-primary" in service_tier and "tier-confirmation" in service_tier

    hybrid_before = review.openrouter_review_with_hybrid_first_pass
    payload_before = review.hardened.build_openrouter_payload
    prompt_before = review.build_per_file_review_prompt
    v32.apply_pareto_context_module(review)
    v32.apply_pareto_context_module(review)
    assert review.openrouter_review_with_hybrid_first_pass is hybrid_before
    assert review.hardened.build_openrouter_payload is payload_before
    assert review.build_per_file_review_prompt is prompt_before

    print("dcoir_review_required_runtime_patch_v32_selftest passed")


if __name__ == "__main__":
    main()
