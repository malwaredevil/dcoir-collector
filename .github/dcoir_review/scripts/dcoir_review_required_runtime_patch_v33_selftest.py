#!/usr/bin/env python3
"""Regression checks for DCOIR Review v33 verification/repair budget separation."""

from __future__ import annotations

import importlib
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class _Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v33" in entrypoint.patch_module_names

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review.finding_verifier")
    repair = importlib.import_module("dcoir_review.repair_pipeline")
    repair_policy = importlib.import_module("dcoir_review.repair")
    v33 = importlib.import_module("dcoir_review_required_runtime_patch_v33")

    assert getattr(review, v33.APPLIED_MARKER, False) is True
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    # v33 is now compatibility policy only. Canonical owners hold both limits.
    assert v21.VERIFIER_MAX_MODEL_FINDINGS == 12
    assert repair.MAX_REPAIR_CANDIDATES == 12
    assert v33.verifier_candidate_limit(config) == v21.verifier_candidate_limit(config) == 12
    assert v33.repair_synthesis_budget(config) == repair_policy.repair_synthesis_budget(config) == 12
    assert v21.verify_findings_for_publication.__module__ == "dcoir_review.finding_verifier"
    assert not hasattr(v33, "REPAIR_STORAGE")
    assert not hasattr(repair, "_dcoir_review_v33_original_synthesize_verified_repairs")

    # Applying v33 repeatedly may mark compatibility but must never replace synthesis.
    synth_before = repair.synthesize_verified_repairs
    v33.apply_pareto_context_module(review)
    v33.apply_pareto_context_module(review)
    assert repair.synthesize_verified_repairs is synth_before
    assert repair.synthesize_verified_repairs.__module__ == "dcoir_review.repair_pipeline"

    # Budget deferral remains canonical and fail-closed in the stable policy owner.
    config.fix_synthesis_max_findings = 8
    assert v33.repair_synthesis_budget(config) == 8
    raw = {"title": "candidate-9", "path": "probe.py", "line": 9, "confidence": 0.91}
    deferred = repair_policy.budget_deferred_verified_finding(raw, 9, repair)
    assert deferred[repair.REPAIR_MARKER]["outcome"] == v33.DEFERRED_OUTCOME
    assert deferred["suggested_replacement"] == ""
    assert "repair budget was exhausted" in deferred["fix_guidance"]["notes"]

    print("dcoir_review_required_runtime_patch_v33_selftest passed")


if __name__ == "__main__":
    main()
