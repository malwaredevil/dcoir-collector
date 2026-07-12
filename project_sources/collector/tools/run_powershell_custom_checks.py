#!/usr/bin/env python3
"""Run DCOIR-specific static checks for PowerShell validation risk.

Compatibility facade for connector-sized custom-check helper modules.
"""
from __future__ import annotations

from powershell_custom_checks_cli import main, parse_args
from powershell_custom_checks_common import (
    ANALYZABLE_SOURCE_TYPES,
    CHECKS_SCHEMA_VERSION,
    DEFAULT_CHECKS,
    DEFAULT_FIXTURE_MANIFEST,
    DEFAULT_INVENTORY,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_MATRIX,
    FIXTURE_MANIFEST_SCHEMA_VERSION,
    INVENTORY_SCHEMA_VERSION,
    ISSUE_NUMBER,
    MATRIX_SCHEMA_VERSION,
    PARENT_ISSUE_NUMBER,
    REQUIRED_CHECK_FIELDS,
    SCHEMA_VERSION,
    SEVERITY_ORDER,
    CustomCheckError,
    is_absolute_repo_input,
    normalize_repo_path,
    read_json,
    repo_input_metadata,
    repo_relative_cli_path,
    require_string,
    require_string_list,
    safe_fixture_path,
    safe_inventory_path,
    safe_relpath,
    scalar,
    sha256_file,
    sha256_text,
)
from powershell_custom_checks_contract import (
    inventory_targets,
    validate_check_definitions,
    validate_fixture_manifest,
    validate_inventory,
    validate_matrix,
)
from powershell_custom_checks_powershell import (
    code_without_full_line_comments,
    context_has_skip_success_trigger,
    executable_here_string_start,
    line_assignment_value,
    line_has_assignment_value,
    line_has_executable_exit_zero,
    line_in_result_object,
    line_number_for,
    line_window,
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
from powershell_custom_checks_reporting import (
    expected_match,
    render_markdown,
    select_targets,
    severity_at_or_above,
    validate_fixture_results,
    write_outputs,
)
from powershell_custom_checks_rules import (
    CHECK_FUNCTIONS,
    check_analyzer_skip_success,
    check_baseline_suppression,
    check_bounded_event_query,
    check_external_exit,
    check_fail_output,
    check_source_part_drift,
    check_swallowed_catch,
    check_unsafe_wildcard_delete,
    make_finding,
    run_checks_for_text,
)
from powershell_custom_checks_runner import build_report


if __name__ == "__main__":
    raise SystemExit(main())
