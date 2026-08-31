#!/usr/bin/env python3
"""Focused fail-closed regression for the v38 repair critic confidence gate."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")

    for raw_confidence in (-0.01, 1.01, True):
        try:
            v36._parse_critic(
                {"accepted": True, "confidence": raw_confidence, "reason": "invalid confidence probe"},
                review.hardened,
            )
        except review.hardened.ReviewQualityError:
            pass
        else:
            raise AssertionError(f"critic confidence did not fail closed: {raw_confidence!r}")

    accepted, confidence, _reason = v36._parse_critic(
        {"accepted": True, "confidence": 0.95, "reason": "valid lower acceptance boundary"},
        review.hardened,
    )
    assert accepted is True and confidence == 0.95

    accepted, confidence, _reason = v36._parse_critic(
        {"accepted": True, "confidence": 0.949, "reason": "below hard acceptance boundary"},
        review.hardened,
    )
    assert accepted is False and confidence == 0.949

    print("dcoir_review_required_runtime_patch_v38_critic_selftest passed")


if __name__ == "__main__":
    main()
