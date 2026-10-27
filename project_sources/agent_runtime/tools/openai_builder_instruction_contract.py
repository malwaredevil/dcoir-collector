#!/usr/bin/env python3
"""One canonical validator for OpenAI GPT Instructions and behavioral cases.

Both provider targets supply governed section headings, static markers, allowed
provider wording, case schema/count, and their established marker error policy.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from openai_webui_contract import (
    webui_character_count,
    webui_paste_safe_character_count,
)


def validate_instruction_cases(
    instructions: bytes,
    manifest: dict[str, Any],
    cases: dict[str, Any],
    errors: list[str],
    *,
    target_id: str,
    case_schema: str,
    expected_ceiling: int,
    section_headings: dict[str, str],
    required_static_markers: tuple[str, ...],
    provider_topology_leaks: tuple[str, ...],
    expected_cases: int,
    marker_error_policy: str,
) -> list[str]:
    """Return ordered case IDs; append all governance failures without writing files."""
    if marker_error_policy not in ('aggregate', 'per_marker'):
        errors.append('Unknown behavioral marker validation policy')
        return []
    if cases.get('schema') != case_schema:
        errors.append('Unexpected behavioral cases schema')
    if cases.get('target_id') != target_id:
        errors.append('Behavioral cases have the wrong target_id')
    if cases.get('live_model_evidence') is not False:
        errors.append('Offline behavioral cases must not claim live model evidence')
    if not isinstance(instructions, bytes):
        errors.append('Canonical Instructions must be UTF-8 bytes')
        return []
    try:
        text = instructions.decode('utf-8')
    except UnicodeDecodeError:
        errors.append('Canonical Instructions must be UTF-8')
        return []
    ceiling = manifest.get('instruction_character_ceiling')
    if type(ceiling) is not int or ceiling != expected_ceiling:
        errors.append(f'instruction_character_ceiling must remain {expected_ceiling}')
    character_count = webui_character_count(text)
    if character_count > expected_ceiling:
        errors.append(f'Instructions exceed character ceiling: {character_count} > {expected_ceiling}')
    # Actual WebUI paste accounting expands LF and bare CR to CRLF.
    paste_count = webui_paste_safe_character_count(text)
    if paste_count > expected_ceiling:
        errors.append(
            'Instructions exceed paste-safe character ceiling after CRLF expansion: '
            f'{paste_count} > {expected_ceiling}'
        )
    for section_id, heading in section_headings.items():
        if text.count(heading) != 1:
            errors.append(f'Instructions must contain one {section_id} heading')
    positions = [text.find(heading) for heading in section_headings.values()]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append('Instruction sections must remain in the governed order')
    for marker in required_static_markers:
        if marker not in text:
            errors.append(f'Instructions lack required static contract marker: {marker}')
    lower = text.lower()
    for leak in provider_topology_leaks:
        if leak in lower:
            errors.append(f'Provider-topology leakage in Instructions: {leak}')
    case_items = cases.get('cases')
    if not isinstance(case_items, list):
        errors.append('Behavioral cases must be an array')
        return []
    case_ids: list[str] = []
    for case in case_items:
        if not isinstance(case, dict):
            errors.append('Behavioral cases contain a non-object entry')
            continue
        case_id = case.get('id')
        if not isinstance(case_id, str) or not case_id:
            errors.append('Behavioral case lacks an id')
            continue
        case_ids.append(case_id)
        for field in ('scenario', 'expected_behavior'):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f'{case_id} lacks a non-empty {field}')
        markers = case.get('required_markers')
        if marker_error_policy == 'aggregate':
            if not isinstance(markers, list) or not markers or not all(
                isinstance(marker, str) and marker for marker in markers
            ):
                errors.append(f'{case_id} has invalid required_markers')
                continue
        elif not isinstance(markers, list) or not markers:
            errors.append(f'{case_id} has invalid required_markers')
            continue
        for marker in markers:
            if not isinstance(marker, str) or not marker:
                # USB Reporting historically reports an invalid item separately.
                errors.append(f'{case_id} has an invalid required marker')
            elif marker not in text:
                errors.append(f'{case_id} missing Instructions marker: {marker}')
    for duplicate, count in sorted(Counter(case_ids).items()):
        if count > 1:
            errors.append(f'Duplicate behavioral case id: {duplicate}')
    if len(case_ids) != expected_cases:
        errors.append(f'Expected {expected_cases} behavioral cases, got {len(case_ids)}')
    return case_ids
