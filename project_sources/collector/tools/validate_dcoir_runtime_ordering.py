#!/usr/bin/env python3
"""Ordering and source-shape checks for runtime package validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from validate_dcoir_runtime_common import (
    add_missing_errors,
    extract_function_body,
    find_function_definitions,
    read_text,
)


MAIN_ENTRY_PART_RELS = (
    'project_sources/collector/source/parts/DCOIR_Collector.05A1_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05A2_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05A3_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05B_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05C_Main_Entry.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.05_Main_Entry.ps1',
)

METADATA_FINALIZATION_PART_RELS = (
    'project_sources/collector/source/parts/DCOIR_Collector.04H1_PR212_Metadata_Finalization_Fixes.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04H2_PR212_Metadata_Finalization_Fixes.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04H3_PR212_Metadata_Finalization_Fixes.ps1',
)

BUNDLE_METADATA_SYNC_PART_RELS = (
    'project_sources/collector/source/parts/DCOIR_Collector.04G1_PR186_External_Review_Fixes.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04G2_PR186_External_Review_Fixes.ps1',
)


def get_main_entry_source_text(source_dir: Path) -> str:
    return '\n'.join(read_text(source_dir / rel) for rel in MAIN_ENTRY_PART_RELS)


def get_metadata_finalization_source_text(source_dir: Path) -> str:
    return '\n'.join(read_text(source_dir / rel) for rel in METADATA_FINALIZATION_PART_RELS)


def get_bundle_metadata_sync_source_text(source_dir: Path) -> str:
    return '\n'.join(read_text(source_dir / rel) for rel in BUNDLE_METADATA_SYNC_PART_RELS)


def validate_unique_function_definitions(source_dir: Path, manifest: Dict, checks: Dict[str, object], errors: List[str]) -> None:
    definitions = find_function_definitions(source_dir, manifest)
    duplicates = {name: rows for name, rows in definitions.items() if len(rows) > 1}
    checks['function_definition_count'] = sum(len(rows) for rows in definitions.values())
    checks['unique_function_count'] = len(definitions)
    checks['duplicate_function_count'] = len(duplicates)
    checks['duplicate_function_names'] = sorted(duplicates)
    checks['duplicate_function_original_names'] = {name: sorted({row['name'] for row in rows}) for name, rows in sorted(duplicates.items())}
    checks['duplicate_function_definitions'] = {name: rows for name, rows in sorted(duplicates.items())}
    if duplicates:
        errors.append('duplicate function definitions are not allowed: ' + ', '.join(sorted(duplicates)))
    if manifest.get('function_override_manifest'):
        errors.append('function_override_manifest is obsolete; collector functions must be defined once')


def validate_collect_metadata_report_write_ordering(source_dir: Path, checks: Dict[str, object], errors: List[str]) -> None:
    text = get_main_entry_source_text(source_dir)
    helper = get_metadata_finalization_source_text(source_dir)
    out: Dict[str, object] = {
        'paths': list(MAIN_ENTRY_PART_RELS),
        'helper_paths': list(METADATA_FINALIZATION_PART_RELS),
    }
    checks['collect_metadata_report_write_ordering'] = out
    if not text or not helper:
        out['checked'] = False
        errors.append('collect metadata report source/helper is missing')
        return
    markers = {
        'metadata': '$metadataText = New-MetadataReport -State $state -ToolMap $toolMap',
        'write': 'Write-ReportFile -Path $metadataReportPath -Text $metadataText',
        'upload_artifacts': '$uploadArtifacts = New-CollectUploadArtifactsWithLateMetadataReport -State $state -Baseline $baseline',
        'upload_summary': '$state.UploadSummaryPath = $uploadArtifacts.UploadSummaryPath',
        'upload_budget': '$state.UploadBudgetManifestPath = $uploadArtifacts.UploadManifestPath',
        'default_upload_set': '$state.DefaultGeminiUploadSetStatus = $uploadArtifacts.DefaultSetStatus',
        'upload_safe_chunk': '$state.UploadSafeChunkManifestPath = $uploadArtifacts.UploadSafeChunkManifestPath',
        'analyst_overview': '$state.AnalystOverviewPath = New-AnalystOverviewArtifactWithLateMetadataReport -State $state -Baseline $baseline',
        'bundle_name': '$bundleName = ("DCOIR_COLLECT_BUNDLE_{0}_{1}.zip" -f $env:COMPUTERNAME, $RunId)',
        'bundle_path': '$bundlePath = Join-Path $state.BundlesDir $bundleName',
        'collect_bundle': '$state.CollectBundlePath = $bundlePath',
        'manifest': 'New-Manifest -ManifestPath (Join-Path $state.RunRoot "manifest_collect.json")',
        'bundle_call': 'New-BundleZip -BundlesDir $state.BundlesDir -BundleName $bundleName',
    }
    pos = {key: text.find(value) for key, value in markers.items()}
    metadata_positions = [m.start() for m in re.finditer(re.escape(markers['metadata']), text)]
    write_positions = [m.start() for m in re.finditer(re.escape(markers['write']), text)]
    out.update({
        'checked': True,
        'metadata_report_call_count': len(metadata_positions),
        'metadata_report_write_count': len(write_positions),
        'placeholder_metadata_file_absent': 'New-Item -ItemType File -Path $metadataReportPath' not in text,
        'late_bound_upload_builder_used': pos['upload_artifacts'] != -1,
        'late_bound_overview_builder_used': pos['analyst_overview'] != -1,
        'old_upload_builder_not_used_in_collect': 'New-CollectUploadArtifacts -State $state -Baseline $baseline' not in text,
        'old_overview_builder_not_used_in_collect': 'New-AnalystOverviewArtifact -State $state -Baseline $baseline' not in text,
        'late_bound_metadata_manifest_flag': 'metadata_report_late_bound_after_upload_artifacts = $true' in helper,
        'late_bound_recommended_row_flag': 'late_bound_after_upload_artifacts = [bool]$isLateBoundMetadata' in helper,
        'late_bound_metadata_not_budgeted': 'if (-not $isLateBoundMetadata) { $safeTotal += $sizeKB }' in helper,
        'late_bound_metadata_not_resolved': 'if ($pathExists)' in helper and 'Resolve-Path -LiteralPath $pathText' in helper and '$pathText' in helper,
        'overview_includes_late_bound_metadata_path': "($pair.Label -eq 'METADATA_REPORT_PATH')" in helper,
    })
    if len(metadata_positions) != 1:
        errors.append('collect mode must call New-MetadataReport exactly once after late-bound collect fields are populated')
    if len(write_positions) != 1:
        errors.append('collect mode must write the metadata report exactly once')
    if metadata_positions:
        first_metadata = metadata_positions[0]
        for key in ('upload_artifacts', 'upload_summary', 'upload_budget', 'default_upload_set', 'upload_safe_chunk', 'analyst_overview', 'bundle_name', 'bundle_path', 'collect_bundle'):
            out[f'{key}_before_metadata'] = pos[key] != -1 and pos[key] < first_metadata
        out['metadata_before_manifest'] = pos['manifest'] != -1 and first_metadata < pos['manifest']
        out['metadata_before_bundle'] = pos['bundle_call'] != -1 and first_metadata < pos['bundle_call']
    else:
        for key in ('upload_artifacts', 'upload_summary', 'upload_budget_manifest', 'default_upload_set_status', 'upload_safe_chunk_manifest', 'analyst_overview', 'bundle_name', 'bundle_path', 'collect_bundle_path'):
            out[f'{key}_before_metadata'] = False
        out['metadata_before_manifest'] = False
        out['metadata_before_bundle'] = False
    if write_positions:
        out['metadata_write_before_manifest'] = pos['manifest'] != -1 and write_positions[0] < pos['manifest']
        out['metadata_write_before_bundle'] = pos['bundle_call'] != -1 and write_positions[0] < pos['bundle_call']
    else:
        out['metadata_write_before_manifest'] = False
        out['metadata_write_before_bundle'] = False
    out['metadata_write_follows_metadata_call'] = bool(metadata_positions and write_positions and metadata_positions[0] < write_positions[0])
    alias = {
        'upload_budget_manifest_before_metadata': out.get('upload_budget_before_metadata', False),
        'default_upload_set_status_before_metadata': out.get('default_upload_set_before_metadata', False),
        'upload_safe_chunk_manifest_before_metadata': out.get('upload_safe_chunk_before_metadata', False),
        'collect_bundle_path_before_metadata': out.get('collect_bundle_before_metadata', False),
    }
    out.update(alias)
    add_missing_errors('collect metadata report write ordering check failed: ', out, [
        'placeholder_metadata_file_absent', 'late_bound_upload_builder_used', 'late_bound_overview_builder_used',
        'old_upload_builder_not_used_in_collect', 'old_overview_builder_not_used_in_collect',
        'upload_artifacts_before_metadata', 'upload_summary_before_metadata', 'upload_budget_manifest_before_metadata',
        'default_upload_set_status_before_metadata', 'upload_safe_chunk_manifest_before_metadata', 'analyst_overview_before_metadata',
        'bundle_name_before_metadata', 'bundle_path_before_metadata', 'collect_bundle_path_before_metadata',
        'metadata_before_manifest', 'metadata_write_before_manifest', 'metadata_before_bundle', 'metadata_write_before_bundle',
        'metadata_write_follows_metadata_call', 'late_bound_metadata_manifest_flag', 'late_bound_recommended_row_flag',
        'late_bound_metadata_not_budgeted', 'late_bound_metadata_not_resolved', 'overview_includes_late_bound_metadata_path',
    ], errors)


def validate_collect_manifest_bundle_ordering(source_dir: Path, manifest: Dict, checks: Dict[str, object], errors: List[str]) -> None:
    text = get_main_entry_source_text(source_dir)
    out: Dict[str, object] = {'paths': list(MAIN_ENTRY_PART_RELS)}
    checks['collect_manifest_bundle_ordering'] = out
    if not text:
        out['checked'] = False
        errors.append('collect manifest ordering source is missing from main entry parts')
        return
    manifest_marker = 'New-Manifest -ManifestPath (Join-Path $state.RunRoot "manifest_collect.json")'
    bundle_name_marker = '$bundleName = ("DCOIR_COLLECT_BUNDLE_{0}_{1}.zip" -f $env:COMPUTERNAME, $RunId)'
    bundle_path_marker = '$bundlePath = Join-Path $state.BundlesDir $bundleName'
    state_path_marker = '$state.CollectBundlePath = $bundlePath'
    bundle_call_marker = 'New-BundleZip -BundlesDir $state.BundlesDir -BundleName $bundleName'
    manifest_pos = text.find(manifest_marker)
    bundle_call_pos = text.find(bundle_call_marker)
    out.update({
        'checked': True,
        'collect_manifest_call_count': text.count(manifest_marker),
        'collect_bundle_null_present': 'collect_bundle = $null' in text,
        'bundle_name_precomputed_before_manifest': text.find(bundle_name_marker) != -1 and text.find(bundle_name_marker) < manifest_pos,
        'bundle_path_precomputed_before_manifest': text.find(bundle_path_marker) != -1 and text.find(bundle_path_marker) < manifest_pos,
        'state_collect_bundle_path_set_before_manifest': text.find(state_path_marker) != -1 and text.find(state_path_marker) < manifest_pos,
        'manifest_written_before_bundle': manifest_pos != -1 and bundle_call_pos != -1 and manifest_pos < bundle_call_pos,
        'bundle_call_uses_precomputed_name': bundle_call_pos != -1,
        'manifest_in_bundle_inputs': bundle_call_pos != -1 and '$collectManifest' in text[bundle_call_pos:bundle_call_pos + 1200],
    })
    if out['collect_manifest_call_count'] != 1:
        errors.append('collect mode must write manifest_collect.json exactly once before bundle creation')
    if out['collect_bundle_null_present']:
        errors.append('collect mode must not write manifest_collect.json with collect_bundle = $null')
    add_missing_errors('collect manifest/bundle ordering check failed: ', out, [
        'bundle_name_precomputed_before_manifest', 'bundle_path_precomputed_before_manifest', 'state_collect_bundle_path_set_before_manifest',
        'manifest_written_before_bundle', 'bundle_call_uses_precomputed_name', 'manifest_in_bundle_inputs',
    ], errors)


def validate_bundle_metadata_sync_terminates(source_dir: Path, checks: Dict[str, object], errors: List[str]) -> None:
    text = get_bundle_metadata_sync_source_text(source_dir)
    out: Dict[str, object] = {'paths': list(BUNDLE_METADATA_SYNC_PART_RELS)}
    checks['bundle_metadata_sync_error_handling'] = out
    if not text:
        out['checked'] = False
        errors.append('bundle metadata sync helper source is missing')
        return
    sync_body = extract_function_body(text, 'Sync-CollectionMetadataCompanionArtifact')
    bundle_body = extract_function_body(text, 'New-BundleZip')
    catch_match = re.search(r'catch\s*{(?P<body>.*?)^\s*}', sync_body, re.DOTALL | re.MULTILINE)
    catch_body = catch_match.group('body') if catch_match else ''
    out.update({
        'checked': True,
        'sync_function_present': bool(sync_body),
        'bundle_function_present': bool(bundle_body),
        'bundle_invokes_sync': 'Sync-CollectionMetadataCompanionArtifact' in bundle_body,
        'sync_catch_records_collector_error': 'Add-CollectorError' in catch_body,
        'sync_catch_throws_after_error': re.search(r'\bthrow\b', catch_body) is not None,
    })
    if not out['sync_function_present']:
        errors.append('Sync-CollectionMetadataCompanionArtifact function is missing')
    if not out['bundle_function_present']:
        errors.append('New-BundleZip function is missing')
    if not out['bundle_invokes_sync']:
        errors.append('New-BundleZip must synchronize collection metadata companions before compression')
    if not out['sync_catch_records_collector_error']:
        errors.append('metadata companion sync failures must be recorded with Add-CollectorError')
    if not out['sync_catch_throws_after_error']:
        errors.append('metadata companion sync failures must terminate bundle creation after recording the error')
