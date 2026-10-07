#!/usr/bin/env python3
"""CLI orchestration for PowerShell assembly parity validation."""
from __future__ import annotations

from powershell_assembly_parity_builders import build_collector_output, build_harness_output
from powershell_assembly_parity_common import *
from powershell_assembly_parity_controls import (
    compare_baseline_report,
    compare_inventory_controls,
    controlled_bad_cases,
    coverage_statement,
    inventory_counts,
)
from powershell_assembly_parity_reporting import write_outputs

def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = repo_relative_input_path(args.manifest, "--manifest", "collector runtime manifest", repo_root, errors)
    inventory_path = repo_relative_input_path(args.inventory, "--inventory", "PowerShell surface inventory", repo_root, errors)
    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    baseline_report = Path(args.baseline_report) if args.baseline_report else None
    shrink_exceptions = list(args.shrink_exception or [])

    manifest: dict[str, Any] = {}
    inventory: dict[str, Any] = {}
    if not errors and manifest_path is not None and inventory_path is not None:
        try:
            manifest = read_json(manifest_path, "collector runtime manifest")
        except AssemblyParityError as exc:
            errors.append(str(exc))
        try:
            inventory = read_json(inventory_path, "PowerShell surface inventory")
        except AssemblyParityError as exc:
            errors.append(str(exc))
    if manifest and not isinstance(manifest, dict):
        errors.append(f"collector runtime manifest must be a JSON object: {Path(args.manifest).as_posix()}")
        manifest = {}
    if inventory and not isinstance(inventory, dict):
        errors.append(f"PowerShell surface inventory must be a JSON object: {Path(args.inventory).as_posix()}")
        inventory = {}

    collector_text = ""
    harness_text = ""
    collector_sources: list[dict[str, Any]] = []
    harness_sources: list[dict[str, Any]] = []
    generated_outputs: list[dict[str, Any]] = []
    if manifest:
        collector_text, collector_sources, collector_output = build_collector_output(repo_root, manifest, errors)
        if collector_output:
            generated_outputs.append(collector_output)
    harness_text, harness_sources, harness_output = build_harness_output(repo_root, errors)
    generated_outputs.append(harness_output)

    for output in generated_outputs:
        if not output["line_mapping"]:
            errors.append(f"{output['id']}: source/output mapping is missing")
        if not output["parse"]["success"]:
            errors.append(f"{output['id']}: generated output parse check failed")
        if output["parity"]["status"] != "pass":
            errors.append(f"{output['id']}: parity status is {output['parity']['status']}")

    collector_part_count = len([entry for entry in collector_sources if entry.get("role") == "collector_runtime_source_part" and entry.get("exists")])
    harness_part_count = len([entry for entry in harness_sources if entry.get("role") == "collector_harness_source_part" and entry.get("exists")])
    summary = {
        "collector_source_part_count": collector_part_count,
        "harness_source_part_count": harness_part_count,
        "source_part_count": collector_part_count + harness_part_count,
        "source_input_count": len([entry for entry in collector_sources + harness_sources if entry.get("exists")]),
        "generated_output_count": len(generated_outputs),
        "parse_success_count": len([output for output in generated_outputs if output["parse"]["success"]]),
        "parity_success_count": len([output for output in generated_outputs if output["parity"]["status"] == "pass"]),
    }
    summary["parse_status"] = "pass" if summary["parse_success_count"] == len(generated_outputs) else "fail"
    summary["parity_status"] = "pass" if summary["parity_success_count"] == len(generated_outputs) else "fail"

    compare_inventory_controls(summary, inventory, errors)
    baseline = None
    if baseline_report is not None:
        try:
            baseline = compare_baseline_report(repo_root, baseline_report, summary, shrink_exceptions, errors, warnings)
        except AssemblyParityError as exc:
            errors.append(str(exc))
    else:
        warnings.append("no baseline parity report supplied; shrink checks used current inventory controls only")

    report = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "parent_issue": PARENT_ISSUE_NUMBER,
        "depends_on": [261, 262, 263, 264],
        "source_of_truth": "#265 assembly-aware validation for PowerShell source parts and generated outputs",
        "manifest": {
            "path": Path(args.manifest).as_posix(),
            "accepted": manifest_path is not None,
            "exists": manifest_path.is_file() if manifest_path is not None else False,
            "sha256": sha256_file(manifest_path) if manifest_path is not None and manifest_path.is_file() else None,
            "source_strategy": manifest.get("source_strategy") if isinstance(manifest, dict) else None,
        },
        "inventory": {
            "path": Path(args.inventory).as_posix(),
            "accepted": inventory_path is not None,
            "exists": inventory_path.is_file() if inventory_path is not None else False,
            "sha256": sha256_file(inventory_path) if inventory_path is not None and inventory_path.is_file() else None,
            "schema_version": inventory.get("schema_version") if isinstance(inventory, dict) else None,
            "control_counts": inventory_counts(inventory),
        },
        "summary": summary,
        "source_maps": {
            "collector_runtime": collector_sources,
            "harness": harness_sources,
        },
        "generated_outputs": generated_outputs,
        "coverage_statement": coverage_statement(),
        "controlled_bad_cases": controlled_bad_cases(),
        "baseline_comparison": baseline,
        "validation": {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        },
        "outputs": {
            "json": json_output.as_posix(),
            "markdown": markdown_output.as_posix(),
        },
    }
    if not args.no_write:
        output_errors = write_outputs(repo_root, report, json_output, markdown_output)
        if output_errors:
            errors.extend(output_errors)
            report["validation"]["success"] = False
            report["validation"]["errors"] = errors
            write_outputs(repo_root, report, json_output, markdown_output)
    return report, errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DCOIR PowerShell assembly parity validation")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix(), help="Collector runtime manifest JSON")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY.as_posix(), help="#261 PowerShell inventory JSON")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="Assembly parity JSON report path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Assembly parity Markdown report path")
    parser.add_argument("--baseline-report", default="", help="Previous assembly parity report for shrink checks")
    parser.add_argument("--shrink-exception", action="append", default=[], help="Approved exception record for expected shrink")
    parser.add_argument("--no-write", action="store_true", help="Do not write report outputs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, errors, _warnings = build_report(args)
    print(json.dumps(report["summary"], indent=2))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0
