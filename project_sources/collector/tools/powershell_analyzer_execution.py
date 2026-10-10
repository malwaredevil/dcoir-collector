#!/usr/bin/env python3
"""Analyzer command execution and response normalization."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from powershell_analyzer_contract import (
    AnalyzerContractError,
    integer_or_none,
    is_supported_powershell_version,
    normalize_repo_path,
    scalar,
    sha256_text,
)

def make_request(settings_path: Path, target: dict[str, Any]) -> dict[str, Any]:
    return {
        "settings_path": str(settings_path),
        "target": {
            "path": target["path"],
            "absolute_path": target["absolute_path"],
            "analysis_path": target["analysis_path"],
            "category": target["category"],
            "source_type": target["source_type"],
            "sha256": target["sha256"],
        },
    }


def psscriptanalyzer_script() -> str:
    return r"""
$ErrorActionPreference = 'Stop'
$requestJson = [Console]::In.ReadToEnd()
$request = $requestJson | ConvertFrom-Json
if ($env:DCOIR_PSSCRIPTANALYZER_VERSION) {
  Import-Module PSScriptAnalyzer -RequiredVersion $env:DCOIR_PSSCRIPTANALYZER_VERSION -ErrorAction Stop
} else {
  Import-Module PSScriptAnalyzer -ErrorAction Stop
}
$module = Get-Module PSScriptAnalyzer
# Preserve the legacy all-built-in diagnostic coverage, including Error findings.
# Add the six governed policy rules without emitting duplicate findings.
$legacyFindings = @(Invoke-ScriptAnalyzer -Path $request.target.analysis_path -ErrorAction Stop)
$policyFindings = @(Invoke-ScriptAnalyzer -Path $request.target.analysis_path -Settings $request.settings_path -ErrorAction Stop)
$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$findings = @(
  foreach ($finding in @($legacyFindings) + @($policyFindings)) {
    $key = @([string]$finding.ScriptPath, [string]$finding.Line, [string]$finding.Column, [string]$finding.RuleName, [string]$finding.Severity, [string]$finding.Message) -join [char]0
    if (-not $seen.Add($key)) { continue }
    $recommendedFix = ''
    if ($finding.PSObject.Properties.Name -contains 'SuggestedCorrections' -and $finding.SuggestedCorrections) {
      $recommendedFix = ($finding.SuggestedCorrections | Select-Object -First 1 | ForEach-Object { $_.Description }) -join '; '
    }
    [pscustomobject]@{
      path = $finding.ScriptPath
      line = $finding.Line
      column = $finding.Column
      symbol = $finding.ScriptName
      rule_name = $finding.RuleName
      severity = $finding.Severity.ToString()
      observed_problem = $finding.Message
      recommended_fix = $recommendedFix
    }
  }
)
[pscustomobject]@{
  analyzer_name = 'PSScriptAnalyzer'
  analyzer_version = $module.Version.ToString()
  powershell_engine = $PSVersionTable.PSEdition
  powershell_version = $PSVersionTable.PSVersion.ToString()
  target_path = $request.target.path
  analyzed = $true
  findings = $findings
} | ConvertTo-Json -Depth 8
"""


def analyzer_command(args: argparse.Namespace) -> tuple[list[str], str]:
    if args.analyzer_command:
        return args.analyzer_command, "custom_json_command"
    pwsh = shutil.which("pwsh")
    if not pwsh:
        raise AnalyzerContractError("analyzer tool missing: pwsh was not found on PATH")
    return [pwsh, "-NoProfile", "-NonInteractive", "-Command", psscriptanalyzer_script()], "psscriptanalyzer_pwsh"


def run_analyzer_command(
    command: list[str],
    command_kind: str,
    request: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AnalyzerContractError(f"analyzer tool missing: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AnalyzerContractError(
            f"analyzer timeout after {timeout_seconds} seconds for {request['target']['path']}"
        ) from exc
    except OSError as exc:
        raise AnalyzerContractError(f"analyzer launch failed for {request['target']['path']}: {exc}") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()[-2000:]
        raise AnalyzerContractError(
            f"analyzer crash for {request['target']['path']} with exit {completed.returncode}: {stderr}"
        )
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AnalyzerContractError(f"analyzer returned invalid JSON for {request['target']['path']}: {exc}") from exc
    if not isinstance(response, dict):
        raise AnalyzerContractError(f"analyzer response for {request['target']['path']} is not a JSON object")
    response["command_kind"] = command_kind
    return response

def normalize_finding(raw: dict[str, Any], target: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    path = normalize_repo_path(
        scalar(raw.get("path") or raw.get("ScriptPath") or target["path"]),
        repo_root,
        target,
    )
    finding = {
        "path": path,
        "line": integer_or_none(raw.get("line") or raw.get("Line")),
        "column": integer_or_none(raw.get("column") or raw.get("Column")),
        "symbol": scalar(raw.get("symbol") or raw.get("ScriptName") or raw.get("Extent")),
        "rule_name": scalar(raw.get("rule_name") or raw.get("RuleName") or raw.get("rule") or raw.get("check_name")),
        "severity": scalar(raw.get("severity") or raw.get("Severity")),
        "observed_problem": scalar(raw.get("observed_problem") or raw.get("Message") or raw.get("message")),
        "recommended_fix": scalar(raw.get("recommended_fix") or raw.get("RecommendedFix") or raw.get("recommendation")),
        "target_path": target["path"],
        "target_sha256": target["sha256"],
        "suppressed_by_baseline": False,
    }
    missing = [
        key
        for key in ("path", "rule_name", "severity", "observed_problem")
        if not finding[key]
    ]
    if missing:
        raise AnalyzerContractError(
            f"{target['path']}: analyzer finding is missing required normalized fields: {', '.join(missing)}"
        )
    fingerprint_payload = {
        "path": finding["path"],
        "line": finding["line"],
        "column": finding["column"],
        "rule_name": finding["rule_name"],
        "severity": finding["severity"],
        "observed_problem": finding["observed_problem"],
        "target_sha256": finding["target_sha256"],
    }
    finding["fingerprint"] = sha256_text(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")))
    return finding


def normalize_response(response: dict[str, Any], target: dict[str, Any], repo_root: Path, minimum_ps_version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if response.get("analyzed") is not True or response.get("skipped") is True:
        reason = response.get("skipped_reason") or response.get("reason") or "no reason supplied"
        raise AnalyzerContractError(f"{target['path']}: intended analyzer target was skipped: {reason}")

    analyzer_name = scalar(response.get("analyzer_name") or response.get("AnalyzerName"))
    analyzer_version = scalar(response.get("analyzer_version") or response.get("AnalyzerVersion"))
    powershell_engine = scalar(response.get("powershell_engine") or response.get("PowerShellEngine"))
    powershell_version = scalar(response.get("powershell_version") or response.get("PowerShellVersion"))
    if not analyzer_name:
        raise AnalyzerContractError(f"{target['path']}: analyzer response missing analyzer_name")
    if not analyzer_version:
        raise AnalyzerContractError(f"{target['path']}: analyzer response missing analyzer_version")
    if not powershell_engine:
        raise AnalyzerContractError(f"{target['path']}: analyzer response missing powershell_engine")
    if not powershell_version:
        raise AnalyzerContractError(f"{target['path']}: analyzer response missing powershell_version")
    if not is_supported_powershell_version(powershell_version, minimum_ps_version):
        raise AnalyzerContractError(
            f"{target['path']}: unsupported PowerShell version {powershell_version}; minimum is {minimum_ps_version}"
        )

    response_target = scalar(response.get("target_path") or response.get("TargetPath"))
    if not response_target:
        raise AnalyzerContractError(f"{target['path']}: analyzer response missing target_path")
    if normalize_repo_path(response_target, repo_root, target) != target["path"]:
        raise AnalyzerContractError(
            f"{target['path']}: analyzer response target mismatch: {response_target}"
        )

    raw_findings = response.get("findings", [])
    if raw_findings is None:
        raw_findings = []
    if not isinstance(raw_findings, list):
        raise AnalyzerContractError(f"{target['path']}: analyzer findings must be a list")
    findings: list[dict[str, Any]] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            raise AnalyzerContractError(f"{target['path']}: analyzer finding is not a JSON object")
        findings.append(normalize_finding(raw, target, repo_root))

    metadata = {
        "target_path": target["path"],
        "analyzer_name": analyzer_name,
        "analyzer_version": analyzer_version,
        "powershell_engine": powershell_engine,
        "powershell_version": powershell_version,
        "command_kind": response.get("command_kind"),
        "finding_count": len(findings),
    }
    return metadata, findings
