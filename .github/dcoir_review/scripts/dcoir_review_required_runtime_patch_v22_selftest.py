#!/usr/bin/env python3
"""Production-stack regression for DCOIR Review v22 semantic summary recovery."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PROBE_PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"
PROBE_LINE = 12
LIVE_SUMMARY = (
    "Identified a correctness bug in is_recent where the upper boundary condition is inverted, "
    "causing values between 0 and 59 to return False instead of True."
)
EXPECTED_RETRY_REASON = "model summary indicated a possible issue while the structured findings array was empty"


def main() -> None:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    assert review.hardened.summary_suggests_problem(LIVE_SUMMARY)
    assert review.hardened.review_quality_retry_reason(
        {"summary": LIVE_SUMMARY, "findings": []},
        config,
        [],
        {(PROBE_PATH, PROBE_LINE): 1},
    ) == EXPECTED_RETRY_REASON

    for positive_summary in (
        "Found a semantic defect in the changed boundary check.",
        "Detected a vulnerability in the changed authorization branch.",
        "Observed a correctness bug in the new comparison.",
    ):
        assert review.hardened.summary_suggests_problem(positive_summary), positive_summary

    for clean_summary in (
        "No bugs were found in the changed diff.",
        "Found no defects in the changed code.",
        "No vulnerabilities were identified.",
        "This behavior is not a bug and requires no code change.",
        "Bug fixes were applied; no actionable findings were found.",
    ):
        assert not review.hardened.summary_suggests_problem(clean_summary), clean_summary

    print("dcoir_review_required_runtime_patch_v22_selftest passed")


if __name__ == "__main__":
    main()
