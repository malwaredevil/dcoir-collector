#!/usr/bin/env python3
"""Markdown rendering and output writing for rule-risk fixture reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from powershell_rule_risk_fixtures_common import RuleRiskFixtureError, repo_relative_path_or_error

def render_matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# PowerShell Rule-To-Risk Matrix",
        "",
        f"- Schema: `{matrix.get('schema_version')}`",
        f"- Issue: `#{matrix.get('issue')}`",
        f"- Parent issue: `#{matrix.get('parent_issue')}`",
        "- Scope: rule-to-risk mapping and fixture proof only; no workflow, SARIF, required-check, or PR mutation.",
        "",
        "## Checks",
        "",
        "| Check ID | Rule | Tool | Blocking | Severity | Risk Classes | Fixtures |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for check in matrix.get("checks", []):
        risks = "<br>".join(f"`{risk}`" for risk in check.get("risk_classes", []))
        fixtures = ", ".join(f"`{fixture}`" for fixture in check.get("fixtures", [])) or "(none)"
        lines.append(
            f"| `{check.get('id')}` | `{check.get('rule_name')}` | {check.get('tool')} | "
            f"`{str(check.get('blocking')).lower()}` | `{check.get('expected_severity')}` | {risks} | {fixtures} |"
        )
    lines.extend(["", "## Advisory Promotion", ""])
    advisory = [check for check in matrix.get("checks", []) if check.get("blocking") is False]
    if not advisory:
        lines.append("- No advisory checks declared.")
    for check in advisory:
        lines.append(f"- `{check.get('id')}`: {check.get('promotion_criteria')}")
    lines.append("")
    return "\n".join(lines)

def render_report_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    validation = report["validation"]
    lines = [
        "# PowerShell Rule-Risk Fixture Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: `#{report['issue']}`",
        f"- Matrix: `{report['matrix']['path']}`",
        f"- Manifest: `{report['manifest']['path']}`",
        f"- Analyzer wrapper: `{report['analyzer_wrapper']['path']}`",
        f"- Fixture analyzer: `{report['fixture_analyzer']['name']} {report['fixture_analyzer']['version']}`",
        f"- Validation: `{'pass' if validation['success'] else 'fail'}`",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Matrix checks | {summary['matrix_check_count']} |",
        f"| Blocking checks | {summary['blocking_check_count']} |",
        f"| Advisory checks | {summary['advisory_check_count']} |",
        f"| Negative fixtures | {summary['negative_fixture_count']} |",
        f"| Control fixtures | {summary['control_fixture_count']} |",
        f"| Expected findings | {summary['expected_finding_count']} |",
        f"| Observed findings | {summary['observed_finding_count']} |",
        "",
        "## Fixtures",
        "",
        "| Fixture | Kind | Expected | Observed | Status | Rules |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for fixture in report["fixtures"]:
        rules = ", ".join(f"`{rule}`" for rule in fixture["observed_rules"]) or "(none)"
        status = "pass" if fixture["validation"]["success"] else "fail"
        lines.append(
            f"| `{fixture['id']}` | `{fixture['kind']}` | {fixture['expected_finding_count']} | "
            f"{fixture['observed_finding_count']} | `{status}` | {rules} |"
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
    if report.get("environment_gap"):
        lines.extend(["", "## Environment Gap", "", f"- {report['environment_gap']}"])
    lines.append("")
    return "\n".join(lines)

def ensure_distinct_output_paths(paths: list[tuple[str, Path]], errors: list[str]) -> None:
    seen: dict[Path, str] = {}
    for label, path in paths:
        prior = seen.get(path)
        if prior is not None:
            errors.append(f"{label} output path must be different from {prior} output path")
        seen[path] = label

def mark_output_failure(report: dict[str, Any], error: str) -> None:
    validation = report.setdefault("validation", {})
    validation["success"] = False
    errors = validation.setdefault("errors", [])
    if error not in errors:
        errors.append(error)

def rewrite_failed_report_outputs(
    json_path: Path | None,
    markdown_path: Path | None,
    report: dict[str, Any],
    error: str,
) -> None:
    mark_output_failure(report, error)
    written_paths: set[Path] = set()
    rewrite_targets = [
        (json_path, json.dumps(report, indent=2) + "\n", "JSON"),
        (markdown_path, render_report_markdown(report), "Markdown"),
    ]
    for path, text, label in rewrite_targets:
        if path is None or path in written_paths:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written_paths.add(path)
        except (TypeError, OSError) as exc:
            mark_output_failure(report, f"failed to rewrite failed {label} report after output error: {exc}")

def write_outputs(
    repo_root: Path,
    report: dict[str, Any],
    matrix: dict[str, Any],
    json_output: Path,
    markdown_output: Path,
    matrix_markdown_output: Path,
) -> None:
    path_errors: list[str] = []
    json_path = repo_relative_path_or_error(repo_root, json_output, "fixture report JSON output path", path_errors)
    markdown_path = repo_relative_path_or_error(repo_root, markdown_output, "fixture report Markdown output path", path_errors)
    matrix_markdown_path = repo_relative_path_or_error(
        repo_root,
        matrix_markdown_output,
        "rule-risk matrix Markdown output path",
        path_errors,
    )
    if json_path is not None and markdown_path is not None and matrix_markdown_path is not None:
        ensure_distinct_output_paths(
            [("JSON", json_path), ("Markdown", markdown_path), ("matrix Markdown", matrix_markdown_path)],
            path_errors,
        )
    if path_errors:
        error = "; ".join(path_errors)
        rewrite_failed_report_outputs(json_path, markdown_path, report, error)
        raise RuleRiskFixtureError(error)

    if json_path is None or markdown_path is None or matrix_markdown_path is None:
        raise RuleRiskFixtureError("output path validation failed unexpectedly")
    output_paths = [("JSON", json_path), ("Markdown", markdown_path), ("matrix Markdown", matrix_markdown_path)]
    outputs = [
        ("matrix Markdown", matrix_markdown_path, render_matrix_markdown(matrix)),
        ("JSON", json_path, json.dumps(report, indent=2) + "\n"),
        ("Markdown", markdown_path, render_report_markdown(report)),
    ]
    try:
        for _label, path, text in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for label, path in output_paths:
            if not path.exists() or path.stat().st_size == 0:
                raise RuleRiskFixtureError(f"missing output: {label} report was not written to {path}")
    except RuleRiskFixtureError as exc:
        error = str(exc)
    except (TypeError, OSError) as exc:
        error = f"report write failure: {exc}"
    else:
        return

    rewrite_failed_report_outputs(json_path, markdown_path, report, error)
    raise RuleRiskFixtureError(error)
