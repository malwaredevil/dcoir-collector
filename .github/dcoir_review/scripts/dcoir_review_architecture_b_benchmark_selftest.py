#!/usr/bin/env python3
"""Regression checks for the complete deterministic Architecture-B benchmark."""

from __future__ import annotations

import json

import dcoir_review_architecture_b_benchmark_contract as benchmark


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
    assert summary["suppressed_real_defect_regression_count"] == 0
    assert summary["semantic_stage_activation_count"] == 2
    assert summary["carry_forward_scenario_count"] == 2
    assert summary["context_projection_contract_passed"] is True

    semantic = report_a["quality"]["semantic_recall_corpus"]
    assert semantic["case_count"] >= 12
    assert semantic["expected_finding_case_count"] >= 10
    assert semantic["expected_clean_case_count"] >= 2
    assert semantic["semantic_model_recall"]["status"] == "not_measured"

    precision = report_a["quality"]["deterministic_precision"]
    assert precision["regressions"] == []
    assert precision["true_positive_retention_rate"] == 1.0
    assert precision["false_positive_suppression_rate"] == 1.0
    assert precision["suppressed_real_defect_regression_count"] == 0

    unique_stage = report_a["quality"]["unique_stage_contribution"]
    assert unique_stage["status"] == "not_measured"

    budgets = _by_id(report_a["architecture"]["budget_scenarios"])
    reduced = budgets["trusted-small-delta-reduced-budget"]
    assert reduced["optimized"]["mode"] == "small-incremental-delta"
    assert reduced["prompt_budget_reduction_pct"] == 50.0
    assert reduced["deep_context_budget_reduction_pct"] == 50.0
    assert reduced["safety_floor_unchanged"] is True
    assert reduced["input_metrics"]["reviewed_file_count"] == 2
    assert reduced["input_metrics"]["review_surface_chars"] == 6000
    assert reduced["input_metrics"]["deep_context_chars"] == 12000
    assert reduced["input_metrics"]["scope_source"] == "incremental-reviewed-head"
    for scenario_id in (
        "initial-deep-full-quality-floor",
        "risky-small-delta-retains-full-quality-floor",
        "fallback-scope-retains-full-quality-floor",
        "oversized-context-retains-full-quality-floor",
    ):
        assert budgets[scenario_id]["optimized"]["mode"] == "full-quality-floor"
        assert budgets[scenario_id]["safety_floor_unchanged"] is True
        assert budgets[scenario_id]["input_metrics"]["reviewed_file_count"] > 0
        assert budgets[scenario_id]["input_metrics"]["review_surface_chars"] >= 0
        assert budgets[scenario_id]["input_metrics"]["deep_context_chars"] >= 0

    reuse = _by_id(report_a["architecture"]["reuse_batches"])
    mixed = reuse["warm-small-delta-mixed-reuse"]
    assert mixed["file_count"] == 4
    assert mixed["optimized_reused_file_count"] == 2
    assert mixed["optimized_recomputed_file_count"] == 2
    assert mixed["reuse_pct"] == 50.0
    assert mixed["recompute_reduction_pct"] == 50.0
    invalidation = reuse["fail-closed-invalidation-batch"]
    assert invalidation["optimized_reused_file_count"] == 0
    assert invalidation["optimized_recomputed_file_count"] == 3

    carry_forward = _by_id(report_a["architecture"]["carry_forward_scenarios"])
    trusted = carry_forward["trusted-incremental-carry-forward"]
    assert trusted["prior_record_count"] == 3
    assert trusted["changed_frontier_file_count"] == 1
    assert trusted["carried_forward_record_count"] == 2
    assert trusted["counts_match_expectation"] is True
    assert all(
        item["reason"] == "unchanged-in-incremental-frontier"
        for item in trusted["decisions"]
    )
    fallback = carry_forward["fallback-scope-no-carry-forward"]
    assert fallback["carried_forward_record_count"] == 0
    assert fallback["counts_match_expectation"] is True

    escalation = _by_id(report_a["architecture"]["escalation_scenarios"])
    assert escalation["confident-low-risk-primary-evidence"]["plan"]["mode"] == "none"
    assert (
        escalation["near-threshold-candidate-scoped-escalation"]["plan"]["mode"]
        == "candidate-scoped"
    )
    assert escalation["explicit-deep-retains-full-deep"]["plan"]["mode"] == "full-deep"

    stage_activation = report_a["architecture"]["stage_activation"]
    assert stage_activation["activation_count"] == 2
    assert stage_activation["activation_count_matches_expectation"] is True
    assert stage_activation["counts_by_mode"]["candidate-scoped"] == 1
    assert stage_activation["counts_by_mode"]["full-deep"] == 1
    assert stage_activation["counts_by_mode"]["none"] == 1
    assert stage_activation["unique_stage_contribution"]["status"] == "not_measured"

    context_identity = report_a["architecture"]["context_identity"]
    assert context_identity["same_input_signature_stable"] is True
    assert context_identity["head_change_invalidates_signature"] is True

    projection = report_a["architecture"]["context_projection"]
    assert projection["reviewed_file_count"] == 2
    assert projection["review_surface_chars"] > 0
    assert projection["canonical_file_context_chars"] > 0
    assert projection["deep_context_chars"] > 0
    assert projection["context_package_outcome"] == "completed"
    assert projection["budget_mode"] == "small-incremental-delta"
    assert projection["raw_file_contexts_exposed"] is False
    assert projection["projection_telemetry_matches_expectation"] is True
    assert projection["projection_contract_passed"] is True
    assert projection["underlying_builder_calls"] == {
        "contexts": 1,
        "file_prompt": 1,
        "broad_prompt": 1,
        "hybrid": 1,
    }
    telemetry = projection["telemetry"]
    assert telemetry["context_package_build_count"] == 1
    assert telemetry["file_context_fetch_pass_count"] == 1
    assert telemetry["file_context_projection_reuse_count"] == 1
    assert telemetry["per_file_prompt_build_count"] == 1
    assert telemetry["per_file_prompt_reuse_count"] == 1
    assert telemetry["broad_prompt_build_count"] == 1
    assert telemetry["broad_prompt_reuse_count"] == 1
    assert telemetry["fallback_projection_count"] == 0

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
        f"{len(carry_forward)} carry-forward scenarios; "
        f"{len(escalation)} escalation scenarios"
    )


if __name__ == "__main__":
    main()
