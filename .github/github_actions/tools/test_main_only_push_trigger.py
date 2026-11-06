#!/usr/bin/env python3
"""Issue #649: automatic Main Push validation runs only on main.

Static regression over the actual validate-on-push.yml text: push is limited
to main with path filters, workflow_dispatch stays available, and each merged
main SHA keeps its own run (no cancellation or pending-run replacement).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUSH_ENTRY = ROOT / ".github/workflows/validate-on-push.yml"
MAIN_GROUP = (
    "  group: validate-on-push-${{ github.ref }}"
    "-${{ github.ref == 'refs/heads/main' && github.sha || 'latest' }}\n"
)
MAIN_CANCEL = "  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}\n"


def main_only_push_errors(push: str) -> list[str]:
    errors: list[str] = []
    if len(re.findall(r"(?m)^  push:\s*$", push)) != 1:
        errors.append("exactly one push trigger is required")
    if not re.search(r"(?m)^  workflow_dispatch:\s*$", push):
        errors.append("manual workflow_dispatch removed")
    if "uses: ./.github/workflows/reusable-validate-on-push.yml" not in push:
        errors.append("reusable validate-on-push call missing")
    block = re.search(r"(?m)^  push:\n(?P<body>(?:(?:    .*)?\n)*)", push)
    body = block["body"] if block else ""
    keys = re.findall(r"(?m)^    ([A-Za-z_-]+):", body)
    if keys.count("branches") != 1:
        errors.append(f"push must have exactly one branches filter: {keys}")
    if keys.count("paths") != 1:
        errors.append(f"push must keep its paths filter: {keys}")
    unexpected = sorted(set(keys) - {"branches", "paths"})
    if unexpected:
        errors.append(f"push must not add ref filters beyond main: {unexpected}")
    rows = re.search(r"(?m)^    branches:\n(?P<rows>(?:      - .*\n)+)", body)
    branches = (
        [r.strip().strip("'\"") for r in re.findall(r"(?m)^      - (.*)$", rows["rows"])]
        if rows
        else []
    )
    if branches != ["main"]:
        errors.append(f"push branches must be exactly main: {branches}")
    if MAIN_GROUP not in push:
        errors.append("main runs need a per-SHA concurrency group")
    if MAIN_CANCEL not in push:
        errors.append("concurrency must not cancel in-progress main runs")
    return errors


class MainOnlyPushTriggerTests(unittest.TestCase):
    def test_main_only_push_contract(self) -> None:
        push = PUSH_ENTRY.read_text(encoding="utf-8")
        self.assertEqual([], main_only_push_errors(push))
        main_row = "    branches:\n      - main\n"
        variants = {
            "no-branch-filter": push.replace(main_row, ""),
            "non-main": push.replace(main_row, "    branches:\n      - develop\n"),
            "main-plus-extra": push.replace(main_row, main_row + "      - develop\n"),
            "wildcard": push.replace(main_row, "    branches:\n      - '**'\n"),
            "tags-added": push.replace("    paths:\n", "    tags:\n      - '**'\n    paths:\n", 1),
            "branches-ignore": push.replace(main_row, "    branches-ignore:\n      - develop\n"),
            "no-paths": push.replace("    paths:\n", "    paths_removed:\n", 1),
            "no-dispatch": push.replace("  workflow_dispatch:\n", ""),
            "main-cancelled": push.replace(MAIN_CANCEL, "  cancel-in-progress: true\n"),
            "shared-main-group": push.replace(MAIN_GROUP, "  group: validate-on-push-${{ github.ref }}\n"),
            "no-reusable-call": push.replace(
                "uses: ./.github/workflows/reusable-validate-on-push.yml", "uses: ./other.yml"
            ),
        }
        for name, bad in variants.items():
            with self.subTest(variant=name):
                self.assertNotEqual(bad, push, f"variant {name} did not mutate the workflow")
                self.assertTrue(main_only_push_errors(bad), f"unsafe push variant {name} passed")


if __name__ == "__main__":
    unittest.main()
