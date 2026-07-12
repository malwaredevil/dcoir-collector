#!/usr/bin/env python3
"""Fixture result validation and output rendering for custom checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from powershell_custom_checks_common import (
    SEVERITY_ORDER,
    normalize_repo_path,
    repo_relative_cli_path,
    safe_relpath,
)
from powershell_custom_checks_contract import inventory_targets

def expected_match(expected: dict[str, Any], finding: dict[str, Any], path: str) -> bool:
    return (
        finding.get("path") == path
        and finding.get("check_id") == expected.get("check_id")
        and finding.get("rule_name") == expected.get("rule_name")
        and finding.get("severity") == expected.get("severity")
        and finding.get("risk_class") == expected.get("risk_class")
        and finding.get("line") == expected.get("line")
    )


def validate_fixture_results(
    fixture_map: dict[str, dict[str, Any]],
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    by_path: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        by_path.setdefault(finding["path"], []).append(finding)

    fixture_results: list[dict[str, Any]] = []
    for fixture_id, fixture in sorted(fixture_map.items()):
        path = fixture["path"]
        fixture_findings = by_path.get(path, [])
        expected_findings = fixture.get("expected_findings", [])
        if fixture.get("kind") == "control" and fixture_findings:
            errors.append(
                f"{fixture_id}: control fixture produced unexpected findings: "
                + ", ".join(finding["rule_name"] for finding in fixture_findings)
            )
        for expected in expected_findings:
            if not any(expected_match(expected, finding, path) for finding in fixture_findings):
                errors.append(
                    f"{fixture_id}: expected {expected.get('rule_name')} at {path}:{expected.get('line')} was not produced"
                )
        unexpected = [
            finding
            for finding in fixture_findings
            if not any(expected_match(expected, finding, path) for expected in expected_findings)
        ]
        if unexpected and fixture.get("kind") == "negative":
            warnings.append(
                f"{fixture_id}: produced additional unmapped findings: "
                + ", ".join(finding["rule_name"] for finding in unexpected)
            )
        fixture_results.append(
            {
                "id": fixture_id,
                "kind": fixture.get("kind"),
                "check_id": fixture.get("check_id"),
                "path": path,
                "expected_finding_count": len(expected_findings),
                "observed_finding_count": len(fixture_findings),
                "observed_rules": sorted({finding["rule_name"] for finding in fixture_findings}),
            }
        )
    return fixture_results, errors, warnings


def severity_at_or_above(severity: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(severity.casefold(), 99) >= SEVERITY_ORDER.get(threshold.casefold(), 1)


def select_targets(
    args: argparse.Namespace,
    inventory: dict[str, Any],
    fixture_map: dict[str, dict[str, Any]],
) -> list[str]:
    fixture_paths = [fixture["path"] for fixture in fixture_map.values()]
    if args.target_scope == "fixtures":
        targets = fixture_paths
    elif args.target_scope == "inventory":
        targets = inventory_targets(inventory)
    else:
        targets = fixture_paths + inventory_targets(inventory)
    if args.target_path:
        requested = {normalize_repo_path(path) for path in args.target_path}
        targets = [target for target in targets if target in requested]
    return sorted(dict.fromkeys(targets))


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    validation = report["validation"]
    lines = [
        "# PowerShell Custom DCOIR Check Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: `#{report['issue']}`",
        f"- Target scope: `{report['target_scope']}`",
        f"- Checks: `{report['checks']['path']}`",
        f"- Fixture manifest: `{report['fixture_manifest']['path']}`",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Custom checks | {summary['custom_check_count']} |",
        f"| Targets scanned | {summary['target_count']} |",
        f"| Findings | {summary['finding_count']} |",
        f"| Negative fixtures | {summary['negative_fixture_count']} |",
        f"| Control fixtures | {summary['control_fixture_count']} |",
        f"| Expected fixture findings | {summary['expected_fixture_finding_count']} |",
        f"| Observed fixture findings | {summary['observed_fixture_finding_count']} |",
        "",
        "## Findings",
        "",
    ]
    if report["findings"]:
        lines.extend(
            [
                "| Check | Risk | Path | Line | Severity | Observed | Impact | Fix |",
                "| --- | --- | --- | ---: | --- | --- | --- | --- |",
            ]
        )
        for finding in report["findings"]:
            observed = str(finding["observed_problem"]).replace("|", "\\|")
            impact = str(finding["impact"]).replace("|", "\\|")
            fix = str(finding["fix"]).replace("|", "\\|")
            lines.append(
                f"| `{finding['check_id']}` | `{finding['risk_class']}` | `{finding['path']}` | "
                f"{finding['line']} | `{finding['severity']}` | {observed} | {impact} | {fix} |"
            )
    else:
        lines.append("No custom DCOIR findings were reported.")
    lines.extend(["", "## Fixture Results", ""])
    lines.extend(["| Fixture | Kind | Check | Expected | Observed | Rules |", "| --- | --- | --- | ---: | ---: | --- |"])
    for fixture in report["fixtures"]:
        rules = ", ".join(f"`{rule}`" for rule in fixture["observed_rules"]) or "(none)"
        lines.append(
            f"| `{fixture['id']}` | `{fixture['kind']}` | `{fixture['check_id']}` | "
            f"{fixture['expected_finding_count']} | {fixture['observed_finding_count']} | {rules} |"
        )
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


def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> list[str]:
    errors: list[str] = []
    json_path = repo_relative_cli_path(repo_root, json_output, "custom checks JSON report output path", errors)
    markdown_path = repo_relative_cli_path(repo_root, markdown_output, "custom checks Markdown report output path", errors)
    if json_path is not None and markdown_path is not None:
        try:
            if json_path.resolve() == markdown_path.resolve():
                errors.append("custom checks JSON and Markdown report output paths must be different")
        except (OSError, RuntimeError):
            errors.append("custom checks report output paths must resolve inside the repository root")
    outputs = [
        (
            json_path,
            json.dumps(report, indent=2) + "\n",
        ),
        (
            markdown_path,
            render_markdown(report),
        ),
    ]
    if errors:
        return errors
    for path, content in outputs:
        if path is None:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            errors.append(f"could not write expected report output {safe_relpath(path, repo_root)}: {exc}")
            continue
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"expected report output was not written: {safe_relpath(path, repo_root)}")
    return errors
