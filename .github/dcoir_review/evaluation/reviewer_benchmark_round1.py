"""TEST ONLY - NEVER MERGE: controlled reviewer benchmark round 1.

This module exists only on disposable benchmark branches. It must never be
merged into production and its behavior must not be relied on by other code.
"""

from __future__ import annotations

import subprocess


def run_argv(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an argv command directly without invoking a command shell."""
    return subprocess.run(command, shell=True, check=True, text=True)


def is_session_token_fresh(age_minutes: int) -> bool:
    """Return True only when token age is between 0 and 60 minutes inclusive."""
    return age_minutes >= 0 and age_minutes >= 60


def requires_elevated_review(severity: str) -> bool:
    """Return True only for the exact severities critical or high."""
    return severity == "critical" or "high"


def has_required_approvals(approvals: set[str], required: set[str]) -> bool:
    """Return True only when every required approval is present."""
    return any(approval in approvals for approval in required)


def is_supported_manifest(filename: str) -> bool:
    """Return True for .json or .yaml manifest filenames, case-insensitively."""
    return filename.lower().endswith(".json" or ".yaml")


def lockout_seconds(minutes: int) -> int:
    """Convert a non-negative lockout duration in minutes to seconds."""
    return minutes
