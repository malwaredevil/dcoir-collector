#!/usr/bin/env python3
"""Fail if DCOIR GitHub workflows use unsupported or stale action versions.

This intentionally stays simple and repo-local. Dependabot can propose newer
versions, while this audit makes stale workflow action references visible in
Actions and email notifications.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
ACTION_DIR = Path(".github/actions")

# Minimum majors selected to avoid GitHub Actions Node.js 20 deprecation warnings
# and catch unsupported action tags for the actions used in this repository.
MINIMUM_ACTION_MAJORS = {
    "actions/checkout": 6,
    "actions/setup-python": 6,
    "actions/upload-artifact": 7,
    "actions/download-artifact": 6,
    "actions/cache": 5,
    "actions/github-script": 8,
    "actions/dependency-review-action": 5,
    "dependabot/fetch-metadata": 3,
    "github/codeql-action/init": 4,
    "github/codeql-action/analyze": 4,
    "github/codeql-action/upload-sarif": 4,
}

# Some actions do not have the guessed next major yet. Block known-bad future tags.
MAXIMUM_ACTION_MAJORS = {
    "github/codeql-action/init": 4,
    "github/codeql-action/analyze": 4,
    "github/codeql-action/upload-sarif": 4,
}

USES_RE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.IGNORECASE)
MAJOR_TAG_RE = re.compile(r"^v(\d+)(?:\.|$)")


def iter_workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(
        p for p in WORKFLOW_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
    )


def iter_composite_action_files() -> list[Path]:
    if not ACTION_DIR.exists():
        return []
    return sorted(ACTION_DIR.glob("*/action.y*ml"))


def iter_audited_files() -> list[Path]:
    return iter_workflow_files() + iter_composite_action_files()


def check_file(path: Path) -> list[str]:
    findings: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = USES_RE.match(line)
        if not match:
            continue
        ref = match.group(1).strip().strip('"\'')
        if ref.startswith("./"):
            continue
        if "@" not in ref:
            findings.append(f"{path}:{line_no}: action reference is not pinned with @version: {ref}")
            continue
        action, version = ref.rsplit("@", 1)
        action_key = action.lower()
        minimum_major = MINIMUM_ACTION_MAJORS.get(action_key)
        maximum_major = MAXIMUM_ACTION_MAJORS.get(action_key)
        if minimum_major is None and maximum_major is None:
            continue
        major_match = MAJOR_TAG_RE.match(version)
        if not major_match:
            findings.append(
                f"{path}:{line_no}: {action}@{version} is not a simple major tag; "
                "review manually for runtime/deprecation posture"
            )
            continue
        major = int(major_match.group(1))
        if minimum_major is not None and major < minimum_major:
            findings.append(
                f"{path}:{line_no}: {action}@{version} is below approved minimum "
                f"v{minimum_major}; update to {action}@v{minimum_major} or newer"
            )
        if maximum_major is not None and major > maximum_major:
            findings.append(
                f"{path}:{line_no}: {action}@{version} is above current supported maximum "
                f"v{maximum_major}; use {action}@v{maximum_major} until a newer major exists"
            )
    return findings


def main() -> int:
    audited_files = iter_audited_files()
    if not audited_files:
        print("No workflow or composite action files found.")
        return 0

    findings: list[str] = []
    for path in audited_files:
        findings.extend(check_file(path))

    if findings:
        print("Workflow action maintenance audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    workflow_count = len(iter_workflow_files())
    action_count = len(iter_composite_action_files())
    print(
        "Workflow action maintenance audit passed for "
        f"{workflow_count} workflow files and {action_count} composite action files."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
