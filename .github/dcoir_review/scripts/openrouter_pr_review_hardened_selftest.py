#!/usr/bin/env python3
"""Compatibility wrapper for connector-safe DCOIR Review layer hardened_selftest."""

from __future__ import annotations

import copy
from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from dcoir_review.module_loader import load_segments_into

load_segments_into(globals(), 'hardened_selftest')


class _ProgressCommentGitHub:
    def __init__(self) -> None:
        self.created: list[tuple[int, str]] = []
        self.updated: list[tuple[int, str]] = []

    def request(self, method: str, path: str, body=None, accept: str = "application/vnd.github+json"):
        del body, accept
        assert method == "GET", (method, path)
        if "/comments?" in path:
            return []
        raise AssertionError(path)

    def create_issue_comment(self, issue_number: int, body: str) -> dict[str, int]:
        self.created.append((issue_number, body))
        return {"id": 9001}

    def update_issue_comment(self, comment_id: int, body: str) -> dict[str, int]:
        self.updated.append((comment_id, body))
        return {"id": comment_id}


# The canonical #550 status surface is first-class even when the legacy debug
# progress flag is false. One comment is created, meaningful stage boundaries
# update that same id, and terminal failure updates it again rather than
# creating a second status artifact.
progress_disabled = copy.copy(config)
progress_disabled.post_progress_comment = False
progress_gh = _ProgressCommentGitHub()
progress_reporter = mod.base.ProgressReporter(progress_gh, 277, "/dcoir-review", progress_disabled)
progress_reporter.start()
assert len(progress_gh.created) == 1
assert progress_gh.updated == []
progress_reporter.update("test", "canonical status remains first-class")
assert len(progress_gh.created) == 1
assert len(progress_gh.updated) == 1
progress_reporter.fail("Review quality failure: no actionable primary findings survived normalization.")
assert len(progress_gh.created) == 1
assert len(progress_gh.updated) == 2
terminal_body = progress_gh.updated[-1][1]
assert "review failed before a usable PR review could be posted" in terminal_body
assert "no actionable primary findings survived normalization" in terminal_body

# The legacy flag no longer changes status-comment existence semantics. The
# enabled case also creates one comment and mutates that same comment on failure.
progress_enabled = copy.copy(config)
progress_enabled.post_progress_comment = True
enabled_gh = _ProgressCommentGitHub()
enabled_reporter = mod.base.ProgressReporter(enabled_gh, 277, "/dcoir-review", progress_enabled)
enabled_reporter.start()
assert len(enabled_gh.created) == 1
enabled_reporter.fail("synthetic terminal failure")
assert len(enabled_gh.created) == 1
assert len(enabled_gh.updated) == 1

print("DCOIR Review canonical status visibility selftest passed")
