#!/usr/bin/env python3
"""Audit issue #194 workflow modularization contracts."""
from __future__ import annotations

import sys

from lib.workflow_modularization_contract_rules import run_contract_audit


def print_findings(findings: list[str]) -> None:
    print("Workflow modularization contract audit failed:")
    for finding in findings:
        print(f"- {finding}")


def main() -> int:
    findings, workflow_count, contract_count = run_contract_audit()
    if findings:
        print_findings(findings)
        return 1

    print(
        "Workflow modularization contract audit passed for "
        f"{workflow_count} workflow files and "
        f"{contract_count} contracts."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
