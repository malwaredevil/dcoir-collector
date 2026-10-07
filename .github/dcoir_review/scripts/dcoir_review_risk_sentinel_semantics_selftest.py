#!/usr/bin/env python3
"""Regression checks for stable deterministic risk-sentinel semantics ownership."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    numbered = [name for name in names if name.startswith("dcoir_review_required_runtime_patch_v")]
    assert numbered == [], numbered
    assert "dcoir_review.risk_sentinel_semantics" in names, names
    index = names.index("dcoir_review.risk_sentinel_semantics")
    assert names[index - 1] == "dcoir_review.finding_family", names[max(0, index - 2):index + 3]
    assert names[index + 1] == "dcoir_review.precision_guard", names[max(0, index - 2):index + 3]

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    prefix = names[: index + 1]
    entrypoint.apply_runtime_patches(review, prefix)
    assert getattr(review, "_dcoir_review_risk_sentinel_semantics_applied", False)
    assert callable(review.detect_risk_sentinels)
    assert callable(review.hardened.add_risk_sentinel_fallback_findings)
    assert callable(review.hardened.enforce_risk_sentinel_findings)

    print("dcoir_review_risk_sentinel_semantics_selftest passed")


if __name__ == "__main__":
    main()
