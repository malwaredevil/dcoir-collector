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

    def create_issue_comment(self, issue_number: int, body: str) -> dict[str, int]:
        self.created.append((issue_number, body))
        return {"id": 9001}

    def update_issue_comment(self, comment_id: int, body: str) -> dict[str, int]:
        self.updated.append((comment_id, body))
        return {"id": comment_id}


# Production keeps routine progress comments disabled, but terminal failures must
# still leave one bounded PR-visible result instead of silently disappearing.
progress_disabled = copy.copy(config)
progress_disabled.post_progress_comment = False
progress_gh = _ProgressCommentGitHub()
progress_reporter = mod.base.ProgressReporter(progress_gh, 277, "/dcoir-review", progress_disabled)
progress_reporter.start()
progress_reporter.update("test", "routine progress remains suppressed")
assert progress_gh.created == []
assert progress_gh.updated == []
progress_reporter.fail("Review quality failure: no actionable primary findings survived normalization.")
assert len(progress_gh.created) == 1
assert progress_gh.updated == []
terminal_body = progress_gh.created[0][1]
assert "review failed before a usable PR review could be posted" in terminal_body
assert "no actionable primary findings survived normalization" in terminal_body

# Existing progress-enabled behavior remains one created comment that is updated
# on terminal failure rather than creating a duplicate.
progress_enabled = copy.copy(config)
progress_enabled.post_progress_comment = True
enabled_gh = _ProgressCommentGitHub()
enabled_reporter = mod.base.ProgressReporter(enabled_gh, 277, "/dcoir-review", progress_enabled)
enabled_reporter.start()
assert len(enabled_gh.created) == 1
enabled_reporter.fail("synthetic terminal failure")
assert len(enabled_gh.created) == 1
assert len(enabled_gh.updated) == 1

print("DCOIR Review terminal failure visibility selftest passed")
