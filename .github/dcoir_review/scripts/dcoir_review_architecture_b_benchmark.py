#!/usr/bin/env python3
"""Deterministic same-corpus Architecture-B benchmark for DCOIR Review.

This benchmark intentionally performs no OpenRouter/model inference. It reuses
production planning helpers and governed evaluation corpora to measure what can
be proved offline, while marking live token/cost/time fields as not measured.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dcoir_review_precision_regression_selftest as precision_selftest
import dcoir_review_required_runtime_patch_v42_fingerprints as v42_fp
import dcoir_review_required_runtime_patch_v43_reuse as v43_reuse
import dcoir_review_required_runtime_patch_v44_scope as v44_scope
import dcoir_review_required_runtime_patch_v45 as v45
import dcoir_review_required_runtime_patch_v46_budget as v46_budget
import dcoir_review_required_runtime_patch_v46_context as v46_context
import dcoir_review_semantic_recall_corpus_selftest as semantic_recall_selftest
import openrouter_pr_review_pareto_context as review
from dcoir_review.entrypoint import DcoirReviewEntrypoint


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation" / "architecture_b_benchmark_v1.json"
SEMANTIC_CORPUS_PATH = ROOT / "evaluation" / "semantic_recall_corpus_v1.json"
CONFIG_PATH = ROOT / "openrouter-pr-review-pareto.yml"
REPORT_SCHEMA = "dcoir_review_architecture_b_benchmark_report_v1"
NOT_MEASURED_REASON = (
    "offline deterministic benchmark; observed live review evidence is required"
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path.name} must contain a JSON object")
    return value


def _capture_stdout(callable_obj: Any) -> str:
    stream = io.StringIO()
    previous = Path.cwd()
    try:
        os.chdir(ROOT.parents[1])
        with contextlib.redirect_stdout(stream):
            callable_obj()
    finally:
        os.chdir(previous)
    return stream.getvalue().strip()


def _semantic_inventory() -> dict[str, Any]:
    # Reuse the governed structural selftest as the corpus-validity gate.
    selftest_output = _capture_stdout(semantic_recall_selftest.main)
    corpus = _load_json(SEMANTIC_CORPUS_PATH)
    cases = [item for item in corpus.get("cases", []) if isinstance(item, dict)]
    finding_cases = [item for item in cases if item.get("expected") == "finding"]
    clean_cases = [item for item in cases if item.get("expected") == "clean"]
    return {
        "schema_version": str(corpus.get("schema_version", "") or ""),
        "case_count": len(cases),
        "expected_finding_case_count": len(finding_cases),
        "expected_clean_case_count": len(clean_cases),
        "defect_classes": sorted(
            {str(item.get("defect_class", "") or "") for item in cases}
        ),
        "structural_selftest": selftest_output,
        "semantic_model_recall": {
            "status": "not_measured",
            "reason": NOT_MEASURED_REASON,
        },
    }


def _precision_metrics() -> dict[str, Any]:
    # The existing regression selftest owns deterministic precision behavior.
    # Capture and reuse its machine-readable metrics rather than duplicating the
    # sentinel implementation in the benchmark.
    text = _capture_stdout(precision_selftest.main)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise AssertionError("precision selftest did not emit a metrics object")
    return value


def _production_config() -> Any:
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review.load_pareto_context_config(str(CONFIG_PATH))


def _pct_reduction(base: int, selected: int) -> float | None:
    if base <= 0:
        return None
    return round(((base - selected) / base) * 100.0, 4)


def _budget_report(manifest: dict[str, Any], config: Any) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for scenario in manifest.get("budget_scenarios", []):
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("id", "") or "")
        metadata = {
            "package_id": v42_fp.digest({"benchmark_scenario": scenario_id}),
            "review_mode": str(scenario.get("review_mode", "") or ""),
            "scope_source": str(scenario.get("scope_source", "") or ""),
            "scope_compare_status": str(scenario.get("compare_status", "") or ""),
            "scope_fallback_reason": str(scenario.get("fallback_reason", "") or ""),
            "changed_file_count": int(scenario.get("changed_file_count", 0) or 0),
            "diff_chars": int(scenario.get("diff_chars", 0) or 0),
            "deep_context_chars": int(scenario.get("deep_context_chars", 0) or 0),
            "risk_sentinel_count": int(scenario.get("risk_sentinel_count", 0) or 0),
        }
        package = {"metadata": metadata}
        sentinels = [object() for _ in range(metadata["risk_sentinel_count"])]

        baseline_config = copy.copy(config)
        baseline_config.adaptive_semantic_budgets_review = False
        baseline = v46_budget.select_budget_plan(package, baseline_config, sentinels)
        optimized = v46_budget.select_budget_plan(package, config, sentinels)

        baseline_selected = dict(baseline.get("selected", {}))
        optimized_selected = dict(optimized.get("selected", {}))
        safety_keys = (
            "candidate_escalation_total_context_chars",
            "semantic_adjudication_candidate_digest_chars",
            "max_inline_comments",
        )
        safety_unchanged = all(
            baseline_selected.get(key) == optimized_selected.get(key)
            for key in safety_keys
        )
        expected_mode = str(scenario.get("expected_mode", "") or "")
        expected_reason = str(scenario.get("expected_reason", "") or "")
        actual_reasons = [
            str(item) for item in optimized.get("reasons", []) if str(item)
        ]
        reports.append(
            {
                "id": scenario_id,
                "baseline_contract": "adaptive-budgets-disabled-rollback",
                "baseline": baseline,
                "optimized": optimized,
                "prompt_budget_reduction_pct": _pct_reduction(
                    int(baseline_selected.get("max_prompt_chars", 0) or 0),
                    int(optimized_selected.get("max_prompt_chars", 0) or 0),
                ),
                "deep_context_budget_reduction_pct": _pct_reduction(
                    int(
                        baseline_selected.get("deep_review_max_total_chars", 0)
                        or 0
                    ),
                    int(
                        optimized_selected.get("deep_review_max_total_chars", 0)
                        or 0
                    ),
                ),
                "safety_floor_unchanged": safety_unchanged,
                "expected_mode": expected_mode,
                "mode_matches_expectation": optimized.get("mode") == expected_mode,
                "expected_reason": expected_reason,
                "reason_matches_expectation": (
                    not expected_reason or expected_reason in actual_reasons
                ),
            }
        )
    return reports


def _base_reuse_material(path: str) -> dict[str, Any]:
    material = {
        "contract": v43_reuse.REUSE_CONTRACT,
        "runtime_version": v43_reuse.VERSION,
        "architecture_contract": "architecture-b-v1",
        "path": path,
        "source_identity": f"blob:{v42_fp.text_digest(path)[:40]}",
        "semantic_prompt_sha256": v42_fp.text_digest(f"prompt:{path}"),
        "reviewer_fingerprint": v42_fp.text_digest("benchmark-reviewer-v1"),
        "schema_sha256": v42_fp.text_digest("benchmark-schema-v1"),
        "config_sha256": v42_fp.text_digest("benchmark-config-v1"),
        "dependency_sha256": v42_fp.text_digest("benchmark-dependency-v1"),
        "risk_fingerprint": "",
        "review_mode": "diff",
    }
    material["reuse_key"] = v42_fp.digest(material)
    return material


def _mutate_material(material: dict[str, Any], mutation: str) -> dict[str, Any]:
    changed = dict(material)
    mutations = {
        "source_changed": ("source_identity", "blob:" + "f" * 40),
        "config_changed": ("config_sha256", v42_fp.text_digest("changed-config")),
        "risk_changed": ("risk_fingerprint", v42_fp.text_digest("changed-risk")),
        "review_mode_changed": ("review_mode", "first-pass-deep"),
    }
    if mutation in mutations:
        field, value = mutations[mutation]
        changed[field] = value
        changed.pop("reuse_key", None)
        changed["reuse_key"] = v42_fp.digest(changed)
    return changed


def _prior_record(material: dict[str, Any], head: str) -> dict[str, Any]:
    return {
        **material,
        "outcome": "complete",
        "origin_reviewed_head": head,
        "carried_forward_head": head,
        "result": {"findings": []},
    }


def _reuse_report(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    trusted_head = "a" * 40
    for batch in manifest.get("reuse_batches", []):
        if not isinstance(batch, dict):
            continue
        decisions: list[dict[str, Any]] = []
        for file_spec in batch.get("files", []):
            if not isinstance(file_spec, dict):
                continue
            path = str(file_spec.get("path", "") or "")
            mutation = str(file_spec.get("mutation", "none") or "none")
            original = _base_reuse_material(path)
            prior = (
                None
                if mutation == "prior_missing"
                else _prior_record(original, trusted_head)
            )
            current = _mutate_material(original, mutation)
            eligible, reason = v43_reuse.evaluate_reuse_candidate(
                current, prior, trusted_head
            )
            decisions.append(
                {
                    "path": path,
                    "mutation": mutation,
                    "decision": "reused" if eligible else "recomputed",
                    "reason": reason,
                }
            )

        reused = sum(item["decision"] == "reused" for item in decisions)
        recomputed = len(decisions) - reused
        baseline_recomputed = len(decisions)
        expected_reused = int(batch.get("expected_reused", -1))
        expected_recomputed = int(batch.get("expected_recomputed", -1))
        reports.append(
            {
                "id": str(batch.get("id", "") or ""),
                "baseline_contract": "cold-no-prior-semantic-result",
                "file_count": len(decisions),
                "baseline_recomputed_file_count": baseline_recomputed,
                "optimized_reused_file_count": reused,
                "optimized_recomputed_file_count": recomputed,
                "reuse_pct": round((reused / len(decisions)) * 100.0, 4)
                if decisions
                else 0.0,
                "recompute_reduction_pct": _pct_reduction(
                    baseline_recomputed, recomputed
                ),
                "decisions": decisions,
                "expected_reused": expected_reused,
                "expected_recomputed": expected_recomputed,
                "counts_match_expectation": (
                    reused == expected_reused and recomputed == expected_recomputed
                ),
            }
        )
    return reports


class _BenchmarkHardened:
    @staticmethod
    def result_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
        findings = result.get("findings", []) if isinstance(result, dict) else []
        return [item for item in findings if isinstance(item, dict)]

    @staticmethod
    def uncovered_risk_sentinels(
        findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any
    ) -> list[Any]:
        del findings, risk_sentinels, config
        return []


def _escalation_report(
    manifest: dict[str, Any], config: Any
) -> list[dict[str, Any]]:
    module = SimpleNamespace(hardened=_BenchmarkHardened())
    reports: list[dict[str, Any]] = []
    for scenario in manifest.get("escalation_scenarios", []):
        if not isinstance(scenario, dict):
            continue
        files = [
            {"filename": str(path), "status": "modified"}
            for path in scenario.get("changed_paths", [])
        ]
        findings = [
            dict(item)
            for item in scenario.get("findings", [])
            if isinstance(item, dict)
        ]
        plan = v44_scope.build_escalation_plan(
            module,
            {"findings": findings},
            files,
            [],
            config,
            str(scenario.get("review_mode", "") or ""),
        )
        expected_mode = str(scenario.get("expected_mode", "") or "")
        reports.append(
            {
                "id": str(scenario.get("id", "") or ""),
                "plan": plan,
                "expected_mode": expected_mode,
                "mode_matches_expectation": plan.get("mode") == expected_mode,
            }
        )
    return reports


def _context_identity_report(manifest: dict[str, Any]) -> dict[str, Any]:
    spec = manifest.get("context_identity_scenario", {})
    if not isinstance(spec, dict):
        raise AssertionError("context_identity_scenario must be an object")
    head = "1" * 40
    files = [
        {
            "filename": str(path),
            "status": "modified",
            "sha": "2" * 40,
            "patch": f"+benchmark {path}",
        }
        for path in spec.get("changed_paths", [])
    ]
    pr = {"head": {"sha": head}}
    diff = str(spec.get("diff", "") or "")
    deep = str(spec.get("deep_context", "") or "")
    review_mode = str(spec.get("review_mode", "diff") or "diff")
    summary = str(spec.get("context_summary", "") or "")

    signature_a = v46_context.input_signature(
        pr, files, diff, deep, review_mode, summary
    )
    signature_b = v46_context.input_signature(
        pr, files, diff, deep, review_mode, summary
    )
    moved_pr = {"head": {"sha": "3" * 40}}
    moved_signature = v46_context.input_signature(
        moved_pr, files, diff, deep, review_mode, summary
    )
    return {
        "id": str(spec.get("id", "") or ""),
        "same_input_signature_stable": signature_a == signature_b,
        "head_change_invalidates_signature": signature_a != moved_signature,
        "input_signature": signature_a,
        "changed_head_signature": moved_signature,
    }


def _calibration_report(manifest: dict[str, Any]) -> dict[str, Any]:
    spec = manifest.get("calibration_scenario", {})
    if not isinstance(spec, dict):
        raise AssertionError("calibration_scenario must be an object")
    candidate_count = int(spec.get("candidate_count", 0) or 0)
    supported_count = int(spec.get("supported_count", 0) or 0)
    candidates = [{"id": index} for index in range(candidate_count)]
    supported = candidates[:supported_count]
    module = SimpleNamespace()
    disposition = v45._capture_verifier_disposition(
        module,
        candidates,
        supported,
        {"head": {"sha": "4" * 40}},
    )
    expected_suppressed = int(spec.get("expected_suppressed", -1))
    return {
        "id": str(spec.get("id", "") or ""),
        "disposition": disposition,
        "expected_suppressed": expected_suppressed,
        "suppressed_matches_expectation": (
            disposition.get("verifier_suppressed_count") == expected_suppressed
        ),
        "verifier_support_rate_pct": round(
            (supported_count / candidate_count) * 100.0, 4
        )
        if candidate_count
        else 0.0,
        "actual_candidate_to_publish_calibration": {
            "status": "not_measured",
            "reason": NOT_MEASURED_REASON,
        },
        "scope_note": (
            "deterministic verifier disposition accounting only; actual semantic "
            "candidate quality requires live/model-backed evidence"
        ),
    }


def _live_only_metrics(manifest: dict[str, Any]) -> dict[str, Any]:
    fields = [
        str(item)
        for item in manifest.get("live_only_metrics", [])
        if str(item).strip()
    ]
    return {
        field: {"status": "not_measured", "reason": NOT_MEASURED_REASON}
        for field in fields
    }


def _blocking_regressions(
    precision: dict[str, Any],
    budgets: list[dict[str, Any]],
    reuse_batches: list[dict[str, Any]],
    escalation: list[dict[str, Any]],
    context_identity: dict[str, Any],
    calibration: dict[str, Any],
) -> list[str]:
    regressions: list[str] = []
    if precision.get("regressions"):
        regressions.append("precision-corpus-regression")
    for item in budgets:
        if not item.get("mode_matches_expectation"):
            regressions.append(f"budget-mode:{item.get('id')}")
        if not item.get("reason_matches_expectation"):
            regressions.append(f"budget-reason:{item.get('id')}")
        if not item.get("safety_floor_unchanged"):
            regressions.append(f"budget-safety-floor:{item.get('id')}")
    for item in reuse_batches:
        if not item.get("counts_match_expectation"):
            regressions.append(f"reuse-counts:{item.get('id')}")
    for item in escalation:
        if not item.get("mode_matches_expectation"):
            regressions.append(f"escalation-mode:{item.get('id')}")
    if not context_identity.get("same_input_signature_stable"):
        regressions.append("context-signature-nondeterministic")
    if not context_identity.get("head_change_invalidates_signature"):
        regressions.append("context-head-invalidation-missing")
    if not calibration.get("suppressed_matches_expectation"):
        regressions.append("verifier-disposition-accounting")
    return regressions


def build_report() -> dict[str, Any]:
    manifest = _load_json(MANIFEST_PATH)
    if manifest.get("schema_version") != "dcoir_review_architecture_b_benchmark_v1":
        raise AssertionError("unexpected Architecture-B benchmark manifest schema")

    semantic_inventory = _semantic_inventory()
    precision = _precision_metrics()
    config = _production_config()
    budgets = _budget_report(manifest, config)
    reuse_batches = _reuse_report(manifest)
    escalation = _escalation_report(manifest, config)
    context_identity = _context_identity_report(manifest)
    calibration = _calibration_report(manifest)
    live_only = _live_only_metrics(manifest)
    regressions = _blocking_regressions(
        precision,
        budgets,
        reuse_batches,
        escalation,
        context_identity,
        calibration,
    )

    reduced_budget_scenarios = [
        item
        for item in budgets
        if item.get("optimized", {}).get("mode") == "small-incremental-delta"
    ]
    return {
        "schema_version": REPORT_SCHEMA,
        "manifest_schema_version": manifest.get("schema_version"),
        "benchmark_contract": manifest.get("benchmark_contract"),
        "quality": {
            "semantic_recall_corpus": semantic_inventory,
            "deterministic_precision": precision,
            "verifier_calibration": calibration,
        },
        "architecture": {
            "budget_scenarios": budgets,
            "reuse_batches": reuse_batches,
            "escalation_scenarios": escalation,
            "context_identity": context_identity,
        },
        "live_only_metrics": live_only,
        "summary": {
            "blocking_regressions": regressions,
            "deterministic_quality_gate_passed": not bool(regressions),
            "reduced_budget_scenario_count": len(reduced_budget_scenarios),
            "offline_measurement_boundary": (
                "Architecture/proxy metrics only; this report does not satisfy "
                "the parent token or wall-clock acceptance targets."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="optional path for the deterministic JSON benchmark report",
    )
    args = parser.parse_args()

    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if report["summary"]["blocking_regressions"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
