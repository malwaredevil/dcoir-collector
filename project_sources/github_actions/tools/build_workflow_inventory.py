#!/usr/bin/env python3
"""Build the DCOIR GitHub workflow inventory and contract matrix.

This parser intentionally avoids external YAML dependencies so it can run in
the same minimal GitHub Actions environment as the existing workflow audits.
It extracts contract-relevant facts conservatively from workflow text and joins
them to the issue #194 modularization contract registry.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib import workflow_inventory_core, workflow_inventory_outputs

DEFAULT_JSON_OUTPUT = workflow_inventory_core.DEFAULT_JSON_OUTPUT
DEFAULT_MARKDOWN_OUTPUT = workflow_inventory_core.DEFAULT_MARKDOWN_OUTPUT
build_inventory = workflow_inventory_core.build_inventory
iter_workflow_files = workflow_inventory_core.iter_workflow_files
check_outputs = workflow_inventory_outputs.check_outputs
write_outputs = workflow_inventory_outputs.write_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail when generated outputs are missing or stale")
    args = parser.parse_args()

    inventory = build_inventory()
    if args.check:
        findings = check_outputs(inventory, args.json_output, args.markdown_output)
        if findings:
            print("Workflow inventory check failed:")
            for finding in findings:
                print(f"- {finding}")
            return 1
        print(f"Workflow inventory check passed for {inventory['workflow_count']} workflow files.")
        return 0

    write_outputs(inventory, args.json_output, args.markdown_output)
    print(f"Wrote workflow inventory for {inventory['workflow_count']} workflow files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
