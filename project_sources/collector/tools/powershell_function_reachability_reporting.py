#!/usr/bin/env python3
"""Report rendering and classification helpers for PowerShell reachability."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from powershell_function_reachability_contract import (
    CLASSIFICATIONS,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    ISSUE_NUMBER,
    NON_CLAIMS,
    PARENT_ISSUE_NUMBER,
    SCHEMA_VERSION,
    Definition,
    ReachabilityError,
    Reference,
    SourceFile,
    AnalyzerContractError,
    read_json,
    repo_relative_input_path,
    resolve_sources,
    safe_output_path,
    scalar,
    sha256_file,
    write_json,
)


def reference_entry(reference: Reference) -> dict[str, Any]:
    return {
        "source_path": reference.source_path,
        "line": reference.line,
        "column": reference.column,
        "invocation_kind": reference.invocation_kind,
        "parser": reference.parser,
    }


def classify_functions(
    definitions: list[Definition],
    references: list[Reference],
    dynamic_sites: list[dict[str, Any]],
    entrypoints: set[str],
) -> list[dict[str, Any]]:
    refs_by_key: dict[str, list[Reference]] = defaultdict(list)
    for ref in references:
        refs_by_key[ref.key].append(ref)
    has_dynamic_uncertainty = bool(dynamic_sites)
    records: list[dict[str, Any]] = []
    for definition in sorted(definitions, key=lambda item: (item.load_order, item.line, item.name.casefold())):
        refs = refs_by_key.get(definition.key, [])
        if definition.key in entrypoints:
            classification = "entrypoint"
        elif refs:
            classification = "literal_referenced"
        elif has_dynamic_uncertainty:
            classification = "dynamic_invocation_uncertain"
        else:
            classification = "static_unreferenced"
        records.append(
            {
                "name": definition.name,
                "normalized_name": definition.key,
                "classification": classification,
                "source_path": definition.source_path,
                "line": definition.line,
                "column": definition.column,
                "end_line": definition.end_line,
                "definition_kind": definition.definition_kind,
                "static_reference_status": "literal_reference_found" if refs else "no_literal_reference_found",
                "dynamic_uncertainty_status": "dynamic_invocation_sites_present"
                if has_dynamic_uncertainty
                else "no_dynamic_invocation_sites_detected",
                "reference_count": len(refs),
                "references": [reference_entry(ref) for ref in refs[:20]],
                "truncated_reference_count": max(0, len(refs) - 20),
                "coverage_status": "not_observed_in_suite",
                "coverage_lanes": [],
                "claim": "classification is report-only and not deletion proof",
            }
        )
    return records


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# PowerShell Function Reachability Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: #{report['issue']}",
        f"- Parent issue: #{report['parent_issue']}",
        f"- Parser mode: `{summary['parser_mode']}`",
        f"- Validation: `{'pass' if report['validation']['success'] else 'fail'}`",
        f"- Functions: `{summary['function_count']}`",
        "",
        "## Classification Summary",
        "",
        "| Classification | Count |",
        "| --- | ---: |",
    ]
    for classification in CLASSIFICATIONS:
        lines.append(f"| `{classification}` | {summary['classification_counts'].get(classification, 0)} |")
    lines.extend(
        [
            "",
            "## Scope",
            "",
            f"- Manifest: `{report['analysis_scope']['manifest_path']}`",
            "- Runtime-lane coverage: `not_collected`",
            "- Covered source files:",
        ]
    )
    lines.extend(f"  - `{item['path']}`" for item in report["analysis_scope"]["source_files"])
    lines.extend(["", "## Potential Follow-Up Functions", "", "| Function | Classification | Source | Line | References |", "| --- | --- | --- | ---: | ---: |"])
    for item in report["functions"]:
        if item["classification"] in {"static_unreferenced", "dynamic_invocation_uncertain", "entrypoint"}:
            lines.append(
                f"| `{item['name']}` | `{item['classification']}` | `{item['source_path']}` | {item['line']} | {item['reference_count']} |"
            )
    if not any(item["classification"] in {"static_unreferenced", "dynamic_invocation_uncertain", "entrypoint"} for item in report["functions"]):
        lines.append("| none | `none` | none |  |  |")
    lines.extend(["", "## Dynamic Invocation Sites", "", "| Kind | Source | Line | Context |", "| --- | --- | ---: | --- |"])
    for site in report["dynamic_invocation_sites"][:50]:
        context = scalar(site.get("context")).replace("|", "\\|")
        lines.append(f"| `{site.get('kind')}` | `{site.get('source_path')}` | {site.get('line')} | `{context}` |")
    if not report["dynamic_invocation_sites"]:
        lines.append("| none | none |  | none detected |")
    lines.extend(["", "## Non-Claims", ""])
    lines.extend(f"- {claim}" for claim in report["non_claims"])
    if report["validation"]["errors"]:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- {error}" for error in report["validation"]["errors"])
    if report["validation"]["warnings"]:
        lines.extend(["", "## Validation Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["validation"]["warnings"])
    return "\n".join(lines) + "\n"


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    functions = report.get("functions")
    if not isinstance(functions, list) or not functions:
        errors.append("report must contain at least one function record")
        return errors
    classifications = Counter(scalar(item.get("classification")) for item in functions if isinstance(item, dict))
    for classification in classifications:
        if classification not in CLASSIFICATIONS:
            errors.append(f"unknown function classification: {classification}")
    if sum(classifications.values()) != report["summary"].get("function_count"):
        errors.append("classification counts do not sum to function_count")
    markdown = render_markdown(report)
    for fragment in (
        "This report does not claim any function is safe to delete.",
        "Runtime-lane coverage: `not_collected`",
        "Classification Summary",
    ):
        if fragment not in markdown:
            errors.append(f"Markdown parity missing fragment: {fragment}")
    return errors


def build_report(
    args: argparse.Namespace,
    *,
    parse_sources_func: Callable[[list[SourceFile], str], tuple[list[Definition], list[Reference], list[dict[str, Any]], list[dict[str, Any]], str]],
) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest_path = repo_relative_input_path(repo_root, args.manifest, "collector runtime manifest")
    except AnalyzerContractError as exc:
        raise ReachabilityError(str(exc)) from exc
    manifest, sources, source_errors = resolve_sources(repo_root, manifest_path)
    errors.extend(source_errors)

    definitions: list[Definition] = []
    references: list[Reference] = []
    dynamic_sites: list[dict[str, Any]] = []
    parser_mode = "python_lexical_fallback" if getattr(args, "no_powershell", False) else args.parser_mode
    if not errors:
        definitions, references, dynamic_sites, parser_warnings, parser_mode = parse_sources_func(sources, parser_mode)
        warnings.extend(scalar(item.get("message")) for item in parser_warnings if isinstance(item, dict) and item.get("message"))

    seen_defs: set[tuple[str, str, int]] = set()
    for definition in definitions:
        key = (definition.key, definition.source_path, definition.line)
        if key in seen_defs:
            errors.append(f"duplicate function definition record: {definition.name} {definition.source_path}:{definition.line}")
        seen_defs.add(key)

    entrypoints = {item.casefold() for item in args.entrypoint}
    function_records = classify_functions(definitions, references, dynamic_sites, entrypoints)
    classification_counts = Counter(item["classification"] for item in function_records)
    source_files = [
        {
            "path": source.repo_path,
            "load_order": source.load_order,
            "sha256": sha256_file(source.path),
            "size_bytes": source.path.stat().st_size,
        }
        for source in sources
    ]
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "parent_issue": PARENT_ISSUE_NUMBER,
        "generated_from": {
            "tool": "project_sources/collector/tools/run_powershell_function_reachability_report.py",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "parser_mode": parser_mode,
        },
        "analysis_scope": {
            "scope": "manifest_declared_collector_runtime_source",
            "manifest_path": manifest_path.resolve().relative_to(repo_root).as_posix(),
            "collector_wrapper_source": manifest.get("collector_wrapper_source"),
            "collector_part_files": manifest.get("collector_part_files", []),
            "source_files": source_files,
            "excluded_surfaces": [
                "workflow-embedded PowerShell",
                "fixtures",
                "harness-only code",
                "operator tooling",
                "staging artifacts",
            ],
        },
        "summary": {
            "parser_mode": parser_mode,
            "source_file_count": len(sources),
            "function_count": len(function_records),
            "nested_function_count": len([item for item in function_records if item["definition_kind"] == "nested"]),
            "reference_count": len(references),
            "dynamic_invocation_site_count": len(dynamic_sites),
            "classification_counts": dict(sorted(classification_counts.items())),
            "coverage_state": "not_collected",
            "validation_success": False,
        },
        "entrypoint_names": sorted(args.entrypoint, key=str.casefold),
        "functions": function_records,
        "dynamic_invocation_sites": dynamic_sites,
        "runtime_lane_coverage": {
            "state": "not_collected",
            "observed_lanes": [],
            "claim": "Runtime absence is not claimed; no suite trace evidence was supplied to this report.",
        },
        "non_claims": list(NON_CLAIMS),
        "outputs": {
            "json": DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown": DEFAULT_MARKDOWN_OUTPUT.as_posix(),
        },
        "validation": {
            "success": False,
            "errors": errors,
            "warnings": warnings,
        },
    }
    if not errors:
        errors.extend(validate_report(report))
    report["validation"]["errors"] = errors
    report["validation"]["success"] = not errors
    report["summary"]["validation_success"] = report["validation"]["success"]
    return report


def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    json_path, json_repo_path = safe_output_path(repo_root, json_output, "function reachability JSON output", ".json")
    markdown_path, markdown_repo_path = safe_output_path(repo_root, markdown_output, "function reachability Markdown output", ".md")
    if json_path.resolve() == markdown_path.resolve():
        raise ReachabilityError("function reachability JSON and Markdown output paths must be different")
    report["outputs"]["json"] = json_repo_path
    report["outputs"]["markdown"] = markdown_repo_path
    write_json(json_path, report)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
