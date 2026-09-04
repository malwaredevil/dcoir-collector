#!/usr/bin/env python3
"""Complete Workstream-F observability contract for the Architecture-B benchmark.

The original benchmark module owns the same-corpus quality and planning core.
This layer adds the deterministic production telemetry that issue #476 requires
but that is not represented by model-free quality fixtures alone: v43 carry
forward, v46 composed-context projection reuse, explicit review-surface sizes,
and aggregate stage activation. Live semantic contribution, token, cost, and
time measurements remain intentionally unavailable offline.
"""

from __future__ import annotations

import argparse
import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dcoir_review_architecture_b_benchmark as core
import dcoir_review_required_runtime_patch_v41_scope as v41_scope
import dcoir_review_required_runtime_patch_v43 as v43
import dcoir_review_required_runtime_patch_v46 as v46


REPORT_SCHEMA = core.REPORT_SCHEMA
MANIFEST_PATH = core.MANIFEST_PATH
NOT_MEASURED_REASON = core.NOT_MEASURED_REASON


class _BenchmarkReviewQualityError(RuntimeError):
    pass


def _carry_forward_report(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    prior_head = "a" * 40
    current_head = "b" * 40
    reports: list[dict[str, Any]] = []
    for scenario in manifest.get("carry_forward_scenarios", []):
        if not isinstance(scenario, dict):
            continue
        prior_paths = [
            str(path) for path in scenario.get("prior_paths", []) if str(path).strip()
        ]
        changed_paths = [
            str(path) for path in scenario.get("changed_paths", []) if str(path).strip()
        ]
        prior_records = {
            path: core._prior_record(core._base_reuse_material(path), prior_head)
            for path in prior_paths
        }
        state = {
            "prior_records": prior_records,
            "trusted_prior_head": prior_head,
            "load_reason": "trusted-prior-manifest-loaded",
            "decisions": {},
            "carry_forward_decisions": {},
            "records": {},
            "carried_forward_record_count": 0,
            "lock": threading.Lock(),
        }
        scope = {
            "source": str(scenario.get("scope_source", "") or ""),
            "fallback_reason": str(scenario.get("fallback_reason", "") or ""),
            "compare_status": str(scenario.get("compare_status", "") or ""),
            "prior_reviewed_head_sha": prior_head,
            "current_head_sha": current_head,
            "files": [
                {"filename": path, "status": "modified"} for path in changed_paths
            ],
        }
        gh = SimpleNamespace()
        setattr(gh, v41_scope.SCOPE_CACHE_ATTR, scope)
        carried = v43._carry_forward_unchanged_records(
            gh, {"head": {"sha": current_head}}, state
        )
        expected = int(scenario.get("expected_carried", -1))
        reports.append(
            {
                "id": str(scenario.get("id", "") or ""),
                "prior_record_count": len(prior_records),
                "changed_frontier_file_count": len(changed_paths),
                "carried_forward_record_count": carried,
                "expected_carried_forward_record_count": expected,
                "counts_match_expectation": carried == expected,
                "scope_source": scope["source"],
                "scope_compare_status": scope["compare_status"],
                "scope_fallback_reason": scope["fallback_reason"],
                "decisions": [
                    copy.deepcopy(state["carry_forward_decisions"][path])
                    for path in sorted(state["carry_forward_decisions"])
                ],
            }
        )
    return reports


def _fake_hardened(artifacts: dict[str, Any]) -> Any:
    return SimpleNamespace(
        ReviewQualityError=_BenchmarkReviewQualityError,
        risk_sentinel_digest=lambda values: f"risk:{len(values)}",
        write_debug_json_artifact_safely=lambda _cfg, name, value: artifacts.__setitem__(
            name, copy.deepcopy(value)
        ),
        parse_yaml_like_data=lambda _path: {},
        bool_value=lambda data, key, default: data.get(key, default),
    )


def _context_projection_report(
    manifest: dict[str, Any], production_config: Any
) -> dict[str, Any]:
    spec = manifest.get("context_identity_scenario", {})
    if not isinstance(spec, dict):
        raise AssertionError("context_identity_scenario must be an object")

    paths = [str(path) for path in spec.get("changed_paths", []) if str(path).strip()]
    files = [
        {
            "filename": path,
            "status": "modified",
            "sha": core.v42_fp.text_digest(f"blob:{path}")[:40],
            "patch": f"@@ -1 +1 @@\n-old {path}\n+new {path}",
        }
        for path in paths
    ]
    pr = {"number": 476, "title": "Architecture-B benchmark", "head": {"sha": "c" * 40}}
    diff = str(spec.get("diff", "") or "")
    deep_context = str(spec.get("deep_context", "") or "")
    review_mode = str(spec.get("review_mode", "diff") or "diff")
    context_summary = str(spec.get("context_summary", "") or "")
    artifacts: dict[str, Any] = {}
    calls = {"contexts": 0, "file_prompt": 0, "broad_prompt": 0, "hybrid": 0}
    module = SimpleNamespace(hardened=_fake_hardened(artifacts))
    module.load_pareto_context_config = lambda _path: copy.copy(production_config)

    def build_contexts(_gh, _pr, selected_files, _config):
        calls["contexts"] += 1
        return [
            {
                "path": str(item["filename"]),
                "text": f"exact-head source for {item['filename']}",
                "item": item,
            }
            for item in selected_files
        ]

    def file_prompt(_pr, item, file_text, prompt_diff, _cfg, _risks, mode):
        calls["file_prompt"] += 1
        return f"file:{item['filename']}:{file_text}:{prompt_diff}:{mode}"

    def broad_prompt(
        _pr, _files, prompt_diff, _cfg, _risks, deep, mode, summary
    ):
        calls["broad_prompt"] += 1
        return f"broad:{prompt_diff}:{deep}:{mode}:{summary}"

    module.build_file_contexts = build_contexts
    module.build_per_file_review_prompt = file_prompt
    module.build_prompt = broad_prompt

    def hybrid(
        hybrid_pr,
        hybrid_files,
        hybrid_diff,
        _schema,
        staged_config,
        _reporter,
        risks,
        _line_index,
        deep,
        mode,
        summary,
        gh,
    ):
        calls["hybrid"] += 1
        contexts = module.build_file_contexts(gh, hybrid_pr, hybrid_files, staged_config)
        if not contexts:
            raise AssertionError("benchmark context projection requires at least one file")
        first_item = hybrid_files[0]
        first_context = contexts[0]
        first = module.build_per_file_review_prompt(
            hybrid_pr,
            first_item,
            first_context["text"],
            hybrid_diff,
            staged_config,
            risks,
            mode,
        )
        second = module.build_per_file_review_prompt(
            hybrid_pr,
            first_item,
            first_context["text"],
            hybrid_diff,
            staged_config,
            risks,
            mode,
        )
        broad_first = module.build_prompt(
            hybrid_pr,
            hybrid_files,
            hybrid_diff,
            staged_config,
            risks,
            deep,
            mode,
            summary,
        )
        broad_second = module.build_prompt(
            hybrid_pr,
            hybrid_files,
            hybrid_diff,
            staged_config,
            risks,
            deep,
            mode,
            summary,
        )
        if first != second or broad_first != broad_second:
            raise AssertionError("reused projections changed prompt content")
        return {"summary": "offline deterministic benchmark", "findings": []}, "", ""

    module.openrouter_review_with_hybrid_first_pass = hybrid
    v46.apply_pareto_context_module(module)

    gh = SimpleNamespace()
    setattr(
        gh,
        v41_scope.SCOPE_CACHE_ATTR,
        {
            "source": "incremental-reviewed-head",
            "compare_status": "ahead",
            "fallback_reason": "",
        },
    )
    config = copy.copy(production_config)
    reporter = SimpleNamespace(events=[])
    reporter.update = lambda key, value: reporter.events.append((key, value))
    result, _model, _tier = module.openrouter_review_with_hybrid_first_pass(
        pr,
        files,
        diff,
        {"type": "object"},
        config,
        reporter,
        [],
        {},
        deep_context,
        review_mode,
        context_summary,
        gh,
    )
    package = module.semantic_context_package_for_client(gh)
    telemetry = copy.deepcopy(package.get("telemetry", {}))
    expected = spec.get("expected_projection_telemetry", {})
    expected = dict(expected) if isinstance(expected, dict) else {}
    telemetry_matches = all(telemetry.get(key) == value for key, value in expected.items())
    context_records = [
        item for item in package.get("file_context_records", []) if isinstance(item, dict)
    ]
    raw_exposed = "file_contexts" in package
    return {
        "id": str(spec.get("id", "") or ""),
        "reviewed_file_count": int(package.get("changed_file_count", 0) or 0),
        "review_surface_chars": int(package.get("diff_chars", 0) or 0),
        "diff_chars": int(package.get("diff_chars", 0) or 0),
        "canonical_file_context_chars": sum(
            int(item.get("text_chars", 0) or 0) for item in context_records
        ),
        "deep_context_chars": int(package.get("deep_context_chars", 0) or 0),
        "context_package_id": str(package.get("package_id", "") or ""),
        "context_package_outcome": str(package.get("outcome", "") or ""),
        "budget_mode": str(package.get("budget_plan", {}).get("mode", "") or ""),
        "telemetry": telemetry,
        "expected_projection_telemetry": expected,
        "projection_telemetry_matches_expectation": telemetry_matches,
        "underlying_builder_calls": calls,
        "raw_file_contexts_exposed": raw_exposed,
        "projection_contract_passed": bool(
            telemetry_matches
            and not raw_exposed
            and calls
            == {"contexts": 1, "file_prompt": 1, "broad_prompt": 1, "hybrid": 1}
            and package.get("outcome") == "completed"
            and bool(result.get("_semantic_context_package_id"))
        ),
        "artifact_paths": sorted(artifacts),
    }


def _enrich_budget_inputs(
    report: dict[str, Any], manifest: dict[str, Any]
) -> None:
    by_id = {
        str(item.get("id", "")): item
        for item in manifest.get("budget_scenarios", [])
        if isinstance(item, dict)
    }
    for item in report.get("architecture", {}).get("budget_scenarios", []):
        if not isinstance(item, dict):
            continue
        source = by_id.get(str(item.get("id", "")), {})
        item["input_metrics"] = {
            "reviewed_file_count": int(source.get("changed_file_count", 0) or 0),
            "review_surface_chars": int(source.get("diff_chars", 0) or 0),
            "diff_chars": int(source.get("diff_chars", 0) or 0),
            "deep_context_chars": int(source.get("deep_context_chars", 0) or 0),
            "risk_sentinel_count": int(source.get("risk_sentinel_count", 0) or 0),
            "scope_source": str(source.get("scope_source", "") or ""),
            "scope_compare_status": str(source.get("compare_status", "") or ""),
            "scope_fallback_reason": str(source.get("fallback_reason", "") or ""),
        }


def _stage_activation_summary(
    manifest: dict[str, Any], escalation: list[dict[str, Any]]
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in escalation:
        if not isinstance(item, dict):
            continue
        plan = item.get("plan", {})
        mode = str(plan.get("mode", "") or "") if isinstance(plan, dict) else ""
        counts[mode] = counts.get(mode, 0) + 1
    activated_modes = {"candidate-scoped", "broader-context", "full-deep"}
    activated = sum(count for mode, count in counts.items() if mode in activated_modes)
    expected = int(manifest.get("expected_semantic_stage_activation_count", -1))
    return {
        "activation_count": activated,
        "expected_activation_count": expected,
        "activation_count_matches_expectation": activated == expected,
        "counts_by_mode": dict(sorted(counts.items())),
        "unique_stage_contribution": {
            "status": "not_measured",
            "reason": (
                "offline planning can prove stage activation, but unique semantic finding "
                "contribution requires observed model-backed review evidence"
            ),
        },
    }


def _apply_contract_regressions(
    report: dict[str, Any],
    carry_forward: list[dict[str, Any]],
    context_projection: dict[str, Any],
    stage_activation: dict[str, Any],
) -> None:
    summary = report.setdefault("summary", {})
    regressions = [str(item) for item in summary.get("blocking_regressions", [])]
    precision = report.get("quality", {}).get("deterministic_precision", {})
    suppressed_real = int(
        precision.get("suppressed_real_defect_regression_count", 0) or 0
    )
    if suppressed_real:
        regressions.append("suppressed-real-defect-regression")
    for item in carry_forward:
        if not item.get("counts_match_expectation"):
            regressions.append(f"carry-forward:{item.get('id')}")
    if not context_projection.get("projection_contract_passed"):
        regressions.append("context-projection-contract")
    if not stage_activation.get("activation_count_matches_expectation"):
        regressions.append("semantic-stage-activation-count")
    summary["blocking_regressions"] = sorted(set(regressions))
    summary["deterministic_quality_gate_passed"] = not bool(
        summary["blocking_regressions"]
    )
    summary["suppressed_real_defect_regression_count"] = suppressed_real
    summary["semantic_stage_activation_count"] = int(
        stage_activation.get("activation_count", 0) or 0
    )
    summary["carry_forward_scenario_count"] = len(carry_forward)
    summary["context_projection_contract_passed"] = bool(
        context_projection.get("projection_contract_passed")
    )


def build_report() -> dict[str, Any]:
    report = core.build_report()
    manifest = core._load_json(MANIFEST_PATH)
    _enrich_budget_inputs(report, manifest)

    precision = report["quality"]["deterministic_precision"]
    precision["suppressed_real_defect_regression_count"] = max(
        0,
        int(precision.get("known_true_positive_count", 0) or 0)
        - int(precision.get("known_true_positives_retained", 0) or 0),
    )

    carry_forward = _carry_forward_report(manifest)
    production_config = core._production_config()
    context_projection = _context_projection_report(manifest, production_config)
    escalation = report["architecture"]["escalation_scenarios"]
    stage_activation = _stage_activation_summary(manifest, escalation)

    report["architecture"]["carry_forward_scenarios"] = carry_forward
    report["architecture"]["context_projection"] = context_projection
    report["architecture"]["stage_activation"] = stage_activation
    report["quality"]["unique_stage_contribution"] = copy.deepcopy(
        stage_activation["unique_stage_contribution"]
    )
    _apply_contract_regressions(
        report, carry_forward, context_projection, stage_activation
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="optional path for the complete deterministic JSON benchmark report",
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
