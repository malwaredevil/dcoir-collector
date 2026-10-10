#!/usr/bin/env python3
"""Baseline loading and suppression matching for analyzer findings."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from powershell_analyzer_contract import (
    BASELINE_SCHEMA_VERSION,
    AnalyzerContractError,
    read_json,
    safe_relpath,
    scalar,
)

def load_baseline(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    baseline = read_json(path, "PowerShell analyzer baseline")
    if not isinstance(baseline, dict):
        raise AnalyzerContractError("PowerShell analyzer baseline must be a JSON object")
    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise AnalyzerContractError(
            "PowerShell analyzer baseline schema mismatch: "
            f"expected {BASELINE_SCHEMA_VERSION}, got {baseline.get('schema_version')!r}"
        )
    suppressions = baseline.get("suppressions", [])
    if not isinstance(suppressions, list):
        raise AnalyzerContractError("PowerShell analyzer baseline suppressions must be a list")
    seen_suppressions: set[tuple[str, str, str]] = set()
    for suppression in suppressions:
        if not isinstance(suppression, dict):
            raise AnalyzerContractError("PowerShell analyzer baseline suppression must be an object")
        for key in ("path", "rule_name", "reason", "fingerprint"):
            if not scalar(suppression.get(key)).strip():
                raise AnalyzerContractError(f"PowerShell analyzer baseline suppression missing {key}")
        suppression_key = (
            scalar(suppression["path"]),
            scalar(suppression["rule_name"]),
            scalar(suppression["fingerprint"]),
        )
        if suppression_key in seen_suppressions:
            raise AnalyzerContractError(
                "PowerShell analyzer baseline duplicate suppression for "
                f"{suppression_key[0]} {suppression_key[1]} {suppression_key[2]}"
            )
        seen_suppressions.add(suppression_key)
        expected_count = suppression.get("expected_match_count", 1)
        if not isinstance(expected_count, int) or expected_count < 1:
            raise AnalyzerContractError(
                "PowerShell analyzer baseline suppression expected_match_count must be a positive integer"
            )
    return baseline


def apply_baseline(findings: list[dict[str, Any]], baseline: dict[str, Any] | None) -> list[str]:
    if baseline is None:
        return []
    errors: list[str] = []
    for suppression in baseline.get("suppressions", []):
        suppression_path = scalar(suppression["path"])
        suppression_rule = scalar(suppression["rule_name"])
        suppression_fingerprint = scalar(suppression["fingerprint"])
        expected_count = int(suppression.get("expected_match_count", 1))
        matches = [
            finding
            for finding in findings
            if finding["path"] == suppression_path and finding["rule_name"] == suppression_rule
            and finding["fingerprint"] == suppression_fingerprint
        ]
        if any(match.get("severity", "").casefold() == "error" for match in matches):
            errors.append(f"baseline may not suppress Error findings: {suppression_path} {suppression_rule}")
            continue
        if len(matches) != expected_count:
            errors.append(
                "suppressed-rule mismatch: "
                f"{suppression_path} {suppression_rule} {suppression_fingerprint} "
                f"matched {len(matches)} analyzer findings, expected {expected_count}"
            )
            continue
        for finding in matches:
            finding["suppressed_by_baseline"] = True
            finding["baseline_reason"] = suppression["reason"]
    return errors


def baseline_metadata(
    baseline: dict[str, Any] | None,
    baseline_path: Path | None,
    repo_root: Path,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings = findings or []
    return {
        "path": safe_relpath(baseline_path, repo_root) if baseline_path else None,
        "schema_version": baseline.get("schema_version") if baseline else None,
        "suppression_count": len(baseline.get("suppressions", [])) if baseline else 0,
        "matched_suppression_count": len([finding for finding in findings if finding["suppressed_by_baseline"]]),
        "suppression_keys": [
            {
                "path": scalar(suppression.get("path")),
                "rule_name": scalar(suppression.get("rule_name")),
                "fingerprint": scalar(suppression.get("fingerprint")),
                "expected_match_count": suppression.get("expected_match_count", 1),
            }
            for suppression in (baseline.get("suppressions", []) if baseline else [])
        ],
    }
