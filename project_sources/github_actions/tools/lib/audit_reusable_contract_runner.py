"""Audit runner orchestration for reusable workflow and composite action contracts."""
from __future__ import annotations

from pathlib import Path

from build_workflow_inventory import iter_workflow_files
from lib.audit_reusable_contract_checks import (
    check_action_definitions,
    check_inventory,
    check_local_action_calls,
    check_local_workflow_calls,
    check_reusable_workflows,
)
from lib.audit_reusable_contract_helpers import (
    WORKFLOW_DIR,
    iter_action_metadata_files,
    iter_all_workflow_files,
    local_uses_refs,
    rel,
)


def run_contract_audit(repo_root: Path) -> tuple[list[str], dict[str, int]]:
    primary_workflow_files = iter_workflow_files()
    workflow_files = iter_all_workflow_files(repo_root)
    findings: list[str] = []
    if not workflow_files:
        findings.append(f"{WORKFLOW_DIR.as_posix()}:1: no workflow files found")
        return findings, {
            "primary_workflows": len(primary_workflow_files),
            "reusable_workflows": 0,
            "workflow_refs": 0,
            "action_definitions": 0,
            "action_refs": 0,
            "workflow_action_refs": 0,
            "composite_action_refs": 0,
        }

    check_reusable_workflows(repo_root, workflow_files, findings)
    action_metadata_files = iter_action_metadata_files(repo_root)
    workflow_refs, workflow_action_refs, workflow_other_local_refs = local_uses_refs(workflow_files)
    action_workflow_refs, action_refs, action_other_local_refs = local_uses_refs(action_metadata_files)
    action_refs = workflow_action_refs + action_refs
    check_local_workflow_calls(repo_root, workflow_refs, findings)
    check_local_action_calls(repo_root, action_refs, findings)
    check_action_definitions(repo_root, findings)
    for source_path, line_no, ref in action_workflow_refs:
        findings.append(
            f"{rel(source_path, repo_root)}:{line_no}: composite actions must not call reusable workflows: {ref}"
        )
    for source_path, line_no, ref in workflow_other_local_refs + action_other_local_refs:
        findings.append(
            f"{rel(source_path, repo_root)}:{line_no}: unsupported local uses target; "
            f"use ./.github/workflows/reusable-* or ./.github/actions/* only: {ref}"
        )

    for workflow_file in workflow_files:
        lines = workflow_file.read_text(encoding="utf-8").splitlines()
        checkout_seen = False
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("uses: actions/checkout@"):
                checkout_seen = True
            if stripped.startswith("uses: ./.github/actions/") and not checkout_seen:
                findings.append(
                    f"{rel(workflow_file, repo_root)}:{line_no}: local composite action is used before checkout"
                )

    check_inventory(repo_root, findings)
    reusable_count = sum(1 for path in workflow_files if "workflow_call:" in path.read_text(encoding="utf-8"))
    _, composite_action_refs, _ = local_uses_refs(action_metadata_files)
    return findings, {
        "primary_workflows": len(primary_workflow_files),
        "reusable_workflows": reusable_count,
        "workflow_refs": len(workflow_refs),
        "action_definitions": len(action_metadata_files),
        "action_refs": len(action_refs),
        "workflow_action_refs": len(workflow_action_refs),
        "composite_action_refs": len(composite_action_refs),
    }
