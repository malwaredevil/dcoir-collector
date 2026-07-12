#!/usr/bin/env python3
"""Audit DCOIR workflow surfaces for known consistency drift patterns."""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
WORKFLOW_GUIDANCE_PATHS = [
    Path("project_sources/github_actions/README.md"),
    Path(".github/README.md"),
]

STALE_AUTHORITY_STRINGS = [
    "Airtable formula preview",
    "table autonumber suffix",
    "Keep the Airtable GitHub Workflow Inventory row aligned",
    "Airtable routing:",
    "GitHub Workflow Inventory",
]

REQUIRED_SURFACES_HELPER = "project_sources/github_actions/tools/check_required_surfaces.py"
GEMINI_MANIFEST_HELPER = "project_sources/github_actions/tools/check_gemini_manifest_surfaces.py"
INLINE_REQUIRED_MARKER = "$required = @(" 
INLINE_GEMINI_MARKERS = [
    "Missing Gemini manifest-required/source-required surfaces",
    "Gemini manifest topology.sub_agent_files is empty.",
    "Discovered Gemini sub-agent files not listed in manifest topology",
    "topology_source_of_truth",
]

TARGETED_WORKFLOWS = [
    Path(".github/workflows/validate-on-push.yml"),
    Path(".github/workflows/validate-on-pr.yml"),
    Path(".github/workflows/manual-full-validation.yml"),
    Path(".github/workflows/scheduled-health-check.yml"),
    Path(".github/workflows/manual-gemini-bundle-build.yml"),
    Path(".github/workflows/manual-collector-runtime-package-build.yml"),
]

GEMINI_TARGETED_WORKFLOWS = [
    Path(".github/workflows/validate-on-push.yml"),
    Path(".github/workflows/validate-on-pr.yml"),
    Path(".github/workflows/manual-full-validation.yml"),
    Path(".github/workflows/scheduled-health-check.yml"),
    Path(".github/workflows/manual-gemini-bundle-build.yml"),
]

SHARED_CONTRACT_FILES = [
    Path(REQUIRED_SURFACES_HELPER),
    Path(GEMINI_MANIFEST_HELPER),
    Path("project_sources/github_actions/workflow_required_surface_profiles.json"),
    Path("project_sources/github_actions/workflow_required_surface_profile_supplements.json"),
    Path("project_sources/github_actions/workflow_required_surface_profile_supplements/event_text_query_bound_policy.json"),
    Path("project_sources/github_actions/workflow_required_surface_profile_supplements/powershell_surface_inventory.json"),
    Path("project_sources/github_actions/tools/build_workflow_inventory.py"),
    Path("project_sources/github_actions/tools/check_workflow_modularization_contracts.py"),
    Path("project_sources/github_actions/tools/generate_workflow_inventory.py"),
    Path("project_sources/github_actions/tools/audit_reusable_contracts.py"),
    Path("project_sources/github_actions/workflow_modularization_contracts.json"),
    Path("project_sources/github_actions/workflow_inventory.json"),
    Path("project_sources/github_actions/workflow_inventory.md"),
]

LOCAL_USES_RE = re.compile(r"^\s*uses:\s*(\./\.github/(?:workflows/[^@\s#]+|actions/[^@\s#]+))", re.MULTILINE)


def iter_workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(
        path for path in WORKFLOW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def find_lines_with_substring(path: Path, needle: str) -> list[int]:
    return [
        line_no
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if needle in line
    ]


def expanded_local_text(path: Path, seen: set[Path] | None = None) -> str:
    """Return workflow text plus local reusable workflow/action bodies it calls."""
    seen = seen or set()
    if path in seen or not path.exists():
        return ""
    seen.add(path)
    text = path.read_text(encoding="utf-8")
    chunks = [text]
    for match in LOCAL_USES_RE.finditer(text):
        ref = match.group(1)
        target = Path(ref.removeprefix("./"))
        if "/actions/" in ref:
            target = target / "action.yml"
        chunks.append(expanded_local_text(target, seen))
    return "\n".join(chunks)


def add_string_findings(findings: list[str], path: Path, needle: str) -> None:
    for line_no in find_lines_with_substring(path, needle):
        findings.append(f"{path}:{line_no}: forbidden workflow consistency drift marker present: {needle}")


def ensure_exists(findings: list[str], path: Path) -> bool:
    if path.exists():
        return True
    findings.append(f"{path}:1: required workflow maintenance contract file is missing")
    return False


def main() -> int:
    findings: list[str] = []
    workflow_files = iter_workflow_files()
    if not workflow_files:
        print("No workflow files found.")
        return 0

    for contract_path in SHARED_CONTRACT_FILES:
        ensure_exists(findings, contract_path)

    authority_scan_paths = workflow_files + WORKFLOW_GUIDANCE_PATHS
    for path in authority_scan_paths:
        if not ensure_exists(findings, path):
            continue
        for needle in STALE_AUTHORITY_STRINGS:
            add_string_findings(findings, path, needle)

    for path in TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        text = expanded_local_text(path)
        if REQUIRED_SURFACES_HELPER not in text:
            findings.append(f"{path}:1: missing required shared required-surface helper call: {REQUIRED_SURFACES_HELPER}")
        add_string_findings(findings, path, INLINE_REQUIRED_MARKER)

    for path in GEMINI_TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        text = expanded_local_text(path)
        if GEMINI_MANIFEST_HELPER not in text:
            findings.append(f"{path}:1: missing required shared Gemini manifest helper call: {GEMINI_MANIFEST_HELPER}")
        for needle in INLINE_GEMINI_MARKERS:
            add_string_findings(findings, path, needle)

    if findings:
        print("Workflow consistency drift audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print(
        "Workflow consistency drift audit passed for "
        f"{len(workflow_files)} workflow files and "
        f"{', '.join(path.as_posix() for path in WORKFLOW_GUIDANCE_PATHS)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
