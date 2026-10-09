#!/usr/bin/env python3
"""Production-composition regressions for stable final-adjudication policy."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import final_adjudication_policy as final_policy


def run_production_regressions(
    entrypoint: Any,
    adjudicated_result: Callable[..., dict[str, Any]],
    finding: Callable[..., dict[str, Any]],
) -> None:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    final_policy.apply_pareto_context_module(review)
    assert getattr(review, final_policy.APPLIED_MARKER, False) is True
    prod_config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert round(float(prod_config.minimum_confidence), 2) == 0.70
    assert review.hardened.summary_suggests_problem(final_policy.CLEAN_SUMMARY) is False

    production_live_shape = adjudicated_result(
        [
            finding(".github/AGENTS.md", 22, 0.60),
            finding("AGENTS.md", 248, 0.50),
            finding(".github/agent-governance/codex_cloud_environment.md", 77, 0.45),
        ],
        final_policy.CLEAN_SUMMARY,
    )
    production_live_shape["_candidate_escalation"] = {"mode": "full-deep"}
    production_live_shape["_semantic_context_package_id"] = "package-123"
    production_live_shape["_adaptive_semantic_budget_mode"] = "full-deep"
    assert review.split_findings_with_review_body_fallback(
        production_live_shape,
        prod_config,
        {
            (".github/AGENTS.md", 22): 1,
            ("AGENTS.md", 248): 2,
            (".github/agent-governance/codex_cloud_environment.md", 77): 3,
        },
        "+governance",
        [],
    ) == ([], [])
    assert production_live_shape["summary"] == final_policy.CLEAN_SUMMARY
    assert production_live_shape[final_policy.DISPOSITION_MARKER]["candidate_count"] == 3

    retried_low_confidence = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        final_policy.CLEAN_SUMMARY,
    )
    retried_low_confidence.update(
        {
            "_quality_retry_attempted": True,
            "_quality_retry_reason": "none met the configured confidence floor",
            "_quality_retry_initial_summary": "First adjudication candidate.",
            "_quality_retry_retry_summary": final_policy.CLEAN_SUMMARY,
            "_quality_retry_merge_contract": "filtered-initial-v1",
            "_quality_retry_initial_finding_count": 1,
            "_quality_retry_initial_survivor_count": 0,
            "_quality_retry_initial_rejected_count": 1,
            "_quality_retry_retry_finding_count": 1,
            "_quality_retry_initial_raw_digest": "AGENTS.md:248 confidence 0.55 (Candidate)",
        }
    )
    assert review.split_findings_with_review_body_fallback(
        retried_low_confidence,
        prod_config,
        {("AGENTS.md", 248): 1},
        "+governance",
        [],
    ) == ([], [])
    assert retried_low_confidence[final_policy.DISPOSITION_MARKER]["candidate_count"] == 1

    incomplete_retry_metadata = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        final_policy.CLEAN_SUMMARY,
    )
    incomplete_retry_metadata["_quality_retry_attempted"] = True
    try:
        review.split_findings_with_review_body_fallback(
            incomplete_retry_metadata,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("terminal disposition accepted incomplete final-retry metadata")

    production_problem_summary = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        "A correctness issue remains after semantic adjudication.",
    )
    try:
        review.split_findings_with_review_body_fallback(
            production_problem_summary,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path bypassed the summary-only problem fail-closed gate")

    production_overflow = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        final_policy.CLEAN_SUMMARY,
    )
    production_overflow["_semantic_adjudication_overflow_trimmed"] = 1
    try:
        review.split_findings_with_review_body_fallback(
            production_overflow,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path converted overflow-trimmed adjudication to clean")

    production_early = {
        "summary": "Possible weak first-pass concern.",
        "findings": [finding("AGENTS.md", 248, 0.55)],
        "_quality_retry_attempted": True,
    }
    try:
        review.split_findings_with_review_body_fallback(
            production_early,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path weakened #430 earlier-stage fail-closed behavior")

    spoofed_metadata = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        final_policy.CLEAN_SUMMARY,
    )
    spoofed_metadata[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR] = "spoofed"
    try:
        review.split_findings_with_review_body_fallback(
            spoofed_metadata,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path accepted spoofed semantic adjudication provenance")

    spoofed_provider_marker = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        final_policy.CLEAN_SUMMARY,
        provider_result_keys=("summary", "findings", "_semantic_adjudication_result_shape"),
    )
    spoofed_provider_marker["_semantic_adjudication_result_shape"] = "flat-single-finding"
    try:
        review.split_findings_with_review_body_fallback(
            spoofed_provider_marker,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path accepted provider-spoofed envelope metadata")
