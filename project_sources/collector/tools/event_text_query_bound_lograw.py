#!/usr/bin/env python3
"""LogRaw metadata-truth policy checks for collector runtime validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from event_text_query_bound_common import EVENT_TEXT_REVIEW_REL, EVENT_WINDOW_OVERRIDES_REL, PR186_FIXES_REL, RETRIEVAL_ACTIONS_REL, add_missing_errors, extract_function_body, extract_function_param_block, extract_powershell_command_spans, extract_quoted_switch_case_bodies, normalize_powershell_command_span, powershell_command_scan_text, powershell_command_uses_count_cap_parameter, powershell_command_uses_splatting, read_text
from event_text_query_bound_lograw_fixture_checks import evaluate_lograw_fixture_checks
from event_text_query_bound_lograw_fixtures import negative_param_fixture_source


def validate_lograw_metadata_truth_policy(source_dir: Path) -> Dict[str, object]:
    # #238 metadata-honesty guard only. If raw EVTX export intentionally gains
    # a count-bounded implementation later, revise these assertions with that design.
    errors: List[str] = []
    review_text = read_text(source_dir / EVENT_TEXT_REVIEW_REL)
    retrieval_text = read_text(source_dir / RETRIEVAL_ACTIONS_REL)
    evtx_text = read_text(source_dir / EVENT_WINDOW_OVERRIDES_REL)
    helper_text = read_text(source_dir / PR186_FIXES_REL)
    checks: Dict[str, object] = {
        'review_path': EVENT_TEXT_REVIEW_REL,
        'retrieval_path': RETRIEVAL_ACTIONS_REL,
        'evtx_path': EVENT_WINDOW_OVERRIDES_REL,
        'helper_path': PR186_FIXES_REL,
        'review_source_present': bool(review_text),
        'retrieval_source_present': bool(retrieval_text),
        'evtx_source_present': bool(evtx_text),
        'helper_source_present': bool(helper_text),
    }

    if not all((review_text, retrieval_text, evtx_text, helper_text)):
        if not review_text:
            errors.append('review action source is missing: ' + EVENT_TEXT_REVIEW_REL)
        if not retrieval_text:
            errors.append('retrieval action source is missing: ' + RETRIEVAL_ACTIONS_REL)
        if not evtx_text:
            errors.append('raw EVTX export source is missing: ' + EVENT_WINDOW_OVERRIDES_REL)
        if not helper_text:
            errors.append('target-details helper source is missing: ' + PR186_FIXES_REL)
        return {'success': False, 'checks': checks, 'errors': errors}

    review_body = extract_function_body(review_text, 'Invoke-EnrichmentAction')
    retrieval_body = extract_function_body(retrieval_text, 'Invoke-EnrichmentAction-Retrieval')
    logtext_blocks = extract_quoted_switch_case_bodies(review_body, 'LogText')
    lograw_blocks = extract_quoted_switch_case_bodies(retrieval_body, 'LogRaw')
    logtext_block = next((block for block in logtext_blocks if 'Get-EventText' in block), '')
    lograw_block = next((block for block in lograw_blocks if 'Export-FilteredEvtx' in block), '')
    target_helper = extract_function_body(helper_text, 'Get-CollectorEventWindowTargetDetails')
    evtx_export = extract_function_body(evtx_text, 'Export-FilteredEvtx')
    evtx_export_param_block = extract_function_param_block(evtx_export)
    negative_param_fixture = extract_function_param_block(extract_function_body(
        negative_param_fixture_source,
        'Export-FilteredEvtx',
    ))

    lograw_target_detail_calls = extract_powershell_command_spans(
        lograw_block,
        'Get-CollectorEventWindowTargetDetails',
    )
    lograw_export_calls = extract_powershell_command_spans(
        lograw_block,
        'Export-FilteredEvtx',
    )
    target_detail_overclaim = any(
        powershell_command_uses_count_cap_parameter(call)
        for call in lograw_target_detail_calls
    )
    target_detail_uses_splatting = any(
        powershell_command_uses_splatting(call)
        for call in lograw_target_detail_calls
    )
    fixture_checks = evaluate_lograw_fixture_checks()
    export_uses_splatting = any(
        powershell_command_uses_splatting(call)
        for call in lograw_export_calls
    )
    export_claims_maxevents = any(
        powershell_command_uses_count_cap_parameter(call)
        or re.search(r'\$MaxEvents\b', powershell_command_scan_text(call), flags=re.IGNORECASE)
        for call in lograw_export_calls
    )
    evtx_param_claims_event_cap = re.search(r'\$(?:MaxEvents|Take)\b', evtx_export_param_block, flags=re.IGNORECASE) is not None
    negative_fixture_detects_event_cap = re.search(r'\$(?:MaxEvents|Take)\b', negative_param_fixture, flags=re.IGNORECASE) is not None
    target_helper_reads_or_exports_events = re.search(r'\b(?:Get-WinEvent|wevtutil|Export-FilteredEvtx)\b', target_helper, flags=re.IGNORECASE) is not None

    checks.update({
        'review_function_present': bool(review_body),
        'retrieval_function_present': bool(retrieval_body),
        'logtext_action_block_present': bool(logtext_block),
        'lograw_action_block_present': bool(lograw_block),
        'target_details_helper_present': bool(target_helper),
        'evtx_export_function_present': bool(evtx_export),
        'evtx_export_param_block_present': bool(evtx_export_param_block),
        'param_block_negative_fixture_detects_maxevents': negative_fixture_detects_event_cap,
        'target_helper_metadata_only_no_event_reader': bool(target_helper) and not target_helper_reads_or_exports_events,
        'lograw_target_details_call_count': len(lograw_target_detail_calls),
        'lograw_target_details_omits_maxevents_overclaim': bool(lograw_target_detail_calls) and not target_detail_overclaim and not target_detail_uses_splatting,
        'lograw_target_details_omits_splatting': bool(lograw_target_detail_calls) and not target_detail_uses_splatting,
        'lograw_target_details_keeps_log_window_ids': 'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId' in normalize_powershell_command_span(lograw_block),
        'lograw_output_initializes_applied_filter_scope': "$rawEvtxFilters = @('LogName','EffectiveEventWindow')" in lograw_block,
        'lograw_output_conditionally_adds_eventids_filter': "if ($EventId -and @($EventId).Count -gt 0) { $rawEvtxFilters += 'EventIds' }" in lograw_block,
        'lograw_output_writes_applied_filter_scope': 'RAW_EVTX_FILTERS=$rawEvtxFiltersText' in lograw_block,
        'lograw_output_states_no_event_count_cap': 'RAW_EVTX_EVENT_COUNT_CAP=NotApplied' in lograw_block,
        'lograw_interpretation_states_no_maxevents_cap': 'MaxEvents does not limit raw EVTX export size.' in lograw_block,
        'lograw_export_call_preserved': 'Export-FilteredEvtx -LogChannel $LogName -WindowHours $Hours -Ids $EventId -OutPath $plannedStagedPath -ScratchDir $sessionLogsDir' in normalize_powershell_command_span(lograw_block),
        'lograw_export_call_omits_maxevents': bool(lograw_export_calls) and not export_claims_maxevents and not export_uses_splatting,
        'lograw_export_call_omits_splatting': bool(lograw_export_calls) and not export_uses_splatting,
        'logtext_still_uses_maxevents_metadata': 'Get-CollectorEventWindowTargetDetails -LogName $LogName -Hours $Hours -Ids $EventId -Take $MaxEvents' in logtext_block,
        'logtext_still_uses_bounded_text_query': 'Get-EventText -Channel $LogName -WindowHours $Hours -Ids $EventId -Take $MaxEvents' in logtext_block,
        'target_helper_still_emits_maxevents_for_text_paths': 'if ($Take -gt 0) { [void]$parts.Add(("MaxEvents={0}" -f $Take)) }' in target_helper,
        'evtx_export_has_no_maxevents_parameter': bool(evtx_export_param_block) and not evtx_param_claims_event_cap,
        'evtx_export_preserves_timediff_filter': 'TimeCreated[timediff(@SystemTime)' in evtx_export,
        'evtx_export_preserves_explicit_window_filter': "TimeCreated[@SystemTime>='$startUtc' and @SystemTime<='$endUtc']" in evtx_export,
        'evtx_export_preserves_event_id_filter': 'EventID=$_' in evtx_export,
    })
    checks.update(fixture_checks)

    add_missing_errors('lograw metadata truth policy failed: ', checks, [
        'review_function_present',
        'retrieval_function_present',
        'logtext_action_block_present',
        'lograw_action_block_present',
        'target_details_helper_present',
        'evtx_export_function_present',
        'evtx_export_param_block_present',
        'param_block_negative_fixture_detects_maxevents',
        'target_detail_negative_fixtures_detect_count_cap',
        'target_detail_multiline_negative_fixtures_detect_count_cap',
        'target_detail_parameter_prefix_negative_fixtures_detect_count_cap',
        'target_detail_colon_parameter_negative_fixtures_detect_count_cap',
        'target_detail_implicit_continuation_negative_fixtures_detect_count_cap',
        'target_detail_implicit_continuation_benign_fixtures_avoid_false_positives',
        'target_detail_splat_negative_fixtures_reject_splatting',
        'target_detail_implicit_continuation_splat_negative_fixtures_reject_splatting',
        'export_splat_negative_fixtures_reject_splatting',
        'export_implicit_continuation_negative_fixtures_detect_count_cap',
        'export_colon_parameter_negative_fixtures_detect_count_cap',
        'export_implicit_continuation_benign_fixtures_avoid_false_positives',
        'export_implicit_continuation_splat_negative_fixtures_reject_splatting',
        'command_anchor_benign_fixtures_avoid_false_positives',
        'command_separator_benign_fixtures_avoid_false_positives',
        'command_case_negative_fixtures_detect_count_cap',
        'target_helper_metadata_only_no_event_reader',
        'lograw_target_details_omits_maxevents_overclaim',
        'lograw_target_details_omits_splatting',
        'lograw_target_details_keeps_log_window_ids',
        'lograw_output_initializes_applied_filter_scope',
        'lograw_output_conditionally_adds_eventids_filter',
        'lograw_output_writes_applied_filter_scope',
        'lograw_output_states_no_event_count_cap',
        'lograw_interpretation_states_no_maxevents_cap',
        'lograw_export_call_preserved',
        'lograw_export_call_omits_maxevents',
        'lograw_export_call_omits_splatting',
        'logtext_still_uses_maxevents_metadata',
        'logtext_still_uses_bounded_text_query',
        'target_helper_still_emits_maxevents_for_text_paths',
        'evtx_export_has_no_maxevents_parameter',
        'evtx_export_preserves_timediff_filter',
        'evtx_export_preserves_explicit_window_filter',
        'evtx_export_preserves_event_id_filter',
    ], errors)

    return {
        'success': not errors,
        'checks': checks,
        'errors': errors,
    }
