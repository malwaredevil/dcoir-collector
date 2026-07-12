#!/usr/bin/env python3
"""Policy checks for DCOIR collector runtime-package validation."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from validate_dcoir_runtime_behavior import (
    run_json_policy_behavior_tests,
    run_state_recursion_behavior_tests,
    run_suspicious_process_parent_context_behavior_tests,
)
from validate_dcoir_runtime_common import (
    add_missing_errors,
    extract_function_body,
    find_convert_to_json_calls,
    get_combined_source_text,
    load_manifest_source_texts,
)

PART02_SOURCE_PATHS = (
    'project_sources/collector/source/parts/DCOIR_Collector.02A_Baseline_Collection_And_Reports.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.02B_Baseline_Collection_And_Reports.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.02C_Baseline_Collection_And_Reports.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.02D1A_Baseline_Collection_And_Reports.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.02D1B_Baseline_Collection_And_Reports.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.02D2_Baseline_Collection_And_Reports.ps1',
)

MAIN_ENTRY_SOURCE_PATHS = (
    'project_sources/collector/source/parts/DCOIR_Collector.05A1_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05A2_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05A3_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05B_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05C_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05_Main_Entry.ps1',
)

PARALLEL_RUNTIME_PART_RELS = (
    'project_sources/collector/source/parts/DCOIR_Collector.04D1_Bounded_Parallel_Runtime.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04D2_Bounded_Parallel_Runtime.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04D3_Bounded_Parallel_Runtime.ps1',
)

PARALLEL_WORKER_SCRIPT_REL = 'project_sources/collector/source/parts/DCOIR_Collector.04D3_Bounded_Parallel_Runtime.ps1'

MANIFEST_HELPER_PART_RELS = (
    'project_sources/collector/source/parts/DCOIR_Collector.04G1_PR186_External_Review_Fixes.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04G2_PR186_External_Review_Fixes.ps1',
)


def get_parallel_runtime_source_text(source_text_by_rel: Dict[str, str]) -> str:
    return '\n'.join(source_text_by_rel.get(rel, '') for rel in PARALLEL_RUNTIME_PART_RELS)


def get_part02_source_text(source_text_by_rel: Dict[str, str]) -> str:
    return '\n'.join(source_text_by_rel.get(rel, '') for rel in PART02_SOURCE_PATHS)


def get_main_entry_source_text(source_text_by_rel: Dict[str, str]) -> str:
    return '\n'.join(source_text_by_rel.get(rel, '') for rel in MAIN_ENTRY_SOURCE_PATHS)


def get_manifest_helper_source_text(source_text_by_rel: Dict[str, str]) -> str:
    return '\n'.join(source_text_by_rel.get(rel, '') for rel in MANIFEST_HELPER_PART_RELS)


def validate_json_serialization_policy(source_dir: Path, manifest: Dict, checks: Dict[str, object], errors: List[str]) -> None:
    out: Dict[str, object] = {}
    checks['json_serialization_policy'] = out
    texts = load_manifest_source_texts(source_dir, manifest)
    collector = get_combined_source_text(texts)
    reports = get_part02_source_text(texts)
    parallel = get_parallel_runtime_source_text(texts)
    manifest_text = get_manifest_helper_source_text(texts)
    for function_name in ('Add-CollectorJsonEllipsisPaths', 'Get-CollectorJsonEllipsisPathSet', 'Add-CollectorJsonDepthRiskPaths', 'Get-CollectorJsonDepthRiskPathSet', 'Convert-ToCollectorJsonText'):
        out[f'{function_name}_present'] = bool(extract_function_body(collector, function_name))
        if not out[f'{function_name}_present']:
            errors.append(f'collector JSON serialization helper is missing: {function_name}')
    body = extract_function_body(collector, 'Convert-ToCollectorJsonText')
    json_helper_rel = next((rel for rel, text in texts.items() if extract_function_body(text, 'Convert-ToCollectorJsonText')), '')
    out.update({
        'shared_helper_default_depth_20': '[int]$Depth = 20' in body,
        'shared_helper_checks_source_depth_risks': 'Get-CollectorJsonDepthRiskPathSet -InputObject $InputObject -MaxDepth $Depth' in body,
        'shared_helper_parses_emitted_json': 'ConvertFrom-Json -ErrorAction Stop' in body,
        'shared_helper_compares_source_ellipsis_paths': '$sourceEllipsis.ContainsKey($_)' in body,
        'shared_helper_records_collector_error': 'Add-CollectorError $message' in body,
        'shared_helper_can_throw': 'if ($ThrowOnTruncation) { throw $message }' in body,
        'save_state_uses_shared_helper': "Convert-ToCollectorJsonText -InputObject $State -Label 'state.json' -ThrowOnTruncation" in collector,
        'step_log_uses_shared_helper': "Convert-ToCollectorJsonText -InputObject $obj -Compress -Label 'execution step JSONL'" in collector,
        'safe_json_uses_shared_helper': "Convert-ToCollectorJsonText -InputObject $InputObject -Label 'safe JSON artifact' -AppendNewline -ThrowOnTruncation" in reports,
        'manifest_uses_shared_helper': "Convert-ToCollectorJsonText -InputObject $manifest -Label 'manifest JSON' -ThrowOnTruncation" in manifest_text,
        'worker_uses_depth_20': '$workerJson = $workerResult | ConvertTo-Json -Depth 20 -ErrorAction Stop' in parallel,
        'worker_parses_and_checks_sentinel': 'ConvertFrom-Json -ErrorAction Stop' in parallel and 'Test-WorkerJsonContainsEllipsisSentinel' in parallel and 'Parallel worker result JSON' in parallel,
    })
    out['shared_helper_behavior_tests'] = run_json_policy_behavior_tests(source_dir, manifest)
    add_missing_errors('collector JSON serialization policy check failed: ', out, [
        'shared_helper_default_depth_20', 'shared_helper_checks_source_depth_risks', 'shared_helper_parses_emitted_json',
        'shared_helper_compares_source_ellipsis_paths', 'shared_helper_records_collector_error', 'shared_helper_can_throw',
        'save_state_uses_shared_helper', 'step_log_uses_shared_helper', 'safe_json_uses_shared_helper',
        'manifest_uses_shared_helper', 'worker_uses_depth_20', 'worker_parses_and_checks_sentinel',
    ], errors)
    if out['shared_helper_behavior_tests']['status'] == 'failed':
        errors.append('collector JSON serialization policy behavior tests failed')
    approved_raw_calls = {
        (json_helper_rel, '$json = $InputObject | ConvertTo-Json @jsonArgs'),
        (PARALLEL_WORKER_SCRIPT_REL, '$workerJson = $workerResult | ConvertTo-Json -Depth 20 -ErrorAction Stop'),
    }
    raw_calls: List[Dict[str, object]] = []
    unapproved: List[Dict[str, object]] = []
    for rel, text in texts.items():
        for row in find_convert_to_json_calls(rel, text):
            raw_calls.append(row)
            if (rel, row['text']) not in approved_raw_calls:
                unapproved.append(row)
    out['raw_convert_to_json_calls'] = raw_calls
    out['raw_convert_to_json_detector'] = 'broad_unqualified_or_module_qualified_command_scan_with_comment_stripping'
    out['unapproved_raw_convert_to_json_calls'] = unapproved
    out['unapproved_raw_convert_to_json_absent'] = not unapproved
    if unapproved:
        errors.append('collector source must route JSON serialization through the approved policy helpers; unapproved raw ConvertTo-Json calls: ' + ', '.join(f"{row['path']}:{row['line']}" for row in unapproved))


def validate_state_recursion_policy(source_dir: Path, manifest: Dict, checks: Dict[str, object], errors: List[str]) -> None:
    out: Dict[str, object] = {}
    checks['state_recursion_policy'] = out
    texts = load_manifest_source_texts(source_dir, manifest)
    collector = get_combined_source_text(texts)
    parallel = get_parallel_runtime_source_text(texts)
    main_entry = get_main_entry_source_text(texts)
    converter = extract_function_body(collector, 'Convert-StateObjectToHashtable')
    sentinel = extract_function_body(parallel, 'Test-WorkerJsonContainsEllipsisSentinel')
    out.update({
        'convert_state_object_to_hashtable_present': bool(converter),
        'converter_default_depth_20': '[int]$Depth = 20' in converter,
        'converter_tracks_current_depth': '[int]$CurrentDepth = 0' in converter,
        'converter_tracks_path': "[string]$Path = '$'" in converter,
        'converter_throws_at_depth_limit': 'Convert-StateObjectToHashtable exceeded configured depth {0} at path {1}.' in converter,
        'converter_dictionary_recursion_passes_depth_path': 'Convert-StateObjectToHashtable -InputObject $InputObject[$key] -Depth $Depth -CurrentDepth ($CurrentDepth + 1) -Path $childPath' in converter,
        'converter_enumerable_recursion_passes_depth_path': 'Convert-StateObjectToHashtable -InputObject $item -Depth $Depth -CurrentDepth ($CurrentDepth + 1) -Path $childPath' in converter,
        'converter_property_recursion_passes_depth_path': 'Convert-StateObjectToHashtable -InputObject $prop.Value -Depth $Depth -CurrentDepth ($CurrentDepth + 1) -Path $childPath' in converter,
        'load_state_uses_default_converter_policy': 'Convert-StateObjectToHashtable -InputObject $loaded' in main_entry,
        'worker_sentinel_present': bool(sentinel),
        'worker_sentinel_default_max_depth_25': '[int]$MaxDepth = 25' in sentinel,
        'worker_sentinel_tracks_current_depth': '[int]$CurrentDepth = 0' in sentinel,
        'worker_sentinel_tracks_path': "[string]$Path = '$'" in sentinel,
        'worker_sentinel_throws_at_depth_limit': 'Parallel worker result JSON sentinel scan exceeded configured depth {0} at path {1}.' in sentinel,
        'worker_sentinel_enumerable_recursion_passes_depth_path': 'Test-WorkerJsonContainsEllipsisSentinel -InputObject $item -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1) -Path $childPath' in sentinel,
        'worker_sentinel_property_recursion_passes_depth_path': 'Test-WorkerJsonContainsEllipsisSentinel -InputObject $prop.Value -MaxDepth $MaxDepth -CurrentDepth ($CurrentDepth + 1) -Path $childPath' in sentinel,
    })
    out['state_recursion_behavior_tests'] = run_state_recursion_behavior_tests(source_dir, manifest, sentinel)
    add_missing_errors('collector state recursion policy check failed: ', out, [
        'convert_state_object_to_hashtable_present', 'converter_default_depth_20', 'converter_tracks_current_depth', 'converter_tracks_path',
        'converter_throws_at_depth_limit', 'converter_dictionary_recursion_passes_depth_path', 'converter_enumerable_recursion_passes_depth_path',
        'converter_property_recursion_passes_depth_path', 'load_state_uses_default_converter_policy', 'worker_sentinel_present',
        'worker_sentinel_default_max_depth_25', 'worker_sentinel_tracks_current_depth', 'worker_sentinel_tracks_path',
        'worker_sentinel_throws_at_depth_limit', 'worker_sentinel_enumerable_recursion_passes_depth_path',
        'worker_sentinel_property_recursion_passes_depth_path',
    ], errors)
    if out['state_recursion_behavior_tests']['status'] == 'failed':
        errors.append('collector state recursion policy behavior tests failed')


def validate_suspicious_process_parent_context_policy(source_dir: Path, manifest: Dict, checks: Dict[str, object], errors: List[str]) -> None:
    out: Dict[str, object] = {}
    checks['suspicious_process_parent_context_policy'] = out
    texts = load_manifest_source_texts(source_dir, manifest)
    collector = get_combined_source_text(texts)
    reports = get_part02_source_text(texts)
    convert = extract_function_body(collector, 'Convert-ProcessObjectToText')
    inventory = extract_function_body(collector, 'Get-ProcessInventory')
    suspicious = extract_function_body(collector, 'Get-SuspiciousProcessFindings')
    out.update({
        'convert_process_object_present': bool(convert),
        'process_inventory_present': bool(inventory),
        'suspicious_process_findings_present': bool(suspicious),
        'convert_accepts_process_name_lookup': '[hashtable]$ProcessNameById' in convert,
        'convert_accepts_process_start_lookup': '[hashtable]$ProcessStartTimeById' in convert,
        'parent_process_id_normalized': '$parentProcessId = [int]$Proc.ParentProcessId' in convert,
        'parent_process_name_resolved': '$parentName = [string]$ProcessNameById[$parentProcessId]' in convert,
        'parent_start_time_checked_before_name_resolution': '$parentStartTime = $ProcessStartTimeById[$parentProcessId]' in convert and '$parentPrecedesChild = ([datetime]$parentStartTime -le [datetime]$created)' in convert,
        'inventory_builds_parent_name_map': '$processNameById[[int]$p.ProcessId] = [string]$p.Name' in inventory,
        'inventory_passes_parent_name_map': '-ProcessNameById $processNameById' in inventory,
        'inventory_passes_parent_start_map': '-ProcessStartTimeById $startTimeMap' in inventory,
        'finding_reads_parent_name': '$parentNameValue = [string]$proc.ParentProcessName' in suspicious,
        'name_only_lolbin_pattern_present': '$nameOnlyLolbinPattern' in suspicious,
        'benign_name_only_lolbin_limited_to_common_shells': "$benignNameOnlyLolbinPattern = '^(powershell|pwsh|cmd|wmic)(\\.exe)?$'" in suspicious,
        'wmic_command_line_indicators_present': 'wmic' in suspicious and 'process\\s+call\\s+create' in suspicious and '/node:' in suspicious,
        'known_benign_parent_pattern_present': all(marker in suspicious for marker in ('$knownBenignLolbinParentPattern', 'svchost', 'services', 'trustedinstaller', 'tiworker', 'wuauclt', 'msiexec')),
        'suppresses_only_known_benign_name_only_hits': 'if (-not $isKnownBenignNameOnlyLolbin -or @($reasons).Count -gt 0)' in suspicious,
        'finding_includes_parent_process_id': 'ParentProcessId = $proc.ParentProcessId' in suspicious,
        'finding_includes_parent_process_name': 'ParentProcessName = $proc.ParentProcessName' in suspicious,
        'process_inventory_reports_parent_name': 'Select-Object ProcessId, ParentProcessId, ParentProcessName, Name' in reports,
        'recommendations_include_parent_context': 'parent={0} ({1})' in reports,
    })
    out['parent_context_behavior_tests'] = run_suspicious_process_parent_context_behavior_tests(source_dir, manifest)
    add_missing_errors('collector suspicious-process parent-context policy check failed: ', out, [key for key in out if key != 'parent_context_behavior_tests'], errors)
    if out['parent_context_behavior_tests']['status'] == 'failed':
        errors.append('collector suspicious-process parent-context behavior tests failed')
