#!/usr/bin/env python3
"""Canonical source commit resolver for governed release and parity reports.

Precedence (highest first): explicit argument, reviewed exact head, GitHub
pull_request event head, GITHUB_SHA, repository Git HEAD, unavailable.
Return both the commit and its provenance, preserving the existing parity
report's public tuple contract and its warning on unreadable event metadata.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def resolve_source_commit(
    repo_root: Path | None, explicit: str | None = None,
) -> tuple[str, str]:
    if explicit:
        return explicit, 'explicit_argument'

    reviewed = os.environ.get('AGENT_RUNTIME_REVIEWED_HEAD_SHA')
    if reviewed and reviewed.strip():
        return reviewed, 'AGENT_RUNTIME_REVIEWED_HEAD_SHA'

    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding='utf-8'))
            head_sha = event.get('pull_request', {}).get('head', {}).get('sha')
            if isinstance(head_sha, str) and head_sha.strip():
                return head_sha, 'github_event_pull_request_head_sha'
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            print(
                'warning: unable to read pull_request head sha from '
                f'GITHUB_EVENT_PATH ({event_path}): {exc}',
                file=sys.stderr,
            )

    github_sha = os.environ.get('GITHUB_SHA')
    if github_sha and github_sha.strip():
        return github_sha, 'GITHUB_SHA'
    if repo_root is not None:
        try:
            completed = subprocess.run(
                ['git', 'rev-parse', 'HEAD'], cwd=repo_root, check=False,
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed and completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip(), 'git_rev_parse_head'
    return 'unknown', 'unavailable'
