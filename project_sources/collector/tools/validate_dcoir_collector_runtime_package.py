#!/usr/bin/env python3
"""Validate the DCOIR collector runtime package contract.

This stable workflow-facing entrypoint keeps the existing CLI/report contract
while the implementation lives in connector-sized helper modules beside it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from validate_dcoir_runtime_common import load_manifest, read_text
from validate_dcoir_runtime_ordering import (
    validate_bundle_metadata_sync_terminates,
    validate_collect_manifest_bundle_ordering,
    validate_collect_metadata_report_write_ordering,
    validate_unique_function_definitions,
)
from validate_dcoir_runtime_policies import (
    validate_json_serialization_policy,
    validate_state_recursion_policy,
    validate_suspicious_process_parent_context_policy,
)


def validate_runtime_package(source_dir: Path) -> Dict[str, object]:
    manifest = load_manifest(source_dir)
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, object] = {}

    checks['source_strategy'] = manifest.get('source_strategy')
    if manifest.get('source_strategy') != 'compile_single_runtime_then_package':
        errors.append('source_strategy must be compile_single_runtime_then_package for the collector runtime package')

    required_files = manifest.get('required_files', [])
    missing_required = [rel for rel in required_files if not (source_dir / rel).exists()]
    checks['required_files_present'] = not missing_required
    checks['missing_required_files'] = missing_required
    if missing_required:
        errors.append('missing required files: ' + ', '.join(missing_required))

    collector_parts = manifest.get('collector_part_files', [])
    checks['collector_part_count'] = len(collector_parts)
    missing_parts = [rel for rel in collector_parts if not (source_dir / rel).exists()]
    empty_parts = [rel for rel in collector_parts if (source_dir / rel).exists() and not read_text(source_dir / rel).strip()]
    checks['missing_collector_part_files'] = missing_parts
    checks['empty_collector_part_files'] = empty_parts
    if missing_parts:
        errors.append('collector_part_files references missing files: ' + ', '.join(missing_parts))
    if empty_parts:
        errors.append('collector_part_files references empty files: ' + ', '.join(empty_parts))

    validate_unique_function_definitions(source_dir, manifest, checks, errors)
    validate_collect_metadata_report_write_ordering(source_dir, checks, errors)
    validate_collect_manifest_bundle_ordering(source_dir, manifest, checks, errors)
    validate_bundle_metadata_sync_terminates(source_dir, checks, errors)
    validate_json_serialization_policy(source_dir, manifest, checks, errors)
    validate_state_recursion_policy(source_dir, manifest, checks, errors)
    validate_suspicious_process_parent_context_policy(source_dir, manifest, checks, errors)

    entries = manifest.get('delivery_zip_entries', [])
    expected = {'DCOIR_Collector.ps1.txt'}
    prohibited = {'run_DCOIR_Tests.ps1.txt'}
    actual = {Path(row.get('zip_path', '')).name for row in entries if row.get('zip_path')}
    checks['delivery_entry_count'] = len(entries)
    checks['expected_delivery_names_present'] = expected.issubset(actual)
    checks['actual_delivery_names'] = sorted(actual)
    checks['prohibited_delivery_names_absent'] = actual.isdisjoint(prohibited)
    checks['transport_safe_suffix_required_for_scripts'] = bool(manifest.get('delivery_rules', {}).get('transport_safe_suffix_required_for_scripts'))
    if not entries:
        errors.append('delivery_zip_entries is empty')
    if not checks['expected_delivery_names_present']:
        errors.append('delivery package must include DCOIR_Collector.ps1.txt')
    if not checks['prohibited_delivery_names_absent']:
        errors.append('delivery package must not include harness files: ' + ', '.join(sorted(actual.intersection(prohibited))))
    if checks['transport_safe_suffix_required_for_scripts']:
        non_txt = [row.get('zip_path', '') for row in entries if row.get('zip_path') and not row.get('zip_path', '').endswith('.txt')]
        checks['non_txt_delivery_entries'] = non_txt
        if non_txt:
            errors.append('delivery entries must use transport-safe .txt suffixes: ' + ', '.join(non_txt))

    return {
        'success': not errors,
        'source_dir': str(source_dir),
        'bundle_name': manifest.get('bundle_name'),
        'bundle_version': manifest.get('bundle_version'),
        'checks': checks,
        'warnings': warnings,
        'errors': errors,
    }


def write_report(report: Dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'validate_dcoir_collector_runtime_package_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    report = validate_runtime_package(source_dir)
    write_report(report, output_dir)
    print(json.dumps(report, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
