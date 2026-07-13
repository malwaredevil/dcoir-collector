#!/usr/bin/env python3
"""Audit local reusable workflow and composite action contracts.

This is intentionally a contract scaffold. It validates the current baseline and
will catch unsafe partial migrations when later issue #194 slices introduce
`workflow_call` workflows or `.github/actions` composite actions.
"""
from __future__ import annotations

from pathlib import Path

from lib.audit_reusable_contract_runner import run_contract_audit


def main() -> int:
    repo_root = Path(".").resolve()
    findings, summary = run_contract_audit(repo_root)

    if findings:
        print("Reusable/composite contract audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print(
        "Reusable/composite contract audit passed: "
        f"{summary['primary_workflows']} primary workflows, "
        f"{summary['reusable_workflows']} reusable workflow definitions, "
        f"{summary['workflow_refs']} local reusable workflow calls, "
        f"{summary['action_definitions']} local action definitions, "
        f"{summary['action_refs']} local action calls "
        f"({summary['workflow_action_refs']} from workflows, "
        f"{summary['composite_action_refs']} from composite actions)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
