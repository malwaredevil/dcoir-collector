#!/usr/bin/env python3
"""Production-composition regressions for DCOIR Review v57 selftest."""

from __future__ import annotations

import importlib
from typing import Any, Callable

import dcoir_review_required_runtime_patch_v57 as v57


def run_production_regressions(
    entrypoint: Any,
    adjudicated_result: Callable[..., dict[str, Any]],
    finding: Callable[..., dict[str, Any]],
) -> None:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    assert getattr(review, v57.APPLIED_MARKER, False) is True
    prod_config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert round(float(prod_config.minimum_confidence), 2) == 0.70
    assert review.hardened.summary_suggests_problem(v57.CLEAN_SUMMARY) is False

    production_live_shape = adjudicated_result(
        [
            finding(".github/AGENTS.md", 22, 0.60),
            finding("AGENTS.md", 248, 0.50),
            finding(".github/agent-governance/codex_cloud_environment.md", 77, 0.45),
        ],
        v57.CLEAN_SUMMARY,
    )
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
    assert production_live_shape["summary"] == v57.CLEAN_SUMMARY
    assert production_live_shape[v57.DISPOSITION_MARKER]["candidate_count"] == 3

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
        v57.CLEAN_SUMMARY,
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
