#!/usr/bin/env python3
"""Validate event-text and LogRaw query-bound policy for collector runtime builds.

This stable workflow-facing entrypoint keeps the CLI and report contract intact
while the implementation lives in connector-sized helper modules beside it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from event_text_query_bound_common import (
    COUNT_CAP_PARAMETER_NAMES,
    DIAGNOSTIC_CONTEXT_REL,
    EVENT_TEXT_REVIEW_REL,
    EVENT_WINDOW_OVERRIDES_REL,
    PR186_FIXES_REL,
    REPORT_NAME,
    RETRIEVAL_ACTIONS_REL,
    add_missing_errors,
    extract_function_body,
    extract_function_param_block,
    extract_parenthesized_text,
    extract_powershell_command_spans,
    extract_quoted_switch_case_bodies,
    mask_powershell_strings_and_comments,
    normalize_powershell_command_span,
    powershell_command_count_cap_parameters,
    powershell_command_scan_text,
    powershell_command_span_avoids_count_cap_and_splatting,
    powershell_command_span_detects_count_cap,
    powershell_command_uses_count_cap_parameter,
    powershell_command_uses_splatting,
    powershell_parameter_is_count_cap,
    read_text,
)
from event_text_query_bound_event_text import validate_event_text_query_bound_policy
from event_text_query_bound_lograw import validate_lograw_metadata_truth_policy

__all__ = (
    'COUNT_CAP_PARAMETER_NAMES',
    'DIAGNOSTIC_CONTEXT_REL',
    'EVENT_TEXT_REVIEW_REL',
    'EVENT_WINDOW_OVERRIDES_REL',
    'PR186_FIXES_REL',
    'REPORT_NAME',
    'RETRIEVAL_ACTIONS_REL',
    'add_missing_errors',
    'extract_function_body',
    'extract_function_param_block',
    'extract_parenthesized_text',
    'extract_powershell_command_spans',
    'extract_quoted_switch_case_bodies',
    'mask_powershell_strings_and_comments',
    'normalize_powershell_command_span',
    'powershell_command_count_cap_parameters',
    'powershell_command_scan_text',
    'powershell_command_span_avoids_count_cap_and_splatting',
    'powershell_command_span_detects_count_cap',
    'powershell_command_uses_count_cap_parameter',
    'powershell_command_uses_splatting',
    'powershell_parameter_is_count_cap',
    'read_text',
    'validate_event_text_query_bound_policy',
    'validate_lograw_metadata_truth_policy',
    'validate_policy',
)


def validate_policy(source_dir: Path) -> Dict[str, object]:
    checks: Dict[str, object] = {}
    errors: List[str] = []
    event_text_policy = validate_event_text_query_bound_policy(source_dir)
    lograw_policy = validate_lograw_metadata_truth_policy(source_dir)
    checks['event_text_query_bound_policy'] = event_text_policy['checks']
    checks['lograw_metadata_truth_policy'] = lograw_policy['checks']
    errors.extend(event_text_policy['errors'])
    errors.extend(lograw_policy['errors'])
    return {
        'success': not errors,
        'checks': checks,
        'errors': errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    report = validate_policy(source_dir)
    report['source_dir'] = str(source_dir)
    (output_dir / REPORT_NAME).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
