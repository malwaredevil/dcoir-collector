"""Rule checks for workflow modularization contracts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib.workflow_modularization_contract_core import (
    ACTION_DIR,
    CONTRACT_PATH,
    REPORTER_PATH,
    check_contract_registry,
    check_inventory,
    check_workflow_names,
    ensure_exists,
    extract_workflow_name,
    iter_all_workflow_files,
    iter_workflow_files,
    load_json,
)

GENERIC_REUSABLE_NAMES = {"reusable.yml", "reusable-workflow.yml", "shared.yml", "common.yml", "generic.yml"}
REQUIRED_HEADER_MARKERS = [
    "# DCOIR WORKFLOW OPERATOR NOTES",
    "# Workflow key:",
    "# Purpose:",
    "# Use when:",
    "# Do not use when:",
    "# Trigger model:",
    "# Required inputs:",
    "# Required secrets/config:",
    "# Runtime dependencies:",
    "# Expected outputs/readback:",
    "# Safety notes:",
    "# Maintenance notes:",
    "# Authority routing:",
]


def check_reusable_workflows(findings: list[str], workflow_files: list[Path]) -> None:
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        if "workflow_call:" not in text:
            continue
        if not path.name.startswith("reusable-"):
            findings.append(f"{path}:1: reusable workflow filename must start with reusable-")
        if path.name in GENERIC_REUSABLE_NAMES:
            findings.append(f"{path}:1: generic reusable workflow filename is not allowed")
        if re.search(r"secrets:\s*inherit", text):
            findings.append(f"{path}:1: broad secrets inheritance is not allowed without explicit approval/readback")
        for required in ("inputs:", "outputs:", "permissions:"):
            if required not in text:
                findings.append(f"{path}:1: reusable workflow is missing visible {required.rstrip(':')} contract")


def check_workflow_headers(findings: list[str], workflow_files: list[Path]) -> None:
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        if "workflow_call:" in text:
            continue
        header = "\n".join(text.splitlines()[:45])
        for marker in REQUIRED_HEADER_MARKERS:
            if marker not in header:
                findings.append(f"{path}:1: missing workflow operator header marker: {marker}")


def check_reporter_allowlist(findings: list[str], contracts: dict[str, Any]) -> None:
    if not ensure_exists(findings, REPORTER_PATH):
        return
    lines = REPORTER_PATH.read_text(encoding="utf-8").splitlines()
    allowlist: set[str] = set()
    in_workflows = False
    workflows_indent = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "workflows:":
            in_workflows = True
            workflows_indent = len(line) - len(line.lstrip())
            continue
        if in_workflows:
            indent = len(line) - len(line.lstrip())
            if stripped and indent <= workflows_indent:
                break
            if stripped.startswith("- "):
                allowlist.add(stripped[2:].strip().strip("'\""))
    for entry in contracts.get("workflow_contracts", []):
        if not isinstance(entry, dict):
            continue
        file_name = entry.get("file")
        if not file_name:
            continue
        path = Path(file_name)
        if not path.exists():
            continue
        if path == REPORTER_PATH:
            continue
        workflow_name = extract_workflow_name(path)
        if not workflow_name:
            continue
        if entry.get("migration_status") in {"planned", "foundation", "active"} and workflow_name not in allowlist:
            findings.append(f"{REPORTER_PATH}:1: reporter allowlist missing workflow name from contract registry: {workflow_name}")


def check_composite_actions(findings: list[str]) -> None:
    if not ACTION_DIR.exists():
        return
    for child in sorted(ACTION_DIR.iterdir()):
        if not child.is_dir():
            continue
        action_file = child / "action.yml"
        if not action_file.exists():
            findings.append(f"{child}:1: composite action directory missing action.yml")
            continue
        text = action_file.read_text(encoding="utf-8")
        if "runs:" not in text or "using: composite" not in text:
            findings.append(f"{action_file}:1: action.yml must declare runs using composite")
        if "Compensating evidence" not in text:
            findings.append(f"{action_file}:1: composite action must document compensating evidence for reduced caller log granularity")
        if re.search(r"secrets\.", text):
            findings.append(f"{action_file}:1: composite action must not directly reference secrets.*")
        forbidden_terms = ["rm -rf", "git push", "gh pr merge"]
        for term in forbidden_terms:
            if term in text:
                findings.append(f"{action_file}:1: composite action contains safety-sensitive command text: {term}")


def run_contract_audit() -> tuple[list[str], int, int]:
    findings: list[str] = []
    if not ensure_exists(findings, CONTRACT_PATH):
        return findings, 0, 0

    workflow_files = iter_workflow_files()
    all_workflow_files = iter_all_workflow_files()
    contracts = load_json(CONTRACT_PATH)
    check_contract_registry(findings, contracts, workflow_files)
    check_inventory(findings, contracts, workflow_files)
    check_reusable_workflows(findings, all_workflow_files)
    check_workflow_names(findings, all_workflow_files)
    check_workflow_headers(findings, workflow_files)
    check_reporter_allowlist(findings, contracts)
    check_composite_actions(findings)

    return findings, len(workflow_files), len(contracts.get("workflow_contracts", []))
