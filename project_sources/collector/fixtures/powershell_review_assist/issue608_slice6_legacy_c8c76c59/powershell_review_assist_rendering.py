#!/usr/bin/env python3
"""Markdown rendering and schema-contract validation for PowerShell review-assist reports."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from powershell_review_assist_common import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_SCHEMA_PATH,
    FUTURE_HANDOFF_CONSUMERS,
    ISSUE_NUMBER,
    scalar,
)

def artifact_contract() -> dict[str, Any]:
    return {
        "issue": ISSUE_NUMBER,
        "local_artifacts": {
            "schema": DEFAULT_SCHEMA_PATH.as_posix(),
            "json": DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown": DEFAULT_MARKDOWN_OUTPUT.as_posix(),
        },
        "future_handoff_consumers": deepcopy(FUTURE_HANDOFF_CONSUMERS),
        "retention_scope": "local committed report artifacts only; workflow artifact retention remains a later explicit gate",
        "workflow_behavior": "none",
    }

def markdown_table_row(values: list[Any]) -> str:
    return "| " + " | ".join(scalar(value).replace("\n", " ").replace("|", "\\|") for value in values) + " |"

def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    validation = report["validation"]
    lines = [
        "# PowerShell Review-Assist Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: #{report['issue']}",
        f"- Parent issue: #{report['parent_issue']}",
        f"- Validation: `{'pass' if validation['success'] else 'fail'}`",
        f"- Normalized findings: `{summary['normalized_finding_count']}`",
        f"- Optional analyzer state: `{report['evidence_channels']['analyzer']['state']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in (
        "required_source_report_count",
        "required_source_reports_present",
        "optional_source_reports_missing",
        "normalized_finding_count",
        "carried_forward_warning_count",
        "missing_artifact_count",
        "unclaimed_artifact_count",
        "non_claim_count",
    ):
        lines.append(markdown_table_row([key, summary.get(key, 0)]))
    lines.extend(["", "## Source Reports", "", "| Report | Required | Status | Schema | Findings |", "| --- | --- | --- | --- | ---: |"])
    for entry in report["source_reports"]:
        lines.append(
            markdown_table_row(
                [
                    f"#{entry['source_issue']} {entry['path']}",
                    entry["required"],
                    entry["validation_status"],
                    entry.get("schema_version") or "not present",
                    entry.get("finding_count") if entry.get("finding_count") is not None else "",
                ]
            )
        )
    lines.extend(["", "## Evidence Channels", "", "| Channel | State | Key Evidence |", "| --- | --- | --- |"])
    channels = report["evidence_channels"]
    lines.append(markdown_table_row(["analyzer", channels["analyzer"]["state"], channels["analyzer"]["claim"]]))
    lines.append(
        markdown_table_row(
            [
                "deterministic_fixture_analyzer",
                channels["deterministic_fixture_analyzer"]["state"],
                f"{channels['deterministic_fixture_analyzer']['finding_count']} findings; {channels['deterministic_fixture_analyzer'].get('environment_gap')}",
            ]
        )
    )
    lines.append(markdown_table_row(["custom_checks", channels["custom_checks"]["state"], f"{channels['custom_checks']['finding_count']} findings"]))
    lines.append(
        markdown_table_row(
            [
                "assembly_parity",
                channels["assembly_parity"]["state"],
                f"{channels['assembly_parity']['summary'].get('generated_output_count', 0)} generated outputs; {channels['assembly_parity']['summary'].get('parity_status')}",
            ]
        )
    )
    delta = channels["finding_governance"].get("baseline_delta", {})
    lines.append(
        markdown_table_row(
            [
                "finding_governance",
                channels["finding_governance"]["state"],
                f"{delta.get('baseline_record_count', 0)} baseline records; {delta.get('suppression_count', 0)} suppressions",
            ]
        )
    )
    lines.append(
        markdown_table_row(
            [
                "engine_boundary",
                channels["engine_boundary"]["state"],
                f"{channels['engine_boundary']['summary'].get('unclaimed_blocking_output_artifact_count', 0)} unclaimed blocking artifacts",
            ]
        )
    )
    function_counts = channels["function_reachability"].get("classification_counts", {})
    lines.append(
        markdown_table_row(
            [
                "function_reachability",
                channels["function_reachability"]["state"],
                (
                    f"{channels['function_reachability'].get('function_count', 0)} functions; "
                    f"{function_counts.get('literal_referenced', 0)} literal referenced; "
                    f"{function_counts.get('dynamic_invocation_uncertain', 0)} dynamic uncertain; "
                    f"coverage {channels['function_reachability'].get('coverage_state')}"
                ),
            ]
        )
    )
    lines.append(markdown_table_row(["pester_boundary", channels["pester_boundary"]["state"], channels["pester_boundary"]["claim"]]))
    lines.extend(["", "## Findings", "", "| Evidence | Severity | Rule/check | Path | Line | Governance |", "| --- | --- | --- | --- | ---: | --- |"])
    for finding in report["findings"]:
        lines.append(
            markdown_table_row(
                [
                    finding["evidence_kind"],
                    finding["severity"],
                    finding["rule_name"] or finding["check_id"],
                    finding["path"],
                    finding["line"] if finding["line"] is not None else "",
                    finding["governance_classification"],
                ]
            )
        )
    lines.extend(["", "## Inventory Decisions", ""])
    inventory = report["surface_inventory"]
    lines.append(f"- Full-scope inventory mode: `{inventory.get('mode')}`")
    lines.append(f"- Total PowerShell surfaces: `{inventory.get('summary', {}).get('total_surfaces')}`")
    for title, key in (
        ("Excluded Paths", "excluded_paths"),
        ("Reference Paths", "reference_paths"),
        ("Skipped Paths", "skipped_paths"),
    ):
        lines.extend(["", f"### {title}", "", "| Path | Reason |", "| --- | --- |"])
        for item in inventory.get(key, []):
            lines.append(markdown_table_row([item.get("path"), item.get("reason")]))
        if not inventory.get(key):
            lines.append(markdown_table_row(["none", "none reported"]))
    lines.extend(["", "## Baseline And Suppression", ""])
    governance_delta = report["evidence_channels"]["finding_governance"].get("baseline_delta", {})
    lines.append(f"- Baseline records: `{governance_delta.get('baseline_record_count', 0)}`")
    lines.append(f"- Matched baseline records: `{governance_delta.get('matched_baseline_record_count', 0)}`")
    lines.append(f"- Suppressions: `{governance_delta.get('suppression_count', 0)}`")
    lines.append(f"- Matched suppressions: `{governance_delta.get('matched_suppression_count', 0)}`")
    lines.extend(["", "## Source And Generated Parity", ""])
    for item in report["evidence_channels"]["assembly_parity"].get("generated_outputs", []):
        parse = item.get("parse") if isinstance(item.get("parse"), dict) else {}
        parity = item.get("parity") if isinstance(item.get("parity"), dict) else {}
        lines.append(
            f"- `{item.get('path')}`: mapping `{item.get('line_mapping_status')}`, parse `{parse.get('success')}`, parity `{parity.get('status')}`"
        )
    lines.extend(["", "## Warnings, Missing Artifacts, And Non-Claims", ""])
    if report["carried_forward_warnings"]:
        lines.extend(["### Carried Forward Warnings", ""])
        for warning in report["carried_forward_warnings"]:
            lines.append(f"- #{warning['source_issue']} `{warning.get('source_report')}`: {warning['warning']}")
    if report["missing_artifacts"]:
        lines.extend(["", "### Missing Artifacts", ""])
        for item in report["missing_artifacts"]:
            lines.append(f"- #{item['source_issue']} `{item.get('path')}`: {item['reason']}")
    if report["unclaimed_artifacts"]:
        lines.extend(["", "### Unclaimed Artifacts", ""])
        for item in report["unclaimed_artifacts"]:
            lines.append(f"- #{item['source_issue']} `{item.get('path')}`: {item['reason']}")
    lines.extend(["", "### Non-Claims", ""])
    lines.extend(f"- {claim}" for claim in report["non_claims"])
    lines.extend(["", "## Artifact Contract", ""])
    lines.append(f"- JSON: `{report['artifact_contract']['local_artifacts']['json']}`")
    lines.append(f"- Markdown: `{report['artifact_contract']['local_artifacts']['markdown']}`")
    lines.append(f"- Retention scope: {report['artifact_contract']['retention_scope']}")
    lines.extend(["", "## Validation", ""])
    if validation["errors"]:
        lines.extend(["### Errors", ""])
        lines.extend(f"- {error}" for error in validation["errors"])
    if validation["warnings"]:
        lines.extend(["### Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    return "\n".join(lines) + "\n"

def validate_markdown_parity(report: dict[str, Any], markdown: str) -> list[str]:
    errors: list[str] = []
    required_fragments = [
        str(report["summary"]["normalized_finding_count"]),
        report["evidence_channels"]["analyzer"]["state"],
        report["artifact_contract"]["local_artifacts"]["json"],
        "No workflow YAML was changed by #268.",
    ]
    required_fragments.extend(entry["path"] for entry in report["source_reports"])
    for finding in report["findings"]:
        required_fragments.append(finding["path"])
        required_fragments.append(finding["governance_classification"])
    for item in report["surface_inventory"].get("excluded_paths", []):
        required_fragments.append(item["path"])
    for item in report["surface_inventory"].get("reference_paths", []):
        required_fragments.append(item["path"])
    for warning in report["carried_forward_warnings"]:
        required_fragments.append(warning["warning"])
    for item in report["missing_artifacts"] + report["unclaimed_artifacts"]:
        required_fragments.append(scalar(item.get("path")))
    for item in report["evidence_channels"]["assembly_parity"].get("generated_outputs", []):
        required_fragments.append(scalar(item.get("path")))
    for fragment in required_fragments:
        text = scalar(fragment)
        if text and text not in markdown:
            errors.append(f"Markdown parity missing fragment: {text}")
    return errors

def schema_type_matches(value: Any, schema_type: Any) -> bool:
    allowed = schema_type if isinstance(schema_type, list) else [schema_type]
    for item in allowed:
        if item == "object" and isinstance(value, dict):
            return True
        if item == "array" and isinstance(value, list):
            return True
        if item == "string" and isinstance(value, str):
            return True
        if item == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if item == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if item == "boolean" and isinstance(value, bool):
            return True
        if item == "null" and value is None:
            return True
    return False

def validate_against_schema_contract(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    if path == "$" and isinstance(value, dict):
        summary = value.get("summary")
        validation = value.get("validation")
        if isinstance(summary, dict) and isinstance(validation, dict):
            summary_success = summary.get("validation_success")
            validation_success = validation.get("success")
            if isinstance(summary_success, bool) and isinstance(validation_success, bool) and summary_success != validation_success:
                errors.append("$.summary.validation_success must match $.validation.success")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']!r}")
    if "type" in schema and not schema_type_matches(value, schema["type"]):
        errors.append(f"{path} type mismatch: expected {schema['type']!r}")
        return errors
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, subschema in properties.items():
                if key in value and isinstance(subschema, dict):
                    errors.extend(validate_against_schema_contract(value[key], subschema, f"{path}.{key}"))
    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path} must contain at least {min_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_against_schema_contract(item, item_schema, f"{path}[{index}]"))
    return errors
