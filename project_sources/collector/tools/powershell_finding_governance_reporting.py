#!/usr/bin/env python3
"""Markdown rendering and output persistence for finding governance."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from powershell_finding_governance_common import (
    GovernanceError,
    mark_report_write_failure,
    resolve_repo_output_path,
    write_json,
)


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    validation = report["validation"]
    delta = report["baseline_delta"]
    lines = [
        "# PowerShell Finding Governance Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: #{report['issue']}",
        f"- Validation: `{'pass' if validation['success'] else 'fail'}`",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Current findings | {summary['finding_count']} |",
        f"| Classified findings | {summary['classified_finding_count']} |",
        f"| Unclassified findings | {summary['unclassified_finding_count']} |",
        f"| Baseline records | {summary['baseline_record_count']} |",
        f"| Matched baseline records | {summary['matched_baseline_record_count']} |",
        f"| Suppressions | {summary['suppression_count']} |",
        f"| Matched suppressions | {summary['matched_suppression_count']} |",
        "",
        "## Decisions",
        "",
        "| Decision | Count |",
        "| --- | ---: |",
    ]
    for decision, count in sorted(summary["decision_counts"].items()):
        lines.append(f"| `{decision}` | {count} |")
    if not summary["decision_counts"]:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "## Baseline Delta Proof",
            "",
            f"- New unclassified findings: `{delta['unclassified_finding_count']}`",
            f"- Matched baseline records: `{delta['matched_baseline_record_count']}` / `{delta['baseline_record_count']}`",
            f"- Matched suppressions: `{delta['matched_suppression_count']}` / `{delta['suppression_count']}`",
            f"- As of: `{delta['as_of']}`",
            "",
            "## Inputs",
            "",
            "| Report | Required | Schema | Findings |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for item in report["input_reports"]:
        schema = item.get("schema_version") or "not present"
        lines.append(f"| `{item['path']}` | `{item.get('required', False)}` | `{schema}` | {item['finding_count']} |")
    lines.extend(
        [
            "",
            "## Controlled Fail-Closed Proof",
            "",
            "| Control | Expected Result | Evidence |",
            "| --- | --- | --- |",
        ]
    )
    for control in report["controlled_fail_closed_proof"]:
        lines.append(f"| `{control['id']}` | {control['expected_result']} | `{control['evidence']}` |")
    if validation["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in validation["errors"])
    if validation["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    return "\n".join(lines) + "\n"


def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    json_path = resolve_repo_output_path(repo_root, json_output, "PowerShell finding governance JSON report output")
    markdown_path = resolve_repo_output_path(repo_root, markdown_output, "PowerShell finding governance Markdown report output")
    try:
        outputs_alias = json_path.resolve() == markdown_path.resolve()
    except (OSError, RuntimeError) as exc:
        raise GovernanceError("PowerShell finding governance report output paths must resolve inside the repository root") from exc
    if outputs_alias:
        raise GovernanceError("PowerShell finding governance JSON and Markdown report output paths must be different")
    try:
        write_json(json_path, report)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    except OSError as exc:
        message = f"report write failure: {exc}"
        mark_report_write_failure(report, message)
        try:
            write_json(json_path, report)
        except OSError as rewrite_exc:
            rewrite_message = f"report write failure: failed to persist failed JSON status: {rewrite_exc}"
            mark_report_write_failure(report, rewrite_message)
            raise GovernanceError(f"{message}; {rewrite_message}") from rewrite_exc
        raise GovernanceError(message) from exc
