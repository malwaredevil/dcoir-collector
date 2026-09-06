#!/usr/bin/env python3
"""Deterministic no-network checks for the clean PR precision lane."""
from __future__ import annotations

import os

import dcoir_review_pr_precision_eval as precision


def main() -> None:
    historical_v3 = precision.load_v3_cases()
    historical_v3_ids = {str(case["id"]) for case in historical_v3}
    assert len(historical_v3) == 10
    assert len(historical_v3_ids) == 10
    assert "precision-ps-native-exit-snapshot-tested" not in historical_v3_ids
    assert "precision-governance-command-gate-approved-tested" not in historical_v3_ids
    assert "precision-ps-native-exit-snapshot-verbose-tested" in historical_v3_ids
    assert "precision-py-retry-budget-tested" in historical_v3_ids
    assert "precision-py-cache-key-callers-tested" in historical_v3_ids
    assert "precision-gha-fork-readonly-approved-tested" in historical_v3_ids

    historical_v4 = precision.load_v4_cases()
    historical_v4_ids = {str(case["id"]) for case in historical_v4}
    assert len(historical_v4) == 10
    assert len(historical_v4_ids) == 10
    assert "precision-py-cache-key-callers-tested" not in historical_v4_ids
    assert "precision-gha-fork-readonly-approved-tested" not in historical_v4_ids
    assert "precision-py-cache-key-callers-invalidation-tested" in historical_v4_ids
    assert "precision-gha-fork-exact-readonly-approved-tested" in historical_v4_ids
    assert "precision-ps-remoting-argumentlist-tested" in historical_v4_ids
    assert "precision-gha-title-via-env-approved-tested" in historical_v4_ids

    cases = precision.load_cases()
    ids = {str(case["id"]) for case in cases}
    assert len(cases) == 10
    assert all(case["expected_findings"] == [] for case in cases)
    assert len(ids) == 10
    for superseded in (
        "precision-ps-native-exit-snapshot-tested",
        "precision-governance-command-gate-approved-tested",
        "precision-py-cache-key-callers-tested",
        "precision-gha-fork-readonly-approved-tested",
        "precision-ps-remoting-argumentlist-tested",
        "precision-gha-title-via-env-approved-tested",
        "precision-gha-fork-exact-readonly-approved-tested",
    ):
        assert superseded not in ids
    for current in (
        "precision-ps-native-exit-snapshot-verbose-tested",
        "precision-py-retry-budget-tested",
        "precision-py-cache-key-callers-invalidation-tested",
        "precision-ps-remoting-argumentlist-behavior-tested",
        "precision-gha-title-via-env-all-shell-surfaces-tested",
        "precision-gha-fork-structural-readonly-approved-tested",
    ):
        assert current in ids

    workflow_cases = [case for case in cases if any(str(item["filename"]).startswith(".github/workflows/") for item in case["files"])]
    assert len(workflow_cases) == 2
    assert all(str(case.get("trusted_context", "")).strip() for case in workflow_cases)

    old = os.environ.get("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT")
    try:
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "1"
        for case in cases:
            prompt = precision.build_pr_prompt(case)
            assert str(case["ground_truth_rationale"]) not in prompt
            assert "expected_findings" not in prompt
            assert str(case["id"]) not in prompt
            assert "ground_truth_rationale" not in prompt
            if case.get("trusted_context"):
                assert "Trusted evaluation context:" in prompt
                assert str(case["trusted_context"]) in prompt
            else:
                assert "Trusted evaluation context:" not in prompt

        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "0"
        for case in workflow_cases:
            prompt = precision.build_pr_prompt(case)
            assert "Trusted evaluation context:" not in prompt
            assert str(case["trusted_context"]) not in prompt
            assert str(case["ground_truth_rationale"]) not in prompt
    finally:
        if old is None:
            os.environ.pop("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT", None)
        else:
            os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = old

    print("dcoir_review_pr_precision_eval_selftest passed: current v5 has 10 policy-clean PRs, preserves historical v3/v4, replaces all three paired-S1 benchmark defects, hides ground truth, and supports trusted-context ablation")


if __name__ == "__main__":
    main()
