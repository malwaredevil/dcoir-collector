#!/usr/bin/env python3
"""Custom PowerShell DCOIR rule detections."""
from __future__ import annotations

import json
import re
from typing import Any

from powershell_custom_checks_common import sha256_text
from powershell_custom_checks_powershell import (
    code_without_full_line_comments,
    context_has_skip_success_trigger,
    line_has_assignment_value,
    line_in_result_object,
    line_number_for,
    line_window,
    local_failure_action,
    local_result_context,
    local_result_context_bounds,
    powershell_code_lines_preserving_positions,
)

def make_finding(
    check: dict[str, Any],
    path: str,
    line: int,
    risk_class: str | None = None,
) -> dict[str, Any]:
    selected_risk = risk_class or check["risk_classes"][0]
    payload = {
        "path": path,
        "line": line,
        "column": 1,
        "symbol": "",
        "check_id": check["id"],
        "rule_name": check["rule_name"],
        "matrix_check_id": check["matrix_check_id"],
        "severity": check["expected_severity"],
        "risk_class": selected_risk,
        "risk_classes": check["risk_classes"],
        "observed_problem": check["intent"],
        "impact": check["failure_impact"],
        "failure_impact": check["failure_impact"],
        "fix": check["recommended_fix"],
        "recommended_fix": check["recommended_fix"],
        "target_surfaces": check["target_surfaces"],
    }
    fingerprint_payload = {
        "path": path,
        "line": line,
        "rule_name": payload["rule_name"],
        "severity": payload["severity"],
        "risk_class": selected_risk,
        "observed_problem": payload["observed_problem"],
    }
    payload["fingerprint"] = sha256_text(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")))
    return payload


def check_analyzer_skip_success(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    code_lines = powershell_code_lines_preserving_positions(lines)
    seen_contexts: set[tuple[int, int]] = set()
    for index, line_text in enumerate(code_lines):
        if not line_has_assignment_value(line_text, {"analyzed": {"$false"}, "skipped": {"$true"}}):
            continue
        context_bounds = local_result_context_bounds(lines, index)
        if context_bounds in seen_contexts:
            continue
        seen_contexts.add(context_bounds)
        context = local_result_context(lines, index)
        if context_has_skip_success_trigger(context) and not local_failure_action(context):
            findings.append(make_finding(check, path, index + 1))
    return findings


def check_external_exit(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    call_operator_target_re = r"(?:\$?[A-Za-z_][\w.]*|\"[^\"]+\"|'[^']+'|\([^)]+\)|[^\s|;&]+)"
    command_re = re.compile(
        rf"^\s*(?:&\s*{call_operator_target_re}|(?:robocopy|cmd|powershell|pwsh|python|git|dotnet)(?:\.exe)?\b|Start-Process\b)",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        if not command_re.search(line):
            continue
        window = line_window(lines, index, after=4)
        if re.search(r"\$LASTEXITCODE|\$\?|\bExitCode\b", window, re.IGNORECASE):
            continue
        findings.append(
            make_finding(check, path, index + 1, "external_command_nonzero_exit_treated_success")
        )
    return findings


def check_fail_output(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    code_lines = powershell_code_lines_preserving_positions(lines)
    seen_contexts: set[tuple[int, int]] = set()
    for index, line_text in enumerate(code_lines):
        if not line_in_result_object(code_lines, index):
            continue
        if not line_has_assignment_value(line_text, {"status": {"fail"}}):
            continue
        context_bounds = local_result_context_bounds(lines, index)
        if context_bounds in seen_contexts:
            continue
        seen_contexts.add(context_bounds)
        context = local_result_context(lines, index)
        if not local_failure_action(context):
            findings.append(make_finding(check, path, index + 1))
    return findings


def check_source_part_drift(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    line = line_number_for(text, r"\bstale-generated\b|\bGeneratedOutputHash\s*=\s*['\"][^'\"]*stale|source[-_ ]part.*drift")
    if line:
        return [make_finding(check, path, line)]
    return []


def check_unsafe_wildcard_delete(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\bRemove-Item\b", line, re.IGNORECASE):
            continue
        if not re.search(r"(?<!\w)-Recurse\b", line, re.IGNORECASE):
            continue
        risky_path = "*" in line or re.search(r"(?<!\w)-(?:Path|LiteralPath)\s+\$|Join-Path", line, re.IGNORECASE)
        if not risky_path:
            continue
        context = "\n".join(lines[max(0, index - 8) : index + 1])
        constrained = re.search(r"\bResolve-Path\b", context, re.IGNORECASE) and re.search(
            r"\bStartsWith\b|\bIsChildPath\b|\bGetFullPath\b",
            context,
            re.IGNORECASE,
        )
        if not constrained:
            findings.append(make_finding(check, path, index + 1))
    return findings


def check_bounded_event_query(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\bGet-WinEvent\b", line, re.IGNORECASE):
            continue
        context = line_window(lines, index, after=2)
        bounded = re.search(
            r"(?<!\w)-(?:FilterHashtable|FilterXPath|MaxEvents)\b|Select-Object\s+(?<!\w)-First\b",
            context,
            re.IGNORECASE,
        )
        if not bounded:
            findings.append(make_finding(check, path, index + 1))
    return findings


def check_baseline_suppression(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    suppression_text = code_without_full_line_comments(text)
    if not re.search(r"Suppression|SuppressMessage|PSScriptAnalyzer|baseline", suppression_text, re.IGNORECASE):
        return []
    broad_line = line_number_for(suppression_text, r"\bpath\s*=\s*['\"]\*['\"]|\brule_name\s*=\s*['\"]PS\*['\"]")
    missing_fields = [
        field
        for field in ("path", "rule_name", "fingerprint", "expected_match_count")
        if not re.search(rf"\b{field}\b", suppression_text, re.IGNORECASE)
    ]
    has_reason = re.search(r"\breason\b|\bjustification\b", suppression_text, re.IGNORECASE)
    if broad_line or missing_fields or not has_reason:
        line = broad_line or line_number_for(suppression_text, r"Suppress|baseline|rule_name|path") or 1
        return [make_finding(check, path, line)]
    return []


def check_swallowed_catch(text: str, path: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for match in re.finditer(r"(?is)\bcatch\b\s*\{(?P<body>.*?)\}", text):
        body = match.group("body")
        fails_closed = re.search(
            r"\bthrow\b|\bexit\s+[1-9]\d*\b|\breturn\s+\$false\b|\bStatus\s*=\s*['\"]FAIL['\"]",
            body,
            re.IGNORECASE,
        )
        if fails_closed:
            continue
        body_start_line = text[: match.start("body")].count("\n") + 1
        write_line = line_number_for(body, r"\bWrite-(?:Warning|Host|Output|Verbose|Information)\b")
        line = body_start_line + write_line - 1 if write_line else text[: match.start()].count("\n") + 1
        findings.append(make_finding(check, path, line))
    return findings


CHECK_FUNCTIONS = {
    "dcoir-analyzer-skip-success": check_analyzer_skip_success,
    "dcoir-check-external-exit": check_external_exit,
    "dcoir-fail-output-must-fail": check_fail_output,
    "dcoir-source-part-drift": check_source_part_drift,
    "dcoir-no-unsafe-wildcard-delete": check_unsafe_wildcard_delete,
    "dcoir-bound-event-query": check_bounded_event_query,
    "dcoir-baseline-fingerprint-bound": check_baseline_suppression,
    "dcoir-no-swallowed-catch": check_swallowed_catch,
}


def run_checks_for_text(text: str, path: str, check_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for check_id, check in check_map.items():
        check_function = CHECK_FUNCTIONS.get(check_id)
        if check_function is None:
            findings.append(
                make_finding(
                    {
                        **check,
                        "intent": f"Custom check {check_id} has no implementation.",
                        "failure_impact": "Missing implementation leaves a documented DCOIR check unenforced.",
                        "recommended_fix": "Add a deterministic local detection function for this check.",
                    },
                    path,
                    1,
                )
            )
            continue
        findings.extend(check_function(text, path, check))
    return findings
