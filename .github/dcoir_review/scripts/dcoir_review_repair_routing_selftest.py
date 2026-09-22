#!/usr/bin/env python3
"""Stable contract checks for independent repair-critic routing."""

from __future__ import annotations

import copy
from email.message import Message
import importlib
import io
import json
import urllib.error

from dcoir_review import repair as repair_policy
from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v29" not in names
    assert "dcoir_review_required_runtime_patch_v28" not in names
    assert "dcoir_review_required_runtime_patch_v30" in names
    assert "dcoir_review_required_runtime_patch_v31" in names
    assert names.index("dcoir_review.repair_pipeline") < names.index(
        "dcoir_review_required_runtime_patch_v30"
    )
    assert names.index("dcoir_review_required_runtime_patch_v30") < names.index(
        "dcoir_review_required_runtime_patch_v31"
    )

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    repair_pipeline = importlib.import_module("dcoir_review.repair_pipeline")

    base_config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    original_stack = list(base_config.model_stack)

    contaminated = copy.copy(base_config)
    contaminated.fallback_models = ["legacy/fallback"]
    contaminated.openrouter_route = "auto"
    contaminated.openrouter_service_tier = "priority"
    author_critic = repair_policy.build_repair_critic_config(
        contaminated, "anthropic/claude-opus-5"
    )
    assert author_critic.model == repair_policy.OPENAI_CROSS_FAMILY_CRITIC_MODEL
    assert author_critic.model_stack == [
        repair_policy.OPENAI_CROSS_FAMILY_CRITIC_MODEL,
        repair_policy.OPENAI_CROSS_FAMILY_CRITIC_FALLBACK_MODEL,
    ]
    assert author_critic.fallback_models == []
    assert author_critic.openrouter_route == ""
    assert author_critic.openrouter_service_tier == ""
    assert contaminated.fallback_models == ["legacy/fallback"]
    assert contaminated.openrouter_route == "auto"
    assert contaminated.openrouter_service_tier == "priority"

    # Issue #582 regression: the 2026-09-21 review run showed every Opus 5
    # request falling through while Sol Pro succeeded. A Sol-authored repair
    # must therefore retain an Anthropic-only fallback rather than turning the
    # first non-retryable 404 into a terminal repair-critic failure.
    sol_author_critic = repair_policy.build_repair_critic_config(
        base_config, "openai/gpt-5.6-sol-pro"
    )
    assert sol_author_critic.model_stack == [
        repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL,
        repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL,
    ]
    assert repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL == "anthropic/claude-sonnet-5"
    assert not repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL.startswith("~")
    assert all(
        not str(model).removeprefix("~").startswith("openai/")
        for model in sol_author_critic.model_stack
    )

    attempted_models: list[str] = []
    original_request_once = review.hardened.openrouter_request_once
    empty_headers = Message()

    def fake_repair_critic_request(_prompt, _schema, _config, _ignored, model):
        attempted_models.append(model)
        if model == repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL:
            body = json.dumps(
                {"error": {"message": "No endpoints found that can handle the requested parameters."}}
            ).encode("utf-8")
            raise urllib.error.HTTPError(
                url="https://openrouter.ai/api/v1/chat/completions",
                code=404,
                msg="No endpoints found",
                hdrs=empty_headers,
                fp=io.BytesIO(body),
            )
        return (
            {"accepted": True, "confidence": 0.99, "reason": "fallback critic accepted"},
            model,
            "",
        )

    review.hardened.openrouter_request_once = fake_repair_critic_request
    try:
        regression_result, regression_model, _regression_tier = review.hardened.openrouter_review(
            "critic probe",
            repair_pipeline.REPAIR_CRITIC_SCHEMA,
            sol_author_critic,
            reporter=None,
        )
    finally:
        review.hardened.openrouter_request_once = original_request_once

    assert attempted_models == [
        repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL,
        repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL,
    ]
    assert regression_model == repair_policy.ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL
    assert regression_result["accepted"] is True

    critic = repair_pipeline._independent_config(base_config)

    assert base_config.model_stack == original_stack, (
        "critic config mutated shared production config"
    )
    assert critic is not base_config
    assert critic.model == repair_policy.PRIMARY_CRITIC_MODEL
    assert critic.model_stack == [
        repair_policy.PRIMARY_CRITIC_MODEL,
        repair_policy.FALLBACK_CRITIC_MODEL,
    ]
    assert critic.fallback_models == []
    assert critic.openrouter_route == ""
    assert critic.openrouter_service_tier == ""
    assert critic.openrouter_session_id_prefix.endswith("-repair-critic")

    payload = review.hardened.build_openrouter_payload(
        "critic probe",
        repair_pipeline.REPAIR_CRITIC_SCHEMA,
        critic,
        [],
        critic.model_stack[0],
    )
    assert payload["model"] == repair_policy.PRIMARY_CRITIC_MODEL
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["provider"]["require_parameters"] is True
    assert "plugins" not in payload, (
        "direct critic unexpectedly received Auto/Pareto router plugin"
    )
    assert "models" not in payload, (
        "critic should use explicit sequential model_stack fallback"
    )

    print("dcoir_review_repair_routing_selftest passed")


if __name__ == "__main__":
    main()
