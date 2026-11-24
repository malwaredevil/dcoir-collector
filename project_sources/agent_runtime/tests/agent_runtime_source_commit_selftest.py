#!/usr/bin/env python3
"""Independent source-commit precedence and cross-tool release identity tests."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import agent_runtime_source_commit as shared
import report_agent_release_parity as parity
import build_openai_gpt_deployment_release as release
from openai_gpt_release_test_fixture import stage_repo, _build

COMMIT = 'a' * 40
MERGE = 'b' * 40
OTHER = 'c' * 40


def test_precedence_and_both_consumers() -> None:
    assert parity.resolve_source_commit is shared.resolve_source_commit
    assert release.resolve_source_commit is shared.resolve_source_commit

    with tempfile.TemporaryDirectory(prefix='openai-identity-event-') as directory:
        root = Path(directory)
        event = root / 'event.json'
        event.write_text(json.dumps({
            'pull_request': {'head': {'sha': COMMIT}},
        }), encoding='utf-8')
        environ = {
            'AGENT_RUNTIME_REVIEWED_HEAD_SHA': OTHER,
            'GITHUB_EVENT_PATH': str(event),
            'GITHUB_SHA': MERGE,
        }
        with mock.patch.dict(os.environ, environ, clear=True):
            assert shared.resolve_source_commit(root, 'explicit-id') == (
                'explicit-id', 'explicit_argument',
            )
            assert shared.resolve_source_commit(root) == (
                OTHER, 'AGENT_RUNTIME_REVIEWED_HEAD_SHA',
            )
            assert release._source_commit(root, None) == OTHER
            assert parity.resolve_source_commit(root)[0] == release._source_commit(root, None)

        environ.pop('AGENT_RUNTIME_REVIEWED_HEAD_SHA')
        with mock.patch.dict(os.environ, environ, clear=True):
            assert shared.resolve_source_commit(root) == (
                COMMIT, 'github_event_pull_request_head_sha',
            )
            assert release._source_commit(root, None) == COMMIT

        environ.pop('GITHUB_EVENT_PATH')
        with mock.patch.dict(os.environ, environ, clear=True):
            assert shared.resolve_source_commit(root) == (MERGE, 'GITHUB_SHA')
        with mock.patch.dict(os.environ, {'GITHUB_SHA': MERGE}, clear=True):
            assert shared.resolve_source_commit(None) == (MERGE, 'GITHUB_SHA')

    with mock.patch.dict(os.environ, {}, clear=True):
        assert shared.resolve_source_commit(None) == ('unknown', 'unavailable')


def test_malformed_pr_event_fallback() -> None:
    with tempfile.TemporaryDirectory(prefix='openai-identity-hostile-') as directory:
        root = Path(directory)
        event = root / 'event.json'
        for value in (
            b'{',
            b'\xff',
            b'[]',
            b'{"pull_request":null}',
            b'{"pull_request":{"head":[]}}',
        ):
            event.write_bytes(value)
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, {
                'GITHUB_EVENT_PATH': str(event),
                'GITHUB_SHA': MERGE,
            }, clear=True), contextlib.redirect_stderr(stderr):
                assert shared.resolve_source_commit(root) == (MERGE, 'GITHUB_SHA')
            assert 'warning: unable to read pull_request head sha' in stderr.getvalue(), value

        # Missing/non-string/whitespace PR head is not authority.
        for document in (
            {}, {'pull_request': {}},
            {'pull_request': {'head': {'sha': 7}}},
            {'pull_request': {'head': {'sha': '   '}}},
        ):
            event.write_text(json.dumps(document), encoding='utf-8')
            with mock.patch.dict(os.environ, {
                'GITHUB_EVENT_PATH': str(event),
                'GITHUB_SHA': MERGE,
            }, clear=True):
                assert shared.resolve_source_commit(root) == (MERGE, 'GITHUB_SHA')

        event.unlink()
        with mock.patch.dict(os.environ, {
            'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': MERGE,
        }, clear=True):
            with contextlib.redirect_stderr(io.StringIO()):
                assert shared.resolve_source_commit(root) == (MERGE, 'GITHUB_SHA')


def test_git_and_unavailable_fallback() -> None:
    with tempfile.TemporaryDirectory(prefix='openai-identity-git-') as directory:
        root = Path(directory)
        git = subprocess.CompletedProcess(['git', 'rev-parse', 'HEAD'], 0, COMMIT + '\n', '')
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            shared.subprocess, 'run', return_value=git,
        ) as call:
            assert shared.resolve_source_commit(root) == (COMMIT, 'git_rev_parse_head')
            call.assert_called_once()
            assert call.call_args.kwargs['cwd'] == root
            assert call.call_args.kwargs['timeout'] == 10

        for result in (
            subprocess.CompletedProcess(['git'], 1, '', 'failed'),
            subprocess.CompletedProcess(['git'], 0, '  \n', ''),
        ):
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
                shared.subprocess, 'run', return_value=result,
            ):
                assert shared.resolve_source_commit(root) == ('unknown', 'unavailable')
        for problem in (FileNotFoundError('git missing'), subprocess.TimeoutExpired('git', 10)):
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
                shared.subprocess, 'run', side_effect=problem,
            ):
                assert shared.resolve_source_commit(root) == ('unknown', 'unavailable')

        # An exact reviewed head also must not spawn a Git process.
        with mock.patch.dict(os.environ, {
            'AGENT_RUNTIME_REVIEWED_HEAD_SHA': COMMIT, 'GITHUB_SHA': MERGE,
        }, clear=True), mock.patch.object(
            shared.subprocess, 'run', side_effect=AssertionError('Git must not run'),
        ):
            assert shared.resolve_source_commit(root) == (
                COMMIT, 'AGENT_RUNTIME_REVIEWED_HEAD_SHA',
            )


def test_release_accepts_same_pr_head_and_rejects_mismatch() -> None:
    # Build the baseline within this selftest, independent of any /tmp file,
    # local checkout identity, CI step order or earlier test invocation.
    temp, root = stage_repo()
    try:
        errors, baseline = _build(root, 'baseline-identity')
        assert not errors, errors
        baseline_bytes = (root / baseline['zip_path']).read_bytes()
    finally:
        temp.cleanup()

    for environ, expected_basis in (
        ({'AGENT_RUNTIME_REVIEWED_HEAD_SHA': COMMIT, 'GITHUB_SHA': MERGE},
         'AGENT_RUNTIME_REVIEWED_HEAD_SHA'),
        ({'GITHUB_SHA': COMMIT}, 'GITHUB_SHA'),
    ):
        temp, root = stage_repo()
        try:
            with mock.patch.dict(os.environ, environ, clear=True):
                errors, report = release.build_release(
                    root, root / 'project_sources/validation/release',
                    root / 'project_sources/validation/parity',
                    source_commit=None,
                )
            assert not errors and report['success'], (environ, errors)
            assert report['source_commit'] == COMMIT
            assert report['source_commit_basis'] == expected_basis
            assert (root / report['zip_path']).read_bytes() == baseline_bytes
        finally:
            temp.cleanup()

    # In PR events GitHub's merge SHA must not override the event's exact head.
    temp, root = stage_repo()
    try:
        event = root / 'event.json'
        event.write_text(json.dumps({'pull_request': {'head': {'sha': COMMIT}}}),
                         encoding='utf-8')
        with mock.patch.dict(os.environ, {
            'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': MERGE,
        }, clear=True):
            errors, report = release.build_release(
                root, root / 'project_sources/validation/event-release',
                root / 'project_sources/validation/parity',
                source_commit=None,
            )
        assert not errors and report['success'], errors
        assert report['source_commit'] == COMMIT
        assert report['source_commit_basis'] == 'github_event_pull_request_head_sha'
        assert (root / report['zip_path']).read_bytes() == baseline_bytes
    finally:
        temp.cleanup()

    temp, root = stage_repo()
    try:
        with mock.patch.dict(os.environ, {
            'AGENT_RUNTIME_REVIEWED_HEAD_SHA': OTHER,
            'GITHUB_SHA': MERGE,
        }, clear=True):
            errors, report = release.build_release(
                root, root / 'project_sources/validation/release',
                root / 'project_sources/validation/parity',
                source_commit=None,
            )
        assert errors and not report['success']
        assert any('Release parity report source commit mismatch' in e for e in errors), errors
        assert report['source_commit'] == OTHER
        assert report['source_commit_basis'] == 'AGENT_RUNTIME_REVIEWED_HEAD_SHA'
        assert report['zip_path'] is None
    finally:
        temp.cleanup()


def main() -> int:
    test_precedence_and_both_consumers()
    test_malformed_pr_event_fallback()
    test_git_and_unavailable_fallback()
    test_release_accepts_same_pr_head_and_rejects_mismatch()
    print('PASS: governed source-commit precedence, provenance, hostile fallback and release parity')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
