#!/usr/bin/env python3
"""Regression checks for the deterministic Architecture-B benchmark."""

from __future__ import annotations

import json

import dcoir_review_architecture_b_benchmark as benchmark


FORBIDDEN_CASE_LOOKUPS = (
    "pull request #448",
    "pr #448",
    "issue #456",
    "gemini_behavioral_replay_scoring.py",
)


def _by_id(items):
    return {str(item.get("id", "")): item for item in items}


def main() -> None:
    report_a = benchmark.build_report()
    report_b = benchmark.build_report()
    assert report_a == report_b
    assert report_a["schema_version"] == benchmark.REPORT_SCHEMA

    summary = report_a["summary"]
    assert summary["blocking_regressions"] == []
    assert summary["deterministic_quality_gate_passed"] is True
    assert summary["reduced_budget_scenario_count"] >= 1

    semantic = report_a["quality"]["semantic_recall_corpus"]
    assert semantic["case_count"] >= 12
    assert semantic["expected_finding_case_count"] >= 10
    assert semantic["expected_clean_case_count"] >= 2
    assert semantic["semantic_model_recall"]["status"] == "not_measured"

    precision = report_a["quality"]["deterministic_precision"]
    assert precision["regressions"] == []
    assert precision["true_positive_retention_rate"] == 1.0
    assert precision["false_positive_suppression_rate"] == 1.0

    budgets = _by_id(report_a["architecture"]["budget_scenarios"])
    reduced = budgets["trusted-small-delta-reduced-budget"]
    assert reduced["optimized"]["mode"] == "small-incremental-delta"
    assert reduced["prompt_budget_reduction_pct"] > 0
    assert reduced["deep_context_budget_reduction_pct"] > 0
    assert reduced["safety_floor_unchanged"] is True
    for scenario_id in (
        "initial-deep-full-quality-floor",
        "risky-small-delta-retains-full-quality-floor",
        "fallback-scope-retains-full-quality-floor",
        "oversized-context-retains-full-quality-floor",
    ):
        assert budgets[scenario_id]["optimized"]["mode"] == "full-quality-floor"
        assert budgets[scenario_id]["safety_floor_unchanged"] is True

    reuse = _by_id(report_a["architecture"]["reuse_batches"])
    mixed = reuse["warm-small-delta-mixed-reuse"]
    assert mixed["optimized_reused_file_count"] == 2
    assert mixed["optimized_recomputed_file_count"] == 2
    assert mixed["recompute_reduction_pct"] == 50.0
    invalidation = reuse["fail-closed-invalidation-batch"]
    assert invalidation["optimized_reused_file_count"] == 0
    assert invalidation["optimized_recomputed_file_count"] == 3

    escalation = _by_id(report_a["architecture"]["escalation_scenarios"])
    assert escalation["confident-low-risk-primary-evidence"]["plan"]["mode"] == "none"
    assert (
        escalation["near-threshold-candidate-scoped-escalation"]["plan"]["mode"]
        == "candidate-scoped"
    )
    assert escalation["explicit-deep-retains-full-deep"]["plan"]["mode"] == "full-deep"

    context_identity = report_a["architecture"]["context_identity"]
    assert context_identity["same_input_signature_stable"] is True
    assert context_identity["head_change_invalidates_signature"] is True

    calibration = report_a["quality"]["verifier_calibration"]
    assert calibration["disposition"]["verifier_candidate_count"] == 3
    assert calibration["disposition"]["verifier_supported_count"] == 2
    assert calibration["disposition"]["verifier_suppressed_count"] == 1
    assert calibration["suppressed_matches_expectation"] is True
    assert calibration["actual_candidate_to_publish_calibration"]["status"] == "not_measured"

    live_only = report_a["live_only_metrics"]
    assert live_only
    assert all(item["status"] == "not_measured" for item in live_only.values())

    manifest = json.loads(benchmark.MANIFEST_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(manifest, sort_keys=True).lower()
    for forbidden in FORBIDDEN_CASE_LOOKUPS:
        assert forbidden not in serialized

    print(
        "dcoir_review_architecture_b_benchmark_selftest passed: "
        f"{semantic['case_count']} semantic cases; "
        f"{len(budgets)} budget scenarios; "
        f"{len(reuse)} reuse batches; "
        f"{len(escalation)} escalation scenarios"
    )


if __name__ == "__main__":
    main()
