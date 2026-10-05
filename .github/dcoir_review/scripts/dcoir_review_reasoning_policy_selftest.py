#!/usr/bin/env python3
"""Regression checks for canonical DCOIR Review reasoning payload policy."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from dcoir_review import reasoning_policy
from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v32" not in entrypoint.patch_module_names

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    }

    assert reasoning_policy.model_owns_fixed_pro_reasoning("openai/gpt-5.6-sol-pro") is True
    assert reasoning_policy.model_owns_fixed_pro_reasoning("openai/gpt-5.6-sol-pro-20260709") is True
    assert reasoning_policy.model_owns_fixed_pro_reasoning("openai/gpt-5.6-sol") is False
    assert reasoning_policy.model_uses_openai_gpt5_reasoning("openai/gpt-5.6-sol") is True
    assert reasoning_policy.model_uses_openai_gpt5_reasoning("openai/gpt-4.1") is False
    assert reasoning_policy.model_uses_anthropic_adaptive_reasoning("anthropic/claude-opus-5.5") is True
    assert reasoning_policy.model_uses_anthropic_adaptive_reasoning("anthropic/claude-sonnet-5.5") is True

    opus = review.hardened.build_openrouter_payload("probe", schema, config, [], "anthropic/claude-opus-5.5")
    assert "temperature" not in opus
    assert opus["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}

    pro = review.hardened.build_openrouter_payload("probe", schema, config, [], "openai/gpt-5.6-sol-pro")
    assert "temperature" not in pro
    assert "reasoning" not in pro
    assert pro["provider"]["require_parameters"] is True

    regular = review.hardened.build_openrouter_payload("probe", schema, config, [], "openai/gpt-5.6-sol")
    assert "temperature" not in regular
    assert regular["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}

    legacy = review.hardened.build_openrouter_payload("probe", schema, config, [], "openai/gpt-4.1")
    assert legacy["temperature"] == 0.2
    assert legacy["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}

    repair_projection = SimpleNamespace(
        review_reasoning_effort="xhigh",
        dcoir_reasoning_effort_by_model={"anthropic/claude-sonnet-5.5": "high"},
    )
    direct = reasoning_policy.apply_reasoning_payload_policy(
        {"temperature": 0.2}, repair_projection, "anthropic/claude-sonnet-5.5"
    )
    assert "temperature" not in direct
    assert direct["reasoning"] == {"enabled": True, "effort": "high", "exclude": True}

    disabled_reasoning = SimpleNamespace(review_reasoning_effort="none")
    unchanged = reasoning_policy.apply_reasoning_payload_policy(
        {"temperature": 0.2}, disabled_reasoning, "anthropic/claude-sonnet-5.5"
    )
    assert unchanged == {"temperature": 0.2}

    print("dcoir_review_reasoning_policy_selftest passed")


if __name__ == "__main__":
    main()
