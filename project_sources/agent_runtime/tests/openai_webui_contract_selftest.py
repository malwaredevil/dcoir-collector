#!/usr/bin/env python3
"""Adversarial boundary and ownership checks for the shared OpenAI WebUI contract."""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))

import openai_webui_contract as webui
import build_openai_dcoir_analyst as dcoir
import build_openai_usb_reporting as usb
import build_openai_gpt_deployment_release as release
import validate_shared_agent_source_contract as source_validator


def main() -> int:
    assert webui.INSTRUCTION_CHARACTER_CEILING == 8000
    assert webui.DESCRIPTION_CHARACTER_CEILING == 300
    assert webui.CONVERSATION_STARTER_COUNT == 4
    assert len(webui.CAPABILITY_KEYS) == 10
    assert len(set(webui.CAPABILITY_KEYS)) == len(webui.CAPABILITY_KEYS)
    assert set(webui.CAPABILITY_LABELS) == set(webui.CAPABILITY_KEYS)
    assert source_validator.UNAVAILABLE_OPENAI_CAPABILITIES == set(webui.CAPABILITY_KEYS)

    # All three consumers must execute the identical counting and surrogate rules.
    for consumer in (dcoir, usb, release):
        assert consumer._webui_character_count is webui.webui_character_count
        assert consumer._webui_paste_safe_character_count is webui.webui_paste_safe_character_count
        assert consumer._contains_lone_surrogate is webui.contains_lone_surrogate

    count = webui.webui_character_count
    paste_count = webui.webui_paste_safe_character_count
    for value, exact, expanded in (
        ('', 0, 0),
        ('ascii', 5, 5),
        ('a\nb', 3, 4),
        ('a\r\nb', 4, 4),
        ('a\rb', 3, 4),
        ('a\r\r\nb', 5, 6),
        ('a\r\nb\nc\rd', 8, 10),
        ('😀', 2, 2),
        ('a😀\rb', 5, 6),
    ):
        assert count(value) == exact, (repr(value), exact, count(value))
        assert paste_count(value) == expanded, (repr(value), expanded, paste_count(value))
        assert paste_count(value) == paste_count(value.replace('\r\n', '\n').replace('\r', '\n'))

    # Test the actual difference that previously let the two builders undercount.
    boundary = 'x' * 7998 + '\rb'
    assert count(boundary) == 8000
    assert paste_count(boundary) == 8001
    assert paste_count('x' * 7998 + '\nb') == 8001
    assert paste_count('x' * 7998 + '\r\nb') == 8001
    assert paste_count('x' * 7998 + 'b') == 7999
    assert count('x' * 298 + '😀') == 300
    assert count('x' * 299 + '😀') == 301

    for malformed in ('\ud800', '\udfff', 'a\ud800b'):
        assert webui.contains_lone_surrogate(malformed)
        assert count(malformed) == len(malformed)
    for safe in ('', 'ascii', '😀', '𝄞'):
        assert not webui.contains_lone_surrogate(safe)

    starters = ['one', 'two', 'three', 'four']
    valid = webui.valid_conversation_starters_shape
    assert valid(starters)
    assert valid(['one', 'two', 'three', 'three'])  # Uniqueness remains a separate strict check.
    for invalid in (None, '', (), starters[:3], starters + ['five'],
                    ['one', 'two', '', 'four'], ['one', 'two', 3, 'four']):
        assert not valid(invalid), repr(invalid)

    # Release validator must reject a lone CR at the ceiling (raw count is safe).
    errors = []
    manifest = {
        'instruction_character_count': count(boundary),
        'instruction_character_ceiling': webui.INSTRUCTION_CHARACTER_CEILING,
        'description_character_count': 4,
        'description_character_ceiling': webui.DESCRIPTION_CHARACTER_CEILING,
    }
    config = {'description': 'test', 'conversation_starters': starters}
    release._validate_webui_limits(config, boundary.encode(), manifest, 'test_target', errors)
    assert len(errors) == 1 and 'paste-safe characters' in errors[0], errors

    # Release should enforce the same uniqueness rule as both package builders.
    errors = []
    config['conversation_starters'] = ['one', 'two', 'three', 'three']
    manifest['instruction_character_count'] = 2
    release._validate_webui_limits(config, b'ab', manifest, 'test_target', errors)
    assert errors == ['test_target conversation starters must be unique'], errors

    print('PASS: shared WebUI contract boundaries, all import owners and hostile lone-CR parity')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
