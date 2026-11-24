#!/usr/bin/env python3
"""Compatibility facade for PowerShell review-assist contracts and sources."""
from __future__ import annotations

from powershell_review_assist_contract import (
    SCHEMA_VERSION,
    ISSUE_NUMBER,
    PARENT_ISSUE_NUMBER,
    DEFAULT_SCHEMA_PATH,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_SURFACE_INVENTORY,
    DEFAULT_RULE_RISK_REPORT,
    DEFAULT_RULE_RISK_MATRIX,
    DEFAULT_CUSTOM_REPORT,
    DEFAULT_ASSEMBLY_PARITY_REPORT,
    DEFAULT_GOVERNANCE_REPORT,
    DEFAULT_ENGINE_BOUNDARY_REPORT,
    DEFAULT_ANALYZER_REPORT,
    DEFAULT_FUNCTION_REACHABILITY_REPORT,
    SCHEMA_VERSIONS,
    SOURCE_ISSUES,
    SOURCE_LABELS,
    REQUIRED_SOURCE_KEYS,
    SOURCE_PATH_PREFIXES,
    NON_CLAIMS,
    FUTURE_HANDOFF_CONSUMERS,
    ReviewAssistError,
    SourceContract,
    SOURCE_CONTRACTS,
)
from powershell_review_assist_sources import (
    scalar,
    slash_path,
    is_windows_drive_path,
    path_has_traversal,
    resolve_repo_path,
    resolve_existing_input_path,
    repo_path_if_safe,
    resolve_report_output_path,
    looks_like_repo_path,
    read_json,
    write_json,
    validate_source_path_aliases,
    validation_state,
    require_object,
    require_list,
    require_field,
    summary_finding_count,
    source_entry,
    load_source,
)

__all__ = ['SCHEMA_VERSION', 'ISSUE_NUMBER', 'PARENT_ISSUE_NUMBER', 'DEFAULT_SCHEMA_PATH', 'DEFAULT_JSON_OUTPUT', 'DEFAULT_MARKDOWN_OUTPUT', 'DEFAULT_SURFACE_INVENTORY', 'DEFAULT_RULE_RISK_REPORT', 'DEFAULT_RULE_RISK_MATRIX', 'DEFAULT_CUSTOM_REPORT', 'DEFAULT_ASSEMBLY_PARITY_REPORT', 'DEFAULT_GOVERNANCE_REPORT', 'DEFAULT_ENGINE_BOUNDARY_REPORT', 'DEFAULT_ANALYZER_REPORT', 'DEFAULT_FUNCTION_REACHABILITY_REPORT', 'SCHEMA_VERSIONS', 'SOURCE_ISSUES', 'SOURCE_LABELS', 'REQUIRED_SOURCE_KEYS', 'SOURCE_PATH_PREFIXES', 'NON_CLAIMS', 'FUTURE_HANDOFF_CONSUMERS', 'ReviewAssistError', 'SourceContract', 'SOURCE_CONTRACTS', 'scalar', 'slash_path', 'is_windows_drive_path', 'path_has_traversal', 'resolve_repo_path', 'resolve_existing_input_path', 'repo_path_if_safe', 'resolve_report_output_path', 'looks_like_repo_path', 'read_json', 'write_json', 'validate_source_path_aliases', 'validation_state', 'require_object', 'require_list', 'require_field', 'summary_finding_count', 'source_entry', 'load_source']
