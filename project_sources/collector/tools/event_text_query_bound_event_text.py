#!/usr/bin/env python3
"""Event-text bounded-query policy checks for collector runtime validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from event_text_query_bound_common import (
    DIAGNOSTIC_CONTEXT_RELS,
    add_missing_errors,
    extract_function_body,
    read_combined_text,
)


def validate_event_text_query_bound_policy(source_dir: Path) -> Dict[str, object]:
    errors: List[str] = []
    source_paths = [(rel, source_dir / rel) for rel in DIAGNOSTIC_CONTEXT_RELS]
    missing_source_rels = [rel for rel, path in source_paths if not path.exists()]
    text = read_combined_text(source_dir, DIAGNOSTIC_CONTEXT_RELS)
    checks: Dict[str, object] = {
        'paths': list(DIAGNOSTIC_CONTEXT_RELS),
        'source_present': bool(text),
        'all_sources_present': not missing_source_rels,
        'missing_paths': missing_source_rels,
    }

    if missing_source_rels or not text:
        errors.append('event text diagnostic context source is missing: ' + ', '.join(missing_source_rels or list(DIAGNOSTIC_CONTEXT_RELS)))
        return {'success': False, 'checks': checks, 'errors': errors}

    helper = extract_function_body(text, 'Invoke-CollectorBoundedWinEventQuery')
    high_signal = extract_function_body(text, 'Get-SecurityHighSignalSummaryText')
    event_text = extract_function_body(text, 'Get-EventText')
    helper_query = 'Get-WinEvent -FilterHashtable $FilterHashtable -MaxEvents $MaxEvents -ErrorAction Stop'
    helper_sort = 'Sort-Object TimeCreated -Descending'
    helper_query_pos = helper.find(helper_query)
    helper_sort_pos = helper.find(helper_sort)
    legacy_unbounded_sort = re.compile(
        r'Get-WinEvent\s+-FilterHashtable\s+\$fh\s+-ErrorAction\s+Stop\s*\|\s*Sort-Object\s+TimeCreated\s+-Descending\s*\|\s*Select-Object\s+-First',
        re.IGNORECASE | re.DOTALL,
    )
    direct_fh_get_winevent = re.compile(r'Get-WinEvent\s+-FilterHashtable\s+\$fh\b', re.IGNORECASE)

    checks.update({
        'bounded_helper_present': bool(helper),
        'high_signal_function_present': bool(high_signal),
        'event_text_function_present': bool(event_text),
        'helper_applies_maxevents_at_query': helper_query in helper,
        'helper_returns_empty_for_nonpositive_limit': 'if ($MaxEvents -lt 1)' in helper and 'return @()' in helper,
        'helper_sorts_only_after_maxevents': helper_query_pos != -1 and helper_sort_pos != -1 and helper_query_pos < helper_sort_pos,
        'legacy_high_signal_unbounded_sort_absent': legacy_unbounded_sort.search(high_signal) is None,
        'legacy_event_text_unbounded_sort_absent': legacy_unbounded_sort.search(event_text) is None,
        'high_signal_direct_get_winevent_absent': direct_fh_get_winevent.search(high_signal) is None,
        'event_text_direct_get_winevent_absent': direct_fh_get_winevent.search(event_text) is None,
        'high_signal_uses_take_x4_query_limit': '$queryLimit = [Math]::Max(0, ($Take * 4))' in high_signal,
        'high_signal_uses_bounded_helper': 'Invoke-CollectorBoundedWinEventQuery -FilterHashtable $fh -MaxEvents $queryLimit' in high_signal,
        'event_text_uses_take_query_limit': '$queryLimit = [Math]::Max(0, $Take)' in event_text,
        'event_text_uses_bounded_helper': 'Invoke-CollectorBoundedWinEventQuery -FilterHashtable $fh -MaxEvents $queryLimit' in event_text,
        'high_signal_preserves_explicit_end_time': '$fh.EndTime = $window.EndTime' in high_signal,
        'event_text_preserves_explicit_end_time': '$fh.EndTime = $window.EndTime' in event_text,
        'event_text_preserves_event_id_filter': '$fh.Id = $Ids' in event_text,
        'high_signal_metadata_uses_take': "Get-CollectorEventWindowMetadataLines -Window $window -Channel 'Security' -Ids $ids -Take $Take" in high_signal,
        'event_text_metadata_uses_take': 'Get-CollectorEventWindowMetadataLines -Window $window -Channel $Channel -Ids $Ids -Take $Take' in event_text,
        'high_signal_raw_event_count_from_bounded_events': 'RAW_EVENT_COUNT={0}' in high_signal and '@($events).Count' in high_signal,
        'event_text_event_count_from_bounded_events': 'EVENT_COUNT={0}' in event_text and '@($events).Count' in event_text,
        'non_elevated_security_message_preserved': 'Get-NonElevatedSecurityVisibilityMessage' in high_signal and 'Get-NonElevatedSecurityVisibilityMessage' in event_text,
    })

    add_missing_errors('event text query bound policy failed: ', checks, [
        'bounded_helper_present',
        'high_signal_function_present',
        'event_text_function_present',
        'helper_applies_maxevents_at_query',
        'helper_returns_empty_for_nonpositive_limit',
        'helper_sorts_only_after_maxevents',
        'legacy_high_signal_unbounded_sort_absent',
        'legacy_event_text_unbounded_sort_absent',
        'high_signal_direct_get_winevent_absent',
        'event_text_direct_get_winevent_absent',
        'high_signal_uses_take_x4_query_limit',
        'high_signal_uses_bounded_helper',
        'event_text_uses_take_query_limit',
        'event_text_uses_bounded_helper',
        'high_signal_preserves_explicit_end_time',
        'event_text_preserves_explicit_end_time',
        'event_text_preserves_event_id_filter',
        'high_signal_metadata_uses_take',
        'event_text_metadata_uses_take',
        'high_signal_raw_event_count_from_bounded_events',
        'event_text_event_count_from_bounded_events',
        'non_elevated_security_message_preserved',
    ], errors)

    return {
        'success': not errors,
        'checks': checks,
        'errors': errors,
    }
