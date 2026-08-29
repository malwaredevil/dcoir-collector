#!/usr/bin/env python3
"""Regression checks for DCOIR Review v29 critic routing."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v29" in names
    assert names[-1] == "dcoir_review_required_runtime_patch_v28", names[-3:]
    assert names.index("dcoir_review_required_runtime_patch_v29") < names.index("dcoir_review_required_runtime_patch_v28")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v29 = importlib.import_module("dcoir_review_required_runtime_patch_v29")

    base_config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    original_stack = list(base_config.model_stack)
    critic = v25._independent_config(base_config)

    assert base_config.model_stack == original_stack, "critic config mutated shared production config"
    assert critic is not base_config
    assert critic.model == v29.PRIMARY_CRITIC_MODEL
    assert critic.model_stack == [v29.PRIMARY_CRITIC_MODEL, v29.FALLBACK_CRITIC_MODEL]
    assert critic.fallback_models == []
    assert critic.openrouter_route == ""
    assert critic.openrouter_service_tier == ""
    assert critic.openrouter_session_id_prefix.endswith("-repair-critic")

    payload = review.hardened.build_openrouter_payload(
        "critic probe",
        v25.REPAIR_CRITIC_SCHEMA,
        critic,
        [],
        critic.model_stack[0],
    )
    assert payload["model"] == v29.PRIMARY_CRITIC_MODEL
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["provider"]["require_parameters"] is True
    assert "plugins" not in payload, "direct critic unexpectedly received Auto/Pareto router plugin"
    assert "models" not in payload, "critic should use explicit sequential model_stack fallback"

    print("dcoir_review_required_runtime_patch_v29_selftest passed")


if __name__ == "__main__":
    main()
