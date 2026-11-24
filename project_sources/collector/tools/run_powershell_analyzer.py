#!/usr/bin/env python3
"""Run the DCOIR PowerShell analyzer contract.

The wrapper consumes the #261 PowerShell surface inventory, loads the
repository-owned analyzer settings file, runs PSScriptAnalyzer by default, and
normalizes findings into JSON/Markdown reports. It is deliberately strict about
plumbing failures so later workflow integration cannot turn a skipped analyzer
into a green check.
"""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import powershell_analyzer_execution as _execution
from powershell_analyzer_baseline import apply_baseline, baseline_metadata, load_baseline
from powershell_analyzer_cli import build_report, main, parse_args
from collector_tool_path_safety import repo_relative_input_path
from powershell_analyzer_contract import (
    ANALYZABLE_SOURCE_TYPES,
    BASELINE_SCHEMA_VERSION,
    DEFAULT_INVENTORY,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_SETTINGS,
    INVENTORY_SCHEMA_VERSION,
    ISSUE_NUMBER,
    PRIMARY_TARGET_CATEGORIES,
    REQUIRED_POLICY_RULES,
    SCHEMA_VERSION,
    SEVERITY_ORDER,
    AnalyzerContractError,
    integer_or_none,
    is_supported_powershell_version,
    normalize_repo_path,
    read_json,
    read_text,
    relpath,
    safe_relpath,
    scalar,
    severity_at_or_above,
    sha256_file,
    sha256_text,
    version_tuple,
)
from powershell_analyzer_inventory import (
    build_target_sets,
    is_relative_to,
    load_inventory,
    portable_target,
    safe_inventory_path,
    selected_target_paths,
)
from powershell_analyzer_policy import (
    extract_outer_hashtable_body,
    string_literals,
    strip_powershell_comments,
    top_level_assignment_values,
    top_level_hashtable_keys,
    validate_policy,
)
from powershell_analyzer_reporting import empty_report, expected_finding_errors, render_markdown, write_outputs

# Backward compatibility for tests and callers that patch analyzer.shutil.which.
shutil = _execution.shutil
analyzer_command = _execution.analyzer_command
make_request = _execution.make_request
normalize_finding = _execution.normalize_finding
normalize_response = _execution.normalize_response
psscriptanalyzer_script = _execution.psscriptanalyzer_script
run_analyzer_command = _execution.run_analyzer_command

__all__ = [
    "ANALYZABLE_SOURCE_TYPES",
    "BASELINE_SCHEMA_VERSION",
    "DEFAULT_INVENTORY",
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MARKDOWN_OUTPUT",
    "DEFAULT_SETTINGS",
    "INVENTORY_SCHEMA_VERSION",
    "ISSUE_NUMBER",
    "PRIMARY_TARGET_CATEGORIES",
    "REQUIRED_POLICY_RULES",
    "SCHEMA_VERSION",
    "SEVERITY_ORDER",
    "AnalyzerContractError",
    "analyzer_command",
    "apply_baseline",
    "baseline_metadata",
    "build_report",
    "build_target_sets",
    "empty_report",
    "expected_finding_errors",
    "extract_outer_hashtable_body",
    "integer_or_none",
    "is_relative_to",
    "is_supported_powershell_version",
    "load_baseline",
    "load_inventory",
    "main",
    "make_request",
    "normalize_finding",
    "normalize_repo_path",
    "normalize_response",
    "parse_args",
    "portable_target",
    "psscriptanalyzer_script",
    "read_json",
    "read_text",
    "relpath",
    "render_markdown",
    "repo_relative_input_path",
    "run_analyzer_command",
    "safe_inventory_path",
    "safe_relpath",
    "scalar",
    "selected_target_paths",
    "severity_at_or_above",
    "sha256_file",
    "sha256_text",
    "shutil",
    "string_literals",
    "strip_powershell_comments",
    "top_level_assignment_values",
    "top_level_hashtable_keys",
    "validate_policy",
    "version_tuple",
    "write_outputs",
]


if __name__ == "__main__":
    raise SystemExit(main())
