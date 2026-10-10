#!/usr/bin/env python3
"""Report rendering and output helpers for the PowerShell analyzer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from powershell_analyzer_baseline import baseline_metadata
from collector_tool_path_safety import repo_relative_input_path
from powershell_analyzer_contract import (
    ISSUE_NUMBER,
    REQUIRED_POLICY_RULES,
    SCHEMA_VERSION,
    AnalyzerContractError,
    safe_relpath,
    sha256_file,
)

def expected_finding_errors(findings: list[dict[str, Any]], args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.expect_finding_rule:
        matches = [
            finding
            for finding in findings
            if finding["rule_name"] == args.expect_finding_rule
            and (not args.expect_finding_path or finding["path"] == args.expect_finding_path)
        ]
        if not matches:
            path_text = f" at {args.expect_finding_path}" if args.expect_finding_path else ""
            errors.append(f"expected analyzer finding {args.expect_finding_rule}{path_text} was not produced")
    if args.expect_no_findings:
        unsuppressed = [finding for finding in findings if not finding["suppressed_by_baseline"]]
        if unsuppressed:
            errors.append(f"expected no unsuppressed analyzer findings, found {len(unsuppressed)}")
    return errors


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    validation = report["validation"]
    lines = [
        "# DCOIR PowerShell Analyzer Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: `#{report['issue']}`",
        f"- Analyzer: `{report['analyzer']['name']}` `{report['analyzer']['version']}`",
        f"- PowerShell: `{report['powershell']['engine']}` `{report['powershell']['version']}`",
        f"- Settings: `{report['settings']['path']}`",
        f"- Inventory: `{report['inventory']['path']}`",
        f"- JSON artifact: `{report['outputs']['json']}`",
        f"- Validation: `{'pass' if validation['success'] else 'fail'}`",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Intended targets | {summary['target_count']} |",
        f"| Analyzed targets | {summary['analyzed_count']} |",
        f"| Skipped intended targets | {summary['skipped_target_count']} |",
        f"| Reference/excluded surfaces | {summary['reference_or_excluded_surface_count']} |",
        f"| Findings | {summary['finding_count']} |",
        f"| Baseline-suppressed findings | {summary['suppressed_finding_count']} |",
        f"| Unsuppressed findings | {summary['unsuppressed_finding_count']} |",
        "",
        "## Findings",
        "",
    ]
    findings = report["findings"]
    if findings:
        lines.extend(["| Path | Line | Severity | Rule | Problem | Recommended Fix |", "| --- | ---: | --- | --- | --- | --- |"])
        for finding in findings:
            line = finding["line"] if finding["line"] is not None else ""
            suppressed = " (baseline-suppressed)" if finding["suppressed_by_baseline"] else ""
            problem = str(finding["observed_problem"]).replace("|", "\\|")
            fix = str(finding["recommended_fix"] or "").replace("|", "\\|")
            lines.append(
                f"| `{finding['path']}` | {line} | `{finding['severity']}{suppressed}` | "
                f"`{finding['rule_name']}` | {problem} | {fix} |"
            )
    else:
        lines.append("No analyzer findings were reported.")

    lines.extend(["", "## Validation Findings", ""])
    if validation["errors"]:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in validation["errors"])
    else:
        lines.append("- No validation errors.")
    if validation["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    lines.append("")
    return "\n".join(lines)


def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    json_path = repo_relative_input_path(repo_root, json_output, "JSON report output path")
    markdown_path = repo_relative_input_path(repo_root, markdown_output, "Markdown report output path")
    if json_path == markdown_path:
        raise AnalyzerContractError("JSON and Markdown report output paths must be different")
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_text = json.dumps(report, indent=2) + "\n"
        json_path.write_text(json_text, encoding="utf-8")
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    except (TypeError, OSError) as exc:
        raise AnalyzerContractError(f"report write failure: {exc}") from exc
    for label, path in (("JSON", json_path), ("Markdown", markdown_path)):
        if not path.exists() or path.stat().st_size == 0:
            raise AnalyzerContractError(f"missing output: {label} report was not written to {path}")


def empty_report(
    *,
    args: argparse.Namespace,
    repo_root: Path,
    inventory_path: Path | None,
    settings_path: Path | None,
    baseline_path: Path | None = None,
    json_output: Path,
    markdown_output: Path,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    settings_metadata = {
        "path": safe_relpath(settings_path, repo_root) if settings_path is not None else str(args.settings),
        "accepted": settings_path is not None,
        "sha256": sha256_file(settings_path)
        if settings_path is not None and settings_path.exists() and settings_path.is_file()
        else None,
        "required_rules": sorted(REQUIRED_POLICY_RULES),
        "active_severities": [],
        "active_include_rules": [],
        "active_rule_keys": [],
        "warnings": [],
        "exclusions_declared": False,
    }
    inventory_metadata = {
        "path": safe_relpath(inventory_path, repo_root) if inventory_path is not None else str(args.inventory),
        "accepted": inventory_path is not None,
        "schema_version": None,
        "sha256": sha256_file(inventory_path)
        if inventory_path is not None and inventory_path.exists() and inventory_path.is_file()
        else None,
        "inventory_total_surfaces": None,
    }
    baseline_info = baseline_metadata(None, baseline_path, repo_root)
    if args.baseline_json:
        baseline_info["path"] = safe_relpath(baseline_path, repo_root) if baseline_path is not None else str(args.baseline_json)
        baseline_info["accepted"] = baseline_path is not None
    return {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "source_of_truth": "#261 powershell_surface_inventory.json",
        "analyzer": {
            "name": "not_run",
            "version": "not_run",
            "command_kind": "not_run",
            "observed_versions": [],
        },
        "powershell": {
            "engine": "not_run",
            "version": "not_run",
            "minimum_version": args.minimum_powershell_version,
            "observed_versions": [],
        },
        "settings": settings_metadata,
        "inventory": inventory_metadata,
        "baseline": baseline_info,
        "summary": {
            "target_count": 0,
            "analyzed_count": 0,
            "skipped_target_count": 0,
            "reference_or_excluded_surface_count": 0,
            "finding_count": 0,
            "suppressed_finding_count": 0,
            "unsuppressed_finding_count": 0,
        },
        "targets": [],
        "skipped_surfaces": [],
        "findings": [],
        "validation": {
            "success": False,
            "errors": errors,
            "warnings": warnings,
        },
        "outputs": {
            "json": json_output.as_posix(),
            "markdown": markdown_output.as_posix(),
        },
    }
