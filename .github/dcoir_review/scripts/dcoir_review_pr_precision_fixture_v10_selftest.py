#!/usr/bin/env python3
"""Deterministic semantic guards for the current clean-precision v10 corpus."""
from __future__ import annotations

import os
import re

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v9 as v9
import dcoir_review_pr_precision_eval_v10 as current
import dcoir_review_pr_precision_fixture_v9_selftest as v9_guard

CHECKOUT_USES_RE = re.compile(r"^uses\s*:\s*['\"]?actions/checkout@", re.IGNORECASE)
PERSIST_KEY_RE = re.compile(r"^persist-credentials\s*:\s*(.*)$", re.IGNORECASE)
FALSE_VALUE_RE = re.compile(r"(?:false|'false'|\"false\")", re.IGNORECASE)

def _strip_yaml_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == '#':
            return line[:index]
    return line

def _step_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    steps_indent: int | None = None
    step_indent: int | None = None
    for line in lines:
        cleaned = _strip_yaml_comment(line)
        stripped = cleaned.strip()
        indent = len(line) - len(line.lstrip())
        if steps_indent is None:
            if stripped == 'steps:':
                steps_indent = indent
            continue
        if stripped and indent <= steps_indent:
            if current:
                blocks.append('\n'.join(current))
            current = []
            step_indent = None
            steps_indent = indent if stripped == 'steps:' else None
            continue
        if not stripped:
            if current:
                current.append(line)
            continue
        if stripped.startswith('- '):
            if step_indent is None:
                step_indent = indent
            if indent == step_indent:
                if current:
                    blocks.append('\n'.join(current))
                current = [line]
                continue
        if current:
            current.append(line)
    if current:
        blocks.append('\n'.join(current))
    return blocks

def _normalized_block_line(line: str) -> str:
    stripped = _strip_yaml_comment(line).strip()
    if stripped.startswith('- '):
        stripped = stripped[2:].lstrip()
    return stripped

def _checkout_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    for block in _step_blocks(lines):
        if any(CHECKOUT_USES_RE.match(_normalized_block_line(line)) for line in block.splitlines()):
            blocks.append(block)
    return blocks

def _block_disables_credentials(block: str) -> bool:
    lines = block.splitlines()
    with_lines = [line for line in lines if _normalized_block_line(line) == 'with:']
    if len(with_lines) != 1:
        return False
    with_indent = len(with_lines[0]) - len(with_lines[0].lstrip())
    settings: list[tuple[int, str]] = []
    for line in lines:
        match = PERSIST_KEY_RE.match(_normalized_block_line(line))
        if match:
            settings.append((len(line) - len(line.lstrip()), match.group(1).strip()))
    if len(settings) != 1:
        return False
    setting_indent, value = settings[0]
    return setting_indent > with_indent and FALSE_VALUE_RE.fullmatch(value) is not None

def _assert_v10_guard(text: str) -> None:
    lines = text.splitlines()
    assert 'pull_request_target' not in text
    assert not v9_guard._references_secret_context(text)
    assert 'write-all' not in text
    permission_key_lines = [line for line in lines if 'permissions' in line]
    assert permission_key_lines == ['permissions:']
    permission_index = lines.index('permissions:')
    assert lines[permission_index + 1] == '  contents: read'
    assert lines[permission_index + 2] == 'jobs:'
    checkout_refs = [line for line in lines if 'actions/checkout@' in _strip_yaml_comment(line).lower()]
    checkout_blocks = _checkout_blocks(lines)
    assert checkout_refs
    assert len(checkout_refs) == len(checkout_blocks)
    assert all(_block_disables_credentials(block) for block in checkout_blocks)

def _expect_rejected(text: str) -> None:
    try:
        _assert_v10_guard(text)
    except AssertionError:
        return
    raise AssertionError('unsafe fork workflow unexpectedly passed the v10 guard')

def main() -> None:
    v9_cases = {str(case['id']): case for case in v9.load_v9_cases()}
    v10_cases = {str(case['id']): case for case in current.load_v10_cases()}
    assert len(v9_cases) == len(v10_cases) == 10
    assert all(case['expected_findings'] == [] for case in v10_cases.values())

    old_id = 'precision-gha-fork-semantic-secret-context-approved-tested'
    new_id = 'precision-gha-fork-step-aware-checkout-approved-tested'
    assert old_id in v9_cases and old_id not in v10_cases
    assert new_id not in v9_cases and new_id in v10_cases
    assert {key: value for key, value in v9_cases.items() if key != old_id} == {
        key: value for key, value in v10_cases.items() if key != new_id
    }

    fork_case = v10_cases[new_id]
    workflow = v9_guard.right_side_file(fork_case, '.github/workflows/pr-diagnostics.yml')
    fork_test = v9_guard.right_side_file(fork_case, 'tests/test_pr_diagnostics_workflow.py')
    _assert_v10_guard(workflow)

    rejected_mutations = (
        workflow.replace('          persist-credentials: false\n', ''),
        workflow + '\n      - name: Second checkout\n        uses: actions/checkout@v7\n',
        workflow + '\n      - {uses: actions/checkout@v7, with: {persist-credentials: false}}\n',
        workflow.replace('          persist-credentials: false', '          # persist-credentials: false'),
        workflow.replace('          persist-credentials: false', '          persist-credentials: false\n          persist-credentials: true'),
        workflow.replace('        with:\n          persist-credentials: false', '        persist-credentials: false\n        with:'),
        workflow.replace('    runs-on: ubuntu-latest', '    permissions:\n      pull-requests: write\n    runs-on: ubuntu-latest'),
        workflow.replace('    runs-on: ubuntu-latest', '    permissions: {pull-requests: write}\n    runs-on: ubuntu-latest'),
        workflow + '\n      - run: echo "${{ secrets.DEPLOY_KEY }}"\n',
        workflow + '\n      - run: echo "${{ secrets }}"\n',
        workflow + '\n      - run: echo "${{ toJSON(secrets) }}"\n',
    )
    for mutation in rejected_mutations:
        _expect_rejected(mutation)

    with_before_uses = workflow.replace(
        '      - name: Checkout PR head\n        uses: actions/checkout@v7\n        with:\n          persist-credentials: false',
        '      - name: Checkout PR head\n        with:\n          persist-credentials: false\n        uses: actions/checkout@v7',
    )
    _assert_v10_guard(with_before_uses)
    _assert_v10_guard(workflow + '\n      - run: echo "${{ \'secrets }}\' }}"\n')

    for needle in (
        '_step_blocks',
        '_strip_yaml_comment',
        'len(checkout_refs) == len(checkout_blocks)',
        'PERSIST_KEY_RE',
        'FALSE_VALUE_RE',
        'test_guard_rejects_named_checkout_without_disabled_credentials',
        'test_guard_rejects_second_named_checkout_without_disabled_credentials',
        'test_guard_rejects_flow_style_checkout_fail_closed',
        'test_guard_rejects_commented_persist_credentials',
        'test_guard_rejects_duplicate_conflicting_persist_credentials',
        'test_guard_rejects_persist_credentials_outside_with',
        'test_guard_accepts_with_before_uses_when_credentials_disabled',
    ):
        assert needle in fork_test, f'missing v10 fork invariant: {needle!r}'

    workflow_cases = [
        case for case in v10_cases.values()
        if any(str(item['filename']).startswith('.github/workflows/') for item in case['files'])
    ]
    assert len(workflow_cases) == 2
    assert all(str(case.get('trusted_context', '')).strip() for case in workflow_cases)

    old = os.environ.get('DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT')
    try:
        os.environ['DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT'] = '1'
        for case in v10_cases.values():
            prompt = base.build_pr_prompt(case)
            assert str(case['ground_truth_rationale']) not in prompt
            assert 'expected_findings' not in prompt
            assert str(case['id']) not in prompt
            assert 'ground_truth_rationale' not in prompt
            if case.get('trusted_context'):
                assert 'Trusted evaluation context:' in prompt
                assert str(case['trusted_context']) in prompt
        os.environ['DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT'] = '0'
        for case in workflow_cases:
            prompt = base.build_pr_prompt(case)
            assert 'Trusted evaluation context:' not in prompt
            assert str(case['trusted_context']) not in prompt
    finally:
        if old is None:
            os.environ.pop('DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT', None)
        else:
            os.environ['DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT'] = old

    print('dcoir_review_pr_precision_fixture_v10_selftest passed: v9 history is preserved; checkout steps are grouped before classification, comments cannot satisfy credential disabling, unsupported checkout syntax fails closed, semantic secret-context protection remains active, and ground truth stays hidden')

if __name__ == '__main__':
    main()
