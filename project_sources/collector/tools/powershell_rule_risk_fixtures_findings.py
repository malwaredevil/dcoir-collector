#!/usr/bin/env python3
"""Deterministic fixture finding detection for rule-risk fixture reporting."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from powershell_rule_risk_fixtures_powershell import (
    context_has_skip_success_trigger,
    line_has_assignment_value,
    line_in_result_object,
    line_number_for,
    local_failure_action,
    local_result_context,
    local_result_context_bounds,
    powershell_code_lines_preserving_positions,
)

def finding(path: str, line: int, rule_name: str, severity: str, problem: str, fix: str) -> dict[str, Any]:
    return {
        "path": path,
        "line": line,
        "column": 1,
        "symbol": "",
        "rule_name": rule_name,
        "severity": severity,
        "observed_problem": problem,
        "recommended_fix": fix,
    }

def fixture_findings(text: str, path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    code_lines = powershell_code_lines_preserving_positions(lines)
    invoke_line = line_number_for(text, r"\bInvoke-Expression\b")
    if invoke_line:
        findings.append(
            finding(
                path,
                invoke_line,
                "PSAvoidUsingInvokeExpression",
                "Warning",
                "Dynamic expression execution hides command intent and can execute untrusted input.",
                "Replace Invoke-Expression with explicit command invocation or structured parsing.",
            )
        )
    secure_line = line_number_for(text, r"\bConvertTo-SecureString\b.*(?<!\w)-AsPlainText\b")
    if secure_line:
        findings.append(
            finding(
                path,
                secure_line,
                "PSAvoidUsingConvertToSecureStringWithPlainText",
                "Warning",
                "Plaintext data is converted to SecureString.",
                "Avoid plaintext secret material and use a protected input path.",
            )
        )
    credential_literal_line = line_number_for(
        text,
        r"\[(?:string|securestring|pscredential)\]\s*\$(?:Password|Credential|Secret)\s*=\s*['\"][^'\"]+['\"]"
        r"|\$(?:Password|Credential|Secret)\s*=\s*['\"][^'\"]+['\"]",
    )
    if credential_literal_line:
        findings.append(
            finding(
                path,
                credential_literal_line,
                "PSAvoidUsingPlainTextForPassword",
                "Warning",
                "Credential-like variable is assigned a literal string.",
                "Use a non-secret placeholder or load secret material from a protected source.",
            )
        )
    write_host_line = line_number_for(text, r"\bWrite-Host\b")
    if write_host_line:
        findings.append(
            finding(
                path,
                write_host_line,
                "PSAvoidUsingWriteHost",
                "Warning",
                "Validation output is written only to the host stream.",
                "Write durable output through Write-Output, structured reports, or repo logging helpers.",
            )
        )
    unused_line = line_number_for(text, r"\$Unused[A-Za-z0-9_]*\s*=")
    if unused_line:
        findings.append(
            finding(
                path,
                unused_line,
                "PSUseDeclaredVarsMoreThanAssignments",
                "Warning",
                "Assigned validation state is never consumed.",
                "Remove the unused state or wire it into the validation/report decision.",
            )
        )
    function_line = line_number_for(text, r"^\s*function\s+(?:Remove|Set|Clear|New)-[A-Za-z0-9_-]+")
    if function_line and "SupportsShouldProcess" not in text:
        findings.append(
            finding(
                path,
                function_line,
                "PSUseShouldProcessForStateChangingFunctions",
                "Warning",
                "State-changing function does not declare SupportsShouldProcess.",
                "Add CmdletBinding(SupportsShouldProcess) and guard mutation with ShouldProcess.",
            )
        )
    seen_skip_contexts: set[tuple[int, int]] = set()
    for index, line_text in enumerate(code_lines):
        if not line_has_assignment_value(line_text, {"analyzed": {"$false"}, "skipped": {"$true"}}):
            continue
        context_bounds = local_result_context_bounds(lines, index)
        if context_bounds in seen_skip_contexts:
            continue
        seen_skip_contexts.add(context_bounds)
        context = local_result_context(lines, index)
        if context_has_skip_success_trigger(context) and not local_failure_action(context):
            findings.append(
                finding(
                    path,
                    index + 1,
                    "DCOIR.NoAnalyzerSkipSuccess",
                    "Error",
                    "Analyzer skip state is represented with a success validation state.",
                    "Fail closed when analyzer policy, inventory, target, or command execution is incomplete.",
                )
            )
    external_line = line_number_for(text, r"^\s*&\s*\$?[A-Za-z_][\w.]*|^\s*(?:robocopy\.exe|cmd\.exe|Start-Process)\b")
    if external_line and "$LASTEXITCODE" not in text and "$?" not in text:
        findings.append(
            finding(
                path,
                external_line,
                "DCOIR.CheckExternalCommandExit",
                "Error",
                "External command result is not checked before continuing.",
                "Capture and validate the command exit state immediately.",
            )
        )
    seen_fail_contexts: set[tuple[int, int]] = set()
    for index, line_text in enumerate(code_lines):
        if not line_in_result_object(code_lines, index):
            continue
        if not line_has_assignment_value(line_text, {"status": {"fail"}}):
            continue
        context_bounds = local_result_context_bounds(lines, index)
        if context_bounds in seen_fail_contexts:
            continue
        seen_fail_contexts.add(context_bounds)
        context = local_result_context(lines, index)
        if not local_failure_action(context):
            findings.append(
                finding(
                    path,
                    index + 1,
                    "DCOIR.FailOutputMustFailValidation",
                    "Error",
                    "A FAIL output row can be emitted without a failing process result.",
                    "Tie FAIL rows and reports to a thrown exception, nonzero exit, or failed validation summary.",
                )
            )
    drift_line = line_number_for(text, r"GeneratedOutputHash\s*=\s*['\"][^'\"]*stale|stale-generated")
    if drift_line:
        findings.append(
            finding(
                path,
                drift_line,
                "DCOIR.SourcePartAssemblyDrift",
                "Error",
                "Generated output marker indicates stale source-part assembly.",
                "Regenerate or compare source-part hashes before accepting analyzer evidence.",
            )
        )
    delete_line = line_number_for(text, r"\bRemove-Item\b.*\*.*(?<!\w)-Recurse\b|\bRemove-Item\b.*(?<!\w)-Recurse\b.*\*")
    if delete_line and "Resolve-Path" not in text:
        findings.append(
            finding(
                path,
                delete_line,
                "DCOIR.NoUnsafeWildcardDeletion",
                "Error",
                "Wildcard recursive deletion is not constrained to a resolved controlled root.",
                "Resolve and constrain the cleanup root before deleting, and avoid broad wildcards.",
            )
        )
    event_line = line_number_for(text, r"\bGet-WinEvent\b")
    if event_line:
        event_text = "\n".join(text.splitlines()[event_line - 1 : event_line + 2])
        if not re.search(r"-MaxEvents\b|-FilterHashtable\b|-FilterXPath\b", event_text, re.IGNORECASE):
            findings.append(
                finding(
                    path,
                    event_line,
                    "DCOIR.BoundedEventQueryRequired",
                    "Error",
                    "Event query is not bounded by filter or count cap.",
                    "Use FilterHashtable, explicit windows, MaxEvents, or a bounded Take parameter.",
                )
            )
    baseline_line = line_number_for(text, r"path\s*=\s*['\"]\*['\"]|rule_name\s*=\s*['\"]PS\*['\"]")
    if baseline_line and "fingerprint" not in text.casefold():
        findings.append(
            finding(
                path,
                baseline_line,
                "DCOIR.BaselineSuppressionMustBeFingerprintBound",
                "Error",
                "Baseline suppression is broad and lacks a finding fingerprint.",
                "Bind suppressions to path, rule, fingerprint, expected match count, and reason.",
            )
        )
    catch_match = re.search(r"(?is)\bcatch\b\s*\{(?P<body>.*?)\}", text)
    if catch_match:
        body = catch_match.group("body")
        if not re.search(r"\bthrow\b|\bexit\b", body, re.IGNORECASE):
            prefix = text[: catch_match.start("body")]
            catch_body_start = prefix.count("\n") + 1
            warning_line = line_number_for(body, r"\bWrite-(?:Warning|Host|Output)\b")
            line = catch_body_start + warning_line - 1 if warning_line else text[: catch_match.start()].count("\n") + 1
            findings.append(
                finding(
                    path,
                    line,
                    "DCOIR.NoSwallowedCatch",
                    "Error",
                    "Catch block writes a message but does not fail or rethrow.",
                    "Rethrow, exit nonzero, or return a failed validation state after recording diagnostics.",
                )
            )
    return findings

def run_fixture_analyzer() -> int:
    request = json.loads(sys.stdin.read())
    target = request["target"]
    text = Path(target["analysis_path"]).read_text(encoding="utf-8", errors="ignore")
    target_path = str(target["path"])
    response = {
        "analyzer_name": "DCOIRFixtureAnalyzer",
        "analyzer_version": "1.0.0",
        "powershell_engine": "Core",
        "powershell_version": "7.4.1",
        "target_path": target_path,
        "analyzed": True,
        "findings": fixture_findings(text, target_path),
    }
    sys.stdout.write(json.dumps(response) + "\n")
    return 0
