#!/usr/bin/env python3
"""Regression checks for DCOIR Review v26 immutable model anchors."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"


def patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def test_no_sentinel_selection_is_identity(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = {
        "title": "Upper-bound comparison is inverted",
        "severity": "high",
        "confidence": 1.0,
        "path": PATH,
        "line": 12,
        "body": "The expression requires age_minutes >= 60 where the local contract requires an inclusive upper bound of 60.",
        "suggested_replacement": "",
    }
    selected = review.hardened.add_risk_sentinel_fallback_findings([finding], [], config, [])
    assert len(selected) == 1, selected
    assert selected[0] == finding, selected
    assert selected[0]["line"] == 12
    assert selected[0]["title"] == "Upper-bound comparison is inverted"


def test_no_sentinel_selection_preserves_multiple_model_sites(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    findings = [
        {
            "title": "First ordinary finding",
            "severity": "medium",
            "confidence": 0.95,
            "path": "probe.py",
            "line": 4,
            "body": "First exact changed-line issue.",
        },
        {
            "title": "Second ordinary finding",
            "severity": "medium",
            "confidence": 0.94,
            "path": "probe.py",
            "line": 9,
            "body": "Second exact changed-line issue.",
        },
    ]
    selected = review.hardened.add_risk_sentinel_fallback_findings(findings, [], config, [])
    assert [(item["path"], item["line"]) for item in selected] == [("probe.py", 4), ("probe.py", 9)]
    assert [item["title"] for item in selected] == ["First ordinary finding", "Second ordinary finding"]


def main() -> None:
    review = patched_review()
    test_no_sentinel_selection_is_identity(review)
    test_no_sentinel_selection_preserves_multiple_model_sites(review)
    print("dcoir_review_required_runtime_patch_v26_selftest passed")


if __name__ == "__main__":
    main()
