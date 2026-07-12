#!/usr/bin/env python3
"""Validate #263 PowerShell rule-to-risk fixture evidence.

Compatibility facade for the connector-sized rule-risk fixture helper modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import powershell_rule_risk_fixtures_common as _common
import powershell_rule_risk_fixtures_contract as _contract
import powershell_rule_risk_fixtures_runner as _runner
from powershell_rule_risk_fixtures_cli import parse_args as _parse_args, main as _main
from powershell_rule_risk_fixtures_common import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MANIFEST,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_MATRIX,
    DEFAULT_MATRIX_MARKDOWN_OUTPUT,
    FIXTURE_ROOT,
    ISSUE_NUMBER,
    MANIFEST_SCHEMA_VERSION,
    MATRIX_SCHEMA_VERSION,
    MINIMUM_RISK_CLASSES,
    RuleRiskFixtureError,
    SCHEMA_VERSION,
    analyzer,
    is_relative_to,
    path_contains_symlink,
    read_json,
    relpath,
    repo_relative_path_or_error,
    require_string,
    require_string_list,
    safe_fixture_path,
    safe_relpath,
    scalar,
    sha256_file,
    validate_fixture_root,
)
from powershell_rule_risk_fixtures_contract import validate_manifest, validate_matrix
from powershell_rule_risk_fixtures_findings import finding, fixture_findings, run_fixture_analyzer
from powershell_rule_risk_fixtures_powershell import (
    context_has_skip_success_trigger,
    executable_here_string_start,
    line_assignment_value,
    line_has_assignment_value,
    line_has_executable_exit_zero,
    line_in_result_object,
    line_number_for,
    line_without_powershell_comments_or_strings,
    line_without_powershell_line_comment,
    local_failure_action,
    local_result_context,
    local_result_context_bounds,
    parse_powershell_scalar_value,
    position_in_spans,
    powershell_code_lines,
    powershell_code_lines_preserving_positions,
    pscustomobject_end_index,
    pscustomobject_start_column,
    result_object_bounds_for_index,
    string_spans,
    unquoted_token_index,
)
from powershell_rule_risk_fixtures_reporting import (
    ensure_distinct_output_paths,
    mark_output_failure,
    render_matrix_markdown,
    render_report_markdown,
    rewrite_failed_report_outputs,
    write_outputs as _write_outputs,
)
from powershell_rule_risk_fixtures_runner import (
    expected_match,
    inventory_surface,
    validate_fixture_results,
    wrapper_args,
    write_temp_inventory,
)


def _sync_compat_overrides() -> None:
    _common.sha256_file = sha256_file
    _contract.sha256_file = sha256_file
    _runner.sha256_file = sha256_file


def build_fixture_report(args: Any) -> tuple[dict[str, Any], list[str], list[str], dict[str, Any]]:
    _sync_compat_overrides()
    return _runner.build_fixture_report(args)


def write_outputs(
    repo_root: Path,
    report: dict[str, Any],
    matrix: dict[str, Any],
    json_output: Path,
    markdown_output: Path,
    matrix_markdown_output: Path,
) -> None:
    _sync_compat_overrides()
    return _write_outputs(repo_root, report, matrix, json_output, markdown_output, matrix_markdown_output)


def parse_args() -> Any:
    return _parse_args()


def main() -> int:
    _sync_compat_overrides()
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
