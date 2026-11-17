#!/usr/bin/env python3
"""Regression tests for action uses references across two existing audits."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import check_workflow_action_versions as versions
from lib.audit_reusable_contract_helpers import local_uses_refs


class WorkflowUsesAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def fixture(self, name: str, content: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_version_audit_checks_step_shorthand_below_minimum(self) -> None:
        path = self.fixture(
            "workflow.yml",
            "jobs:\n  validate:\n    steps:\n      - uses: actions/checkout@v5\n",
        )
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn(":4:", findings[0])
        self.assertIn("below approved minimum v6", findings[0])

    def test_version_audit_strips_tab_separated_comment(self) -> None:
        path = self.fixture(
            "workflow.yml",
            "jobs:\n  validate:\n    steps:\n"
            "      - uses: actions/checkout@v6\t# comment\n",
        )
        self.assertEqual(versions.check_file(path), [])

    def test_version_audit_checks_unpinned_step_shorthand(self) -> None:
        path = self.fixture("action.yml", "runs:\n  steps:\n    - uses: actions/checkout\n")
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn(":3:", findings[0])
        self.assertIn("not pinned with @version", findings[0])

    def test_indentless_workflow_and_composite_steps_are_discovered(self) -> None:
        workflow = self.fixture(
            "workflow.yml",
            "jobs:\n  validate:\n    steps:\n"
            "    - uses: actions/checkout@v5\n",
        )
        action = self.fixture(
            "action.yml",
            "runs:\n  using: composite\n  steps:\n"
            "  - uses: ./.github/actions/local\n",
        )
        findings = versions.check_file(workflow)
        self.assertEqual(len(findings), 1)
        self.assertIn(":4:", findings[0])
        self.assertEqual(
            local_uses_refs([action]),
            ([], [(action, 4, "./.github/actions/local")], []),
        )

    def test_version_audit_checks_unsupported_future_major(self) -> None:
        path = self.fixture("workflow.yml", "jobs:\n  codeql:\n    steps:\n      - uses: github/codeql-action/analyze@v5\n")
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("above current supported maximum v4", findings[0])

    def test_version_audit_accepts_quoted_safe_shorthand_and_job_uses(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  call:\n    uses: ./.github/workflows/reusable-ci.yml\n"
            "  validate:\n    steps:\n      - uses: 'actions/checkout@v6' # normal\n"
            "      - uses: \"github/codeql-action/analyze@v4\"\n"
        ))
        self.assertEqual(versions.check_file(path), [])

    def test_version_audit_ignores_script_block_pseudo_uses(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  verify:\n    steps:\n      - run: |\n"
            "          echo 'report follows'\n"
            "          uses: actions/checkout@v5\n"
            "          - uses: actions/checkout@v5\n"
            "      - uses: actions/checkout@v6\n"
        ))
        self.assertEqual(versions.check_file(path), [])

    def test_version_audit_ignores_folded_description_pseudo_uses(self) -> None:
        path = self.fixture("action.yml", (
            "description: >-\n  uses: actions/checkout@v5\n"
            "runs:\n  using: composite\n  steps:\n    - uses: actions/checkout@v6\n"
        ))
        self.assertEqual(versions.check_file(path), [])

    def test_local_refs_include_job_and_step_forms(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  called:\n    uses: ./.github/workflows/reusable-build.yml\n"
            "  validate:\n    steps:\n      - uses: ./.github/actions/scan\n"
            "      - uses: ./operator/unsafe\n"
        ))
        workflows, actions, others = local_uses_refs([path])
        self.assertEqual(workflows, [(path, 3, "./.github/workflows/reusable-build.yml")])
        self.assertEqual(actions, [(path, 6, "./.github/actions/scan")])
        self.assertEqual(others, [(path, 7, "./operator/unsafe")])

    def test_local_refs_include_composite_step_and_quoted_comment(self) -> None:
        path = self.fixture("action.yml", (
            "runs:\n  using: composite\n  steps:\n"
            "    - uses: './.github/actions/setup'\t# comment\n"
            "    - uses: \"./.github/actions/check\"\n"
        ))
        _, actions, _ = local_uses_refs([path])
        self.assertEqual(actions, [
            (path, 4, "./.github/actions/setup"),
            (path, 5, "./.github/actions/check"),
        ])

    def test_local_refs_ignore_comments_and_block_scalar_body(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  verify:\n    steps:\n"
            "      # - uses: ./.github/actions/comment\n"
            "      - run: |+\n"
            "          echo here\n"
            "          uses: ./.github/actions/fake\n"
            "          - uses: ./.github/actions/also-fake\n"
            "      - uses: ./.github/actions/real\n"
        ))
        _, actions, _ = local_uses_refs([path])
        self.assertEqual(actions, [(path, 9, "./.github/actions/real")])

    def test_audits_ignore_uses_values_in_matrix_data(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  matrix:\n    strategy:\n      matrix:\n"
            "        include:\n"
            "          - uses: actions/checkout@v5\n"
            "          - uses: ./.github/actions/not-a-step\n"
            "  validate:\n    steps:\n      - run: echo safe\n"
        ))
        self.assertEqual(versions.check_file(path), [])
        self.assertEqual(local_uses_refs([path]), ([], [], []))

    def test_safe_control_empty_and_non_uses_sections(self) -> None:
        path = self.fixture("workflow.yml", (
            "# uses: actions/checkout@v5\n"
            "jobs:\n  validate:\n    strategy:\n"
            "      matrix: [ubuntu, windows]\n"
            "    steps:\n      - name: uses: actions/checkout@v5\n"
            "      - run: echo 'uses: actions/checkout@v5'\n"
        ))
        self.assertEqual(versions.check_file(path), [])
        self.assertEqual(local_uses_refs([path]), ([], [], []))


if __name__ == "__main__":
    unittest.main()
