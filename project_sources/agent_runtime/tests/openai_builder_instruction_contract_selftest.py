#!/usr/bin/env python3
"""Independent safe and hostile tests for both static OpenAI GPT Instructions contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project_sources/agent_runtime/tools'))
import build_openai_dcoir_analyst as dcoir
import build_openai_usb_reporting as usb
from openai_builder_instruction_contract import validate_instruction_cases

TARGETS = (('openai_dcoir_analyst', dcoir), ('openai_usb_reporting', usb))


def fixture(target, builder):
    folder = ROOT / f'project_sources/agent_runtime/provider_adapters/{target}'
    adapter = json.loads((folder / 'Adapter_Manifest.json').read_text(encoding='utf-8'))
    cases = json.loads((folder / 'Behavioral_Contract_Cases.json').read_text(encoding='utf-8'))
    instructions = (folder / 'Instructions.md').read_bytes()
    return adapter, cases, instructions


def evaluate(builder, adapter, cases, instructions):
    errors = []
    ids = validate_instruction_cases(
        instructions, adapter, cases, errors,
        target_id=builder.TARGET_ID,
        case_schema=builder.EXPECTED_CASE_SCHEMA,
        expected_ceiling=builder.EXPECTED_INSTRUCTION_CHARACTER_CEILING,
        section_headings=builder.SECTION_HEADINGS,
        required_static_markers=builder.REQUIRED_STATIC_MARKERS,
        provider_topology_leaks=builder.PROVIDER_TOPOLOGY_LEAKS,
        expected_cases=builder.EXPECTED_CASES,
        marker_error_policy=builder.CASE_MARKER_POLICY,
    )
    return ids, errors


def test_safe_valid_cases_preserve_order():
    for target, builder in TARGETS:
        adapter, cases, instructions = fixture(target, builder)
        ids, errors = evaluate(builder, adapter, cases, instructions)
        assert not errors and len(ids) == builder.EXPECTED_CASES, (target, errors)
        assert ids == [case['id'] for case in cases['cases']]


def test_bad_case_manifest_metadata_fail_closed():
    for target, builder in TARGETS:
        variants = (
            ('schema', 'bad', 'Unexpected behavioral cases schema'),
            ('target_id', 'unexpected', 'wrong target_id'),
            ('live_model_evidence', True, 'must not claim live model evidence'),
            ('live_model_evidence', None, 'must not claim live model evidence'),
            ('cases', {}, 'Behavioral cases must be an array'),
            ('cases', None, 'Behavioral cases must be an array'),
        )
        for key, value, expected in variants:
            adapter, cases, instructions = fixture(target, builder)
            cases[key] = value
            _, errors = evaluate(builder, adapter, cases, instructions)
            assert any(expected in e for e in errors), (target, key, errors)
        for value in (False, None, '8000', 7999):
            adapter, cases, instructions = fixture(target, builder)
            adapter['instruction_character_ceiling'] = value
            _, errors = evaluate(builder, adapter, cases, instructions)
            assert any('instruction_character_ceiling must remain' in e for e in errors), (target, value, errors)
        adapter, cases, instructions = fixture(target, builder)
        _, errors = evaluate(builder, adapter, cases, b'\xff')
        assert any('Canonical Instructions must be UTF-8' in e for e in errors)
        _, errors = evaluate(builder, adapter, cases, 'not bytes')
        assert any('Canonical Instructions must be UTF-8 bytes' in e for e in errors)


def test_bad_behavioral_case_records_fail_closed():
    for target, builder in TARGETS:
        variants = (
            ('nonobject', lambda c: c['cases'].__setitem__(0, None), 'non-object entry'),
            ('missing-id', lambda c: c['cases'][0].pop('id'), 'lacks an id'),
            ('boolean-id', lambda c: c['cases'][0].__setitem__('id', True), 'lacks an id'),
            ('duplicate-id', lambda c: c['cases'][1].__setitem__('id', c['cases'][0]['id']), 'Duplicate behavioral case id'),
            ('wrong-count', lambda c: c['cases'].pop(), 'behavioral cases, got'),
            ('no-scenario', lambda c: c['cases'][0].pop('scenario'), 'non-empty scenario'),
            ('blank-scenario', lambda c: c['cases'][0].__setitem__('scenario', '  '), 'non-empty scenario'),
            ('missing-behavior', lambda c: c['cases'][0].pop('expected_behavior'), 'non-empty expected_behavior'),
            ('empty-required-markers', lambda c: c['cases'][0].__setitem__('required_markers', []), 'invalid required_markers'),
            ('wrong-markers-type', lambda c: c['cases'][0].__setitem__('required_markers', 'x'), 'invalid required_markers'),
            ('missing-text-marker', lambda c: c['cases'][0].__setitem__('required_markers', ['UNREACHABLE_CASE_MARKER_X']), 'missing Instructions marker'),
        )
        for name, mutate, expected in variants:
            adapter, cases, instructions = fixture(target, builder)
            mutate(cases)
            _, errors = evaluate(builder, adapter, cases, instructions)
            assert any(expected in e for e in errors), (target, name, errors)


def test_instruction_content_governance_fail_closed():
    for target, builder in TARGETS:
        adapter, cases, raw = fixture(target, builder)
        text = raw.decode('utf-8')
        heading = next(iter(builder.SECTION_HEADINGS.values()))
        altered = text + '\n' + heading
        _, errors = evaluate(builder, adapter, cases, altered.encode('utf-8'))
        assert any('Instructions must contain one' in e for e in errors), (target, errors)
        altered = text.replace(heading, 'REMOVED_HEADING', 1)
        _, errors = evaluate(builder, adapter, cases, altered.encode('utf-8'))
        assert any('Instruction sections must remain in the governed order' in e for e in errors)
        headings = list(builder.SECTION_HEADINGS.values())
        altered = text.replace(headings[0], 'SWAP_H0', 1).replace(headings[1], headings[0], 1).replace('SWAP_H0', headings[1], 1)
        _, errors = evaluate(builder, adapter, cases, altered.encode('utf-8'))
        assert any('sections must remain in the governed order' in e for e in errors)
        marker = builder.REQUIRED_STATIC_MARKERS[0]
        altered = text.replace(marker, 'REMOVED_STATIC_MARKER')
        _, errors = evaluate(builder, adapter, cases, altered.encode('utf-8'))
        assert any('Instructions lack required static contract marker' in e for e in errors)
        altered = text + '\n' + builder.PROVIDER_TOPOLOGY_LEAKS[0].upper()
        _, errors = evaluate(builder, adapter, cases, altered.encode('utf-8'))
        assert any('Provider-topology leakage in Instructions' in e for e in errors)


def test_utf16_paste_safe_limits_and_boundary_controls():
    for target, builder in TARGETS:
        adapter, cases, _ = fixture(target, builder)
        for text, character_limit, paste_limit in (
            ('a' * 8001, True, True),
            ('a' * 7999 + '\r', False, True),
            ('a' * 7998 + '\U0001f600', False, False),
            ('a' * 7999 + '\U0001f600', True, True),
        ):
            _, errors = evaluate(builder, adapter, cases, text.encode('utf-8'))
            exceeded = any(e.startswith('Instructions exceed character ceiling:') for e in errors)
            paste_exceeded = any(e.startswith('Instructions exceed paste-safe character ceiling') for e in errors)
            assert (exceeded, paste_exceeded) == (character_limit, paste_limit), (target, len(text), errors)


def test_distinct_marker_error_semantics_preserved():
    for target, builder in TARGETS:
        adapter, cases, instructions = fixture(target, builder)
        cases['cases'][0]['required_markers'] = ['NEVER_PRESENT_IN_INSTRUCTIONS_Z', None]
        _, errors = evaluate(builder, adapter, cases, instructions)
        if builder.CASE_MARKER_POLICY == 'aggregate':
            assert any('invalid required_markers' in e for e in errors)
            assert not any('missing Instructions marker: NEVER_PRESENT' in e for e in errors)
            assert not any('invalid required marker' in e for e in errors)
        else:
            assert any('has an invalid required marker' in e for e in errors)
            assert any('missing Instructions marker: NEVER_PRESENT' in e for e in errors)
            assert not any('invalid required_markers' in e for e in errors)


def main() -> int:
    tests = (
        test_safe_valid_cases_preserve_order,
        test_bad_case_manifest_metadata_fail_closed,
        test_bad_behavioral_case_records_fail_closed,
        test_instruction_content_governance_fail_closed,
        test_utf16_paste_safe_limits_and_boundary_controls,
        test_distinct_marker_error_semantics_preserved,
    )
    for test in tests:
        test()
    print(json.dumps({'success': True, 'tests': [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
