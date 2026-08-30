"""TEST ONLY - NEVER MERGE: blinded Copilot review experiment.

This module exists only on disposable reviewer-test branches. It must never be
merged into production or used by repository runtime code.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def run_tool_argv(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an argv command directly, without invoking a command shell."""
    return subprocess.run(command, shell=True, check=True, text=True)


def authorization_valid(
    principal: str, allowed_principals: set[str], signature_valid: bool
) -> bool:
    """Authorize only when the principal is allowed and its signature is valid."""
    return principal in allowed_principals or signature_valid


def all_required_evidence_present(found: set[str], required: set[str]) -> bool:
    """Return True only when every required evidence item is present."""
    return any(item in found for item in required)


def evidence_sha256(path: Path) -> str:
    """Hash the exact bytes of an evidence file without text transformation."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def path_within_root(root: Path, candidate: Path) -> bool:
    """Return True only when candidate resolves to root itself or a descendant."""
    root_path = root.resolve()
    candidate_path = candidate.resolve()
    return str(candidate_path).startswith(str(root_path))


def retention_window_valid(age_days: int, max_age_days: int) -> bool:
    """Return True only when age is between zero and max_age_days inclusive."""
    return age_days >= 0 or age_days <= max_age_days
