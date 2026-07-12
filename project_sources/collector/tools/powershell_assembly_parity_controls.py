#!/usr/bin/env python3
"""Inventory, baseline, and coverage controls for assembly parity validation."""
from __future__ import annotations

from powershell_assembly_parity_common import *

def inventory_counts(inventory: dict[str, Any]) -> dict[str, int]:
    controls = inventory.get("controls") if isinstance(inventory, dict) else {}
    if not isinstance(controls, dict):
        return {}
    collector = controls.get("collector_manifest", {})
    harness = controls.get("harness_source_parts", {})
    generated = controls.get("generated_outputs", [])
    collector_expected = collector.get("expected_path_count", 0) if isinstance(collector, dict) else 0
    harness_expected = harness.get("part_count", 0) if isinstance(harness, dict) else 0
    return {
        "collector_manifest_path_count": int(collector_expected or 0),
        "collector_source_part_count": max(0, int(collector_expected or 0) - 1),
        "harness_source_part_count": int(harness_expected or 0),
        "generated_output_mapping_count": len(generated) if isinstance(generated, list) else 0,
    }


def compare_inventory_controls(
    observed: dict[str, int],
    inventory: dict[str, Any],
    errors: list[str],
) -> None:
    counts = inventory_counts(inventory)
    if not counts:
        errors.append("PowerShell surface inventory controls are missing collector/harness source-part counts")
        return
    if observed["collector_source_part_count"] < counts["collector_source_part_count"]:
        errors.append(
            "collector source-part map unexpectedly shrank below inventory controls: "
            f"{observed['collector_source_part_count']} < {counts['collector_source_part_count']}"
        )
    if observed["harness_source_part_count"] < counts["harness_source_part_count"]:
        errors.append(
            "harness source-part map unexpectedly shrank below inventory controls: "
            f"{observed['harness_source_part_count']} < {counts['harness_source_part_count']}"
        )
    if observed["generated_output_count"] < 1 + counts["generated_output_mapping_count"]:
        errors.append(
            "generated-output map unexpectedly shrank below collector plus inventory-generated controls: "
            f"{observed['generated_output_count']} < {1 + counts['generated_output_mapping_count']}"
        )


def compare_baseline_report(
    repo_root: Path,
    baseline_report: Path | None,
    summary: dict[str, int],
    shrink_exceptions: list[str],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any] | None:
    if baseline_report is None:
        warnings.append("no baseline parity report supplied; shrink checks used current inventory controls only")
        return None
    baseline_path = repo_relative_input_path(
        baseline_report.as_posix(),
        "--baseline-report",
        "baseline assembly parity report",
        repo_root,
        errors,
    )
    if baseline_path is None:
        return None
    baseline = read_json(baseline_path, "baseline assembly parity report")
    baseline_summary = baseline.get("summary", {}) if isinstance(baseline, dict) else {}
    checked: dict[str, Any] = {"path": safe_relpath(baseline_path, repo_root), "comparisons": []}
    for key in (
        "collector_source_part_count",
        "harness_source_part_count",
        "source_part_count",
        "generated_output_count",
    ):
        before = int(baseline_summary.get(key, 0) or 0)
        after = int(summary.get(key, 0) or 0)
        comparison = {"key": key, "baseline": before, "current": after, "status": "pass"}
        if after < before and not shrink_exceptions:
            comparison["status"] = "fail"
            errors.append(f"{key} unexpectedly shrank without approved exception: {after} < {before}")
        elif after < before:
            comparison["status"] = "approved_exception"
            comparison["exception_records"] = shrink_exceptions
        checked["comparisons"].append(comparison)
    return checked


def coverage_statement() -> list[dict[str, str]]:
    return [
        {
            "surface": "collector runtime source parts",
            "psscriptanalyzer_wrapper_reporting": "source-part paths when #262 analyzer targets #261 inventory entries",
            "dcoir_custom_checks_reporting": "source-part paths when #264 checks target source-part risk classes",
            "assembly_parity_reporting": "source input map, source hash, generated runtime hash, parse status, and line mapping",
        },
        {
            "surface": "collector compiled runtime generated output",
            "psscriptanalyzer_wrapper_reporting": "not invoked by this #265 runner; future workflow integration can pass generated output explicitly",
            "dcoir_custom_checks_reporting": "not invoked by this #265 runner; parity and parse proof are reported here",
            "assembly_parity_reporting": "generated output hash, parse status, deterministic regeneration status, and source line map",
        },
        {
            "surface": "harness source parts and generated harness",
            "psscriptanalyzer_wrapper_reporting": "source-part paths when #262 analyzer targets .ps1.txt surfaces; generated output when materialized and explicitly targeted",
            "dcoir_custom_checks_reporting": "source-part drift risks through #264 fixtures plus #265 parity proof",
            "assembly_parity_reporting": "ordered source input map, generated harness hash, optional checked-in comparison, parse status, and line map",
        },
    ]


def controlled_bad_cases() -> list[dict[str, str]]:
    return [
        {
            "case": "stale_checked_in_generated_output",
            "evidence": "test_stale_checked_in_generated_output_fails",
            "expected_result": "fails when a committed generated harness differs from deterministic assembly",
        },
        {
            "case": "missing_source_part",
            "evidence": "test_missing_source_part_fails",
            "expected_result": "fails when the collector manifest references a missing source part",
        },
        {
            "case": "missing_source_output_mapping",
            "evidence": "test_missing_source_output_mapping_fails",
            "expected_result": "fails when collector part mapping is absent and generated output cannot be mapped",
        },
        {
            "case": "generated_output_parse_failure",
            "evidence": "test_generated_output_parse_failure_fails",
            "expected_result": "fails when regenerated runnable output has an unbalanced PowerShell structure",
        },
        {
            "case": "unexpected_inventory_shrink",
            "evidence": "test_baseline_shrink_without_exception_fails",
            "expected_result": "fails when source/generated counts shrink below baseline without an exception record",
        },
        {
            "case": "clean_control",
            "evidence": "test_clean_control_passes_and_maps_counts and test_real_repo_contract_passes",
            "expected_result": "passes when source parts, generated outputs, parse status, parity status, and mappings are fresh",
        },
    ]
