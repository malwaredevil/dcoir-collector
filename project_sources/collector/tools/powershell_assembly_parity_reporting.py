#!/usr/bin/env python3
"""Report rendering and persistence helpers for assembly parity validation."""
from __future__ import annotations

from powershell_assembly_parity_common import *

def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    validation = report["validation"]
    lines = [
        "# PowerShell Assembly Parity Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: `#{report['issue']}`",
        f"- Success: `{validation['success']}`",
        f"- Source parts: `{summary['source_part_count']}`",
        f"- Collector source parts: `{summary['collector_source_part_count']}`",
        f"- Harness source parts: `{summary['harness_source_part_count']}`",
        f"- Generated outputs mapped: `{summary['generated_output_count']}`",
        f"- Parse status: `{summary['parse_status']}`",
        f"- Parity status: `{summary['parity_status']}`",
        "",
        "## Generated Outputs",
        "",
        "| Output | Inputs | Parse | Parity | Line Mapping |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for output in report["generated_outputs"]:
        lines.append(
            "| `{path}` | `{inputs}` | `{parse}` | `{parity}` | `{mapping}` |".format(
                path=output["path"],
                inputs=output["source_input_count"],
                parse="pass" if output["parse"]["success"] else "fail",
                parity=output["parity"]["status"],
                mapping=output["line_mapping_status"],
            )
        )
    lines.extend(
        [
            "",
            "## Coverage Statement",
            "",
            "| Surface | Analyzer wrapper reporting | Custom check reporting | Assembly parity reporting |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in report["coverage_statement"]:
        lines.append(
            "| `{surface}` | {analyzer} | {custom} | {parity} |".format(
                surface=item["surface"],
                analyzer=item["psscriptanalyzer_wrapper_reporting"],
                custom=item["dcoir_custom_checks_reporting"],
                parity=item["assembly_parity_reporting"],
            )
        )
    lines.extend(["", "## Controlled Cases", ""])
    for item in report["controlled_bad_cases"]:
        lines.append(f"- `{item['case']}`: {item['expected_result']} (`{item['evidence']}`)")
    if validation["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in validation["errors"])
    if validation["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    return "\n".join(lines) + "\n"


def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> list[str]:
    errors: list[str] = []
    json_path = repo_relative_input_path(
        json_output.as_posix(),
        "--json-output",
        "assembly parity JSON report output",
        repo_root,
        errors,
    )
    markdown_path = repo_relative_input_path(
        markdown_output.as_posix(),
        "--markdown-output",
        "assembly parity Markdown report output",
        repo_root,
        errors,
    )
    if json_path is not None and markdown_path is not None:
        try:
            if json_path.resolve() == markdown_path.resolve():
                errors.append("assembly parity JSON and Markdown report output paths must be different")
        except (OSError, RuntimeError):
            errors.append("assembly parity report output paths must resolve inside the repository root")
    output_targets = (
        (
            json_path,
            json.dumps(report, indent=2) + "\n",
        ),
        (
            markdown_path,
            render_markdown(report),
        ),
    )
    if errors:
        return errors
    for path, content in output_targets:
        if path is None:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            errors.append(f"failed to write {safe_relpath(path, repo_root)}: {exc}")
    return errors
