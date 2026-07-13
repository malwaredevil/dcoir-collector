#!/usr/bin/env python3
"""Contracts and constants for PowerShell review-assist reports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dcoir_powershell_review_assist_report_v1"


ISSUE_NUMBER = 268


PARENT_ISSUE_NUMBER = 260


DEFAULT_SCHEMA_PATH = Path("project_sources/collector/powershell_review_assist_report.schema.json")


DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_review_assist_report.json")


DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_review_assist_report.md")


DEFAULT_SURFACE_INVENTORY = Path("project_sources/collector/powershell_surface_inventory.json")


DEFAULT_RULE_RISK_REPORT = Path("project_sources/collector/powershell_rule_risk_fixture_report.json")


DEFAULT_RULE_RISK_MATRIX = Path("project_sources/collector/powershell_rule_risk_matrix.json")


DEFAULT_CUSTOM_REPORT = Path("project_sources/collector/powershell_custom_check_report.json")


DEFAULT_ASSEMBLY_PARITY_REPORT = Path("project_sources/collector/powershell_assembly_parity_report.json")


DEFAULT_GOVERNANCE_REPORT = Path("project_sources/collector/powershell_finding_governance_report.json")


DEFAULT_ENGINE_BOUNDARY_REPORT = Path("project_sources/collector/powershell_engine_pester_boundary_report.json")


DEFAULT_ANALYZER_REPORT = Path("project_sources/collector/powershell_analyzer_report.json")


DEFAULT_FUNCTION_REACHABILITY_REPORT = Path("project_sources/collector/powershell_function_reachability_report.json")


SCHEMA_VERSIONS = {
    "surface_inventory": "dcoir_powershell_surface_inventory_v1",
    "rule_risk_report": "dcoir_powershell_rule_risk_fixture_report_v1",
    "rule_risk_matrix": "dcoir_powershell_rule_risk_matrix_v1",
    "custom_report": "dcoir_powershell_custom_check_report_v1",
    "assembly_parity_report": "dcoir_powershell_assembly_parity_report_v1",
    "governance_report": "dcoir_powershell_finding_governance_report_v1",
    "engine_boundary_report": "dcoir_powershell_engine_pester_boundary_report_v1",
    "analyzer_report": "dcoir_powershell_analyzer_report_v1",
    "function_reachability_report": "dcoir_powershell_function_reachability_report_v1",
}


SOURCE_ISSUES = {
    "surface_inventory": 261,
    "analyzer_report": 262,
    "rule_risk_report": 263,
    "rule_risk_matrix": 263,
    "custom_report": 264,
    "assembly_parity_report": 265,
    "governance_report": 266,
    "engine_boundary_report": 267,
    "function_reachability_report": 306,
}


SOURCE_LABELS = {
    "surface_inventory": "#261 surface inventory",
    "rule_risk_report": "#263 rule-risk fixture report",
    "rule_risk_matrix": "#263 rule-risk matrix companion",
    "custom_report": "#264 DCOIR custom-check report",
    "assembly_parity_report": "#265 assembly parity report",
    "governance_report": "#266 finding governance report",
    "engine_boundary_report": "#267 engine/Pester boundary report",
    "analyzer_report": "#262 optional PowerShell analyzer report",
    "function_reachability_report": "#306 function reachability report",
}


REQUIRED_SOURCE_KEYS = (
    "surface_inventory",
    "rule_risk_report",
    "rule_risk_matrix",
    "custom_report",
    "assembly_parity_report",
    "governance_report",
    "engine_boundary_report",
    "function_reachability_report",
)


SOURCE_PATH_PREFIXES = (
    ".github/",
    "compiled_runtime/",
    "knowledge/",
    "project_sources/",
)


NON_CLAIMS = [
    "No workflow YAML was changed by #268.",
    "No SARIF file is generated or uploaded by #268.",
    "No GitHub code-scanning alert or required-check behavior is enabled by #268.",
    "No workflow artifact retention behavior is configured by #268.",
    "No Pester result is promoted to blocking static-validation evidence by #268.",
    "No changed-file execution, path-filter behavior, PR-diff coverage, or changed-file gating is claimed by #268.",
    "No live PSScriptAnalyzer evidence is claimed when the #262 analyzer report is absent.",
    "No Windows PowerShell 5.1 runtime validation is claimed by #268.",
    "No #269, #270, PR/workflow readiness, or parent #260 closeability claim is made by #268.",
    "No function deletion readiness or dead-code removal claim is made by #306 reachability reporting.",
]


FUTURE_HANDOFF_CONSUMERS = [
    {
        "issue": 269,
        "consumer": "SARIF decision gate",
        "may_consume": [
            "normalized findings",
            "evidence channel states",
            "missing analyzer evidence",
            "explicit non-claims",
        ],
        "not_claimed_by_268": "SARIF generation, SARIF upload, code scanning, or required-check readiness.",
    },
    {
        "issue": 270,
        "consumer": "workflow/local integration planning",
        "may_consume": [
            "local report artifact names",
            "source report contract",
            "warning carry-forward behavior",
            "handoff metadata",
        ],
        "not_claimed_by_268": "workflow mutation, artifact retention, or changed-file gating.",
    },
]


class ReviewAssistError(RuntimeError):
    """Raised for fail-closed review-assist validation errors."""


@dataclass(frozen=True)
class SourceContract:
    key: str
    path: Path
    required: bool
    expected_schema: str
    require_validation_success: bool
    finding_count_keys: tuple[str, ...] = ("finding_count", "observed_finding_count")


SOURCE_CONTRACTS = {
    "surface_inventory": SourceContract(
        "surface_inventory",
        DEFAULT_SURFACE_INVENTORY,
        True,
        SCHEMA_VERSIONS["surface_inventory"],
        True,
        (),
    ),
    "rule_risk_report": SourceContract(
        "rule_risk_report",
        DEFAULT_RULE_RISK_REPORT,
        True,
        SCHEMA_VERSIONS["rule_risk_report"],
        True,
    ),
    "rule_risk_matrix": SourceContract(
        "rule_risk_matrix",
        DEFAULT_RULE_RISK_MATRIX,
        True,
        SCHEMA_VERSIONS["rule_risk_matrix"],
        False,
        (),
    ),
    "custom_report": SourceContract(
        "custom_report",
        DEFAULT_CUSTOM_REPORT,
        True,
        SCHEMA_VERSIONS["custom_report"],
        True,
    ),
    "assembly_parity_report": SourceContract(
        "assembly_parity_report",
        DEFAULT_ASSEMBLY_PARITY_REPORT,
        True,
        SCHEMA_VERSIONS["assembly_parity_report"],
        True,
        (),
    ),
    "governance_report": SourceContract(
        "governance_report",
        DEFAULT_GOVERNANCE_REPORT,
        True,
        SCHEMA_VERSIONS["governance_report"],
        True,
    ),
    "engine_boundary_report": SourceContract(
        "engine_boundary_report",
        DEFAULT_ENGINE_BOUNDARY_REPORT,
        True,
        SCHEMA_VERSIONS["engine_boundary_report"],
        True,
        (),
    ),
    "analyzer_report": SourceContract(
        "analyzer_report",
        DEFAULT_ANALYZER_REPORT,
        False,
        SCHEMA_VERSIONS["analyzer_report"],
        True,
    ),
    "function_reachability_report": SourceContract(
        "function_reachability_report",
        DEFAULT_FUNCTION_REACHABILITY_REPORT,
        True,
        SCHEMA_VERSIONS["function_reachability_report"],
        True,
        ("function_count",),
    ),
}


__all__ = ['SCHEMA_VERSION', 'ISSUE_NUMBER', 'PARENT_ISSUE_NUMBER', 'DEFAULT_SCHEMA_PATH', 'DEFAULT_JSON_OUTPUT', 'DEFAULT_MARKDOWN_OUTPUT', 'DEFAULT_SURFACE_INVENTORY', 'DEFAULT_RULE_RISK_REPORT', 'DEFAULT_RULE_RISK_MATRIX', 'DEFAULT_CUSTOM_REPORT', 'DEFAULT_ASSEMBLY_PARITY_REPORT', 'DEFAULT_GOVERNANCE_REPORT', 'DEFAULT_ENGINE_BOUNDARY_REPORT', 'DEFAULT_ANALYZER_REPORT', 'DEFAULT_FUNCTION_REACHABILITY_REPORT', 'SCHEMA_VERSIONS', 'SOURCE_ISSUES', 'SOURCE_LABELS', 'REQUIRED_SOURCE_KEYS', 'SOURCE_PATH_PREFIXES', 'NON_CLAIMS', 'FUTURE_HANDOFF_CONSUMERS', 'ReviewAssistError', 'SourceContract', 'SOURCE_CONTRACTS']
