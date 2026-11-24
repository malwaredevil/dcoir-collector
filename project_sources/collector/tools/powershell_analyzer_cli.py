#!/usr/bin/env python3
"""CLI orchestration for the DCOIR PowerShell analyzer."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from powershell_analyzer_baseline import apply_baseline, baseline_metadata, load_baseline
from collector_tool_path_safety import repo_relative_input_path
from powershell_analyzer_contract import (
    DEFAULT_INVENTORY,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_SETTINGS,
    ISSUE_NUMBER,
    SCHEMA_VERSION,
    AnalyzerContractError,
    relpath,
    severity_at_or_above,
    sha256_file,
)
from powershell_analyzer_execution import analyzer_command, make_request, normalize_response, run_analyzer_command
from powershell_analyzer_inventory import build_target_sets, load_inventory, portable_target, selected_target_paths
from powershell_analyzer_policy import validate_policy
from powershell_analyzer_reporting import empty_report, expected_finding_errors, write_outputs

def build_report(args: argparse.Namespace) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    repo_root = Path(args.repo_root).resolve()
    inventory_path: Path | None = None
    settings_path: Path | None = None
    baseline_path: Path | None = None
    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    errors: list[str] = []
    warnings: list[str] = []

    try:
        inventory_path = repo_relative_input_path(repo_root, args.inventory, "PowerShell surface inventory path")
        settings_path = repo_relative_input_path(repo_root, args.settings, "analyzer settings path")
        baseline_path = (
            repo_relative_input_path(repo_root, args.baseline_json, "PowerShell analyzer baseline path")
            if args.baseline_json
            else None
        )
        policy = validate_policy(settings_path)
        policy["path"] = relpath(settings_path, repo_root)
        warnings.extend(policy["warnings"])
        inventory = load_inventory(repo_root, inventory_path)
        baseline = load_baseline(baseline_path)
        command, command_kind = analyzer_command(args)
    except AnalyzerContractError as exc:
        errors = [str(exc)]
        return empty_report(
            args=args,
            repo_root=repo_root,
            inventory_path=inventory_path,
            settings_path=settings_path,
            baseline_path=baseline_path,
            json_output=json_output,
            markdown_output=markdown_output,
            errors=errors,
            warnings=warnings,
        ), errors, warnings

    with tempfile.TemporaryDirectory(prefix="dcoir-ps-analyzer-") as temp:
        temp_root = Path(temp)
        targets, skipped_surfaces, target_errors = build_target_sets(
            repo_root=repo_root,
            inventory=inventory,
            only_paths=selected_target_paths(args.target_path),
            temp_root=temp_root,
        )
        errors.extend(target_errors)

        analyzed_targets: list[dict[str, Any]] = []
        all_findings: list[dict[str, Any]] = []
        analyzer_metadata: list[dict[str, Any]] = []
        if not errors:
            for target in targets:
                try:
                    response = run_analyzer_command(
                        command,
                        command_kind,
                        make_request(settings_path, target),
                        args.timeout_seconds,
                    )
                    metadata, findings = normalize_response(
                        response,
                        target,
                        repo_root,
                        args.minimum_powershell_version,
                    )
                    analyzed_targets.append(portable_target(target))
                    analyzer_metadata.append(metadata)
                    all_findings.extend(findings)
                except AnalyzerContractError as exc:
                    errors.append(str(exc))
                    break

        errors.extend(apply_baseline(all_findings, baseline if "baseline" in locals() else None))
        errors.extend(expected_finding_errors(all_findings, args))

        unsuppressed_findings = [finding for finding in all_findings if not finding["suppressed_by_baseline"]]
        # The six explicitly enabled policy rules block at Warning; preserve
        # all legacy Error findings. Other built-in warnings remain evidence,
        # not newly invented blocking rules.
        policy_rules = set(policy["active_include_rules"])
        target_categories = {target["path"]: target["category"] for target in targets}
        parser_findings = [f for f in all_findings if f["severity"].casefold() == "parseerror"]
        fragment_parse_errors = [
            f for f in parser_findings
            if target_categories.get(f["target_path"]) == "collector_harness_source_part"
        ]
        unexpected_parse_errors = len(parser_findings) - len(fragment_parse_errors)
        unknown_severities = [
            f for f in all_findings
            if f["severity"].casefold() not in {"error", "warning", "information", "parseerror"}
        ]
        if unexpected_parse_errors:
            errors.append(f"parse errors outside separately assembled harness fragments: {unexpected_parse_errors}")
        if unknown_severities:
            errors.append(f"analyzer findings with unknown severity: {len(unknown_severities)}")
        blocking_findings = [
            finding for finding in unsuppressed_findings
            if severity_at_or_above(finding["severity"], args.fail_on_severity)
            and (
                finding["severity"].casefold() == "error"
                or args.fail_on_severity == "Information"
                or finding["rule_name"] in policy_rules
            )
        ]
        if blocking_findings and not args.allow_findings:
            errors.append(
                f"unsuppressed analyzer findings at or above {args.fail_on_severity}: {len(blocking_findings)}"
            )

        metadata_first = analyzer_metadata[0] if analyzer_metadata else {}
        analyzer_versions = sorted(
            {
                f"{metadata.get('analyzer_name')} {metadata.get('analyzer_version')}"
                for metadata in analyzer_metadata
                if metadata.get("analyzer_name") and metadata.get("analyzer_version")
            }
        )
        powershell_versions = sorted(
            {
                f"{metadata.get('powershell_engine')} {metadata.get('powershell_version')}"
                for metadata in analyzer_metadata
                if metadata.get("powershell_engine") and metadata.get("powershell_version")
            }
        )
        if len(analyzer_versions) > 1:
            errors.append("analyzer version changed across targets: " + ", ".join(analyzer_versions))
        if len(powershell_versions) > 1:
            errors.append("PowerShell engine/version changed across targets: " + ", ".join(powershell_versions))
        skipped_target_count = max(0, len(targets) - len(analyzed_targets))
        if skipped_target_count:
            errors.append(f"partial scan: {skipped_target_count} intended targets were not analyzed")

        report = {
            "schema_version": SCHEMA_VERSION,
            "issue": ISSUE_NUMBER,
            "source_of_truth": "#261 powershell_surface_inventory.json",
            "analyzer": {
                "name": metadata_first.get("analyzer_name", "not_run"),
                "version": metadata_first.get("analyzer_version", "not_run"),
                "command_kind": command_kind,
                "observed_versions": analyzer_versions,
            },
            "powershell": {
                "engine": metadata_first.get("powershell_engine", "not_run"),
                "version": metadata_first.get("powershell_version", "not_run"),
                "minimum_version": args.minimum_powershell_version,
                "observed_versions": powershell_versions,
            },
            "settings": policy,
            "inventory": {
                "path": relpath(inventory_path, repo_root),
                "schema_version": inventory.get("schema_version"),
                "sha256": sha256_file(inventory_path),
                "inventory_total_surfaces": inventory.get("summary", {}).get("total_surfaces"),
            },
            "baseline": baseline_metadata(baseline if "baseline" in locals() else None, baseline_path, repo_root, all_findings),
            "summary": {
                "target_count": len(targets),
                "analyzed_count": len(analyzed_targets),
                "skipped_target_count": skipped_target_count,
                "reference_or_excluded_surface_count": len(skipped_surfaces),
                "finding_count": len(all_findings),
                "suppressed_finding_count": len(all_findings) - len(unsuppressed_findings),
                "unsuppressed_finding_count": len(unsuppressed_findings),
                "error_count": sum(f["severity"].casefold() == "error" for f in all_findings),
                "warning_count": sum(f["severity"].casefold() == "warning" for f in all_findings),
                "information_count": sum(f["severity"].casefold() == "information" for f in all_findings),
                "parse_error_count": len(parser_findings),
                "harness_fragment_parse_error_count": len(fragment_parse_errors),
                "unexpected_severity_count": len(unknown_severities),
                "policy_warning_count": sum(
                    f["severity"].casefold() == "warning" and f["rule_name"] in policy_rules
                    and not f["suppressed_by_baseline"] for f in all_findings
                ),
                "blocking_finding_count": len(blocking_findings),
                "skipped_count": skipped_target_count,
            },
            "targets": analyzed_targets,
            "skipped_surfaces": skipped_surfaces,
            "findings": all_findings,
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
        return report, errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DCOIR PowerShell analyzer contract")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY.as_posix(), help="PowerShell surface inventory JSON")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS.as_posix(), help="PSScriptAnalyzer settings file")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="JSON report output path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Markdown report output path")
    parser.add_argument("--analyzer-command", action="append", default=[], help="Custom JSON analyzer command token; repeat for args")
    parser.add_argument("--target-path", action="append", default=[], help="Inventory path to analyze; may be repeated")
    parser.add_argument("--baseline-json", help="Optional analyzer baseline JSON")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Analyzer timeout per target")
    parser.add_argument("--minimum-powershell-version", default="5.1", help="Minimum supported PowerShell version")
    parser.add_argument("--fail-on-severity", default="Warning", choices=["Information", "Warning", "Error"], help="Finding severity threshold")
    parser.add_argument("--allow-findings", action="store_true", help="Write reports without failing on unsuppressed findings")
    parser.add_argument("--expect-finding-rule", help="Require at least one finding with this rule name")
    parser.add_argument("--expect-finding-path", help="When expecting a finding, require this path")
    parser.add_argument("--expect-no-findings", action="store_true", help="Fail if unsuppressed findings are present")
    parser.add_argument("--no-write", action="store_true", help="Do not write report files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, errors, _warnings = build_report(args)
    if report is not None and not args.no_write:
        try:
            write_outputs(Path(args.repo_root).resolve(), report, Path(args.json_output), Path(args.markdown_output))
        except AnalyzerContractError as exc:
            errors.append(str(exc))
            report["validation"]["success"] = False
            report["validation"]["errors"] = errors
            try:
                write_outputs(Path(args.repo_root).resolve(), report, Path(args.json_output), Path(args.markdown_output))
            except AnalyzerContractError as rewrite_exc:
                errors.append(str(rewrite_exc))
                report["validation"]["errors"] = errors
    if report is None:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(json.dumps(report["summary"], indent=2))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0
