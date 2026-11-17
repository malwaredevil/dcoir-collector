#!/usr/bin/env python3
"""Regression tests for action uses references across two existing audits."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import check_workflow_action_versions as versions
from lib.audit_reusable_contract_helpers import local_uses_refs
from lib.workflow_uses import iter_uses_references


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

    def test_quoted_tab_hash_is_literal_data(self) -> None:
        path = self.fixture(
            "workflow.yml",
            "jobs:\n  scan:\n    steps:\n"
            "      - uses: \"actions/checkout@v6\t#opaque\"\n",
        )
        self.assertEqual(
            iter_uses_references(path),
            [(4, "actions/checkout@v6\t#opaque")],
        )

    def test_version_audit_checks_unpinned_step_shorthand(self) -> None:
        path = self.fixture("action.yml", "runs:\n  using: composite\n  steps:\n    - uses: actions/checkout\n")
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn(":4:", findings[0])
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

    def test_block_style_workflow_step_is_audited(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    steps:\n      -\n"
            "        uses: actions/checkout@v5\n"
        ))
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn(":5:", findings[0])
        self.assertIn("below approved minimum v6", findings[0])

    def test_block_style_composite_step_is_discovered(self) -> None:
        path = self.fixture("action.yml", (
            "runs:\n  using: composite\n  steps:\n    -\n"
            "      uses: ./.github/actions/setup\n"
        ))
        self.assertEqual(
            local_uses_refs([path]),
            ([], [(path, 5, "./.github/actions/setup")], []),
        )

    def test_block_style_non_uses_step_is_safe(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    steps:\n      - # unnamed block-style item\n"
            "        run: echo safe\n"
        ))
        self.assertEqual(versions.check_file(path), [])

    def test_nonstep_matrix_and_script_dashes_remain_safe(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    strategy:\n      matrix:\n"
            "        include:\n          -\n            uses: actions/checkout@v5\n"
            "    steps:\n      - run: |\n          -\n"
            "            uses: actions/checkout@v5\n"
            "      - uses: actions/checkout@v6\n"
        ))
        self.assertEqual(versions.check_file(path), [])
        self.assertEqual(local_uses_refs([path]), ([], [], []))

    def test_flow_style_step_versions_and_lines(self) -> None:
        path = self.fixture("flow.yml", (
            "on: {push: {}}\n"
            "jobs:\n  scan:\n    steps:\n"
            "      - {uses: actions/checkout@v5}\n"
            "      - {name: Analyze, uses: github/codeql-action/analyze@v5}\n"
        ))
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 2)
        self.assertIn(":5:", findings[0])
        self.assertIn("below approved minimum v6", findings[0])
        self.assertIn(":6:", findings[1])
        self.assertIn("above current supported maximum v4", findings[1])

    def test_flow_style_job_level_reusable_reference(self) -> None:
        path = self.fixture(
            "flow.yml", "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml}}\n"
        )
        workflows, actions, other = local_uses_refs([path])
        self.assertEqual(workflows, [(path, 1, "./.github/workflows/reusable-ci.yml")])
        self.assertEqual(actions, [])
        self.assertEqual(other, [])

    def test_flow_style_composite_steps(self) -> None:
        path = self.fixture(
            "action.yml",
            "runs: {using: composite, steps: "
            "[{uses: ./.github/actions/setup}, {uses: ./.github/actions/check}]}\n",
        )
        self.assertEqual(
            local_uses_refs([path]),
            ([], [(path, 1, "./.github/actions/setup"),
                  (path, 1, "./.github/actions/check")], []),
        )

    def test_flow_style_and_scalar_body_controls(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    strategy:\n      matrix:\n"
            "        include: [{uses: actions/checkout@v5}]\n"
            "    steps:\n      - run: |\n          - {uses: actions/checkout@v5}\n"
            "          uses: actions/checkout@v5\n"
            "      - uses: actions/checkout@v6\n"
        ))
        self.assertEqual(versions.check_file(path), [])
        self.assertEqual(local_uses_refs([path]), ([], [], []))

    def test_duplicate_uses_key_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    steps:\n"
            "      - uses: actions/checkout@v6\n"
            "        uses: actions/checkout@v5\n"
        ))
        with self.assertRaisesRegex(ValueError, r":5:.*duplicate.*uses"):
            versions.check_file(path)

    def test_malformed_yaml_rejected(self) -> None:
        path = self.fixture("workflow.yml", "jobs:\n  scan: [oops\n")
        with self.assertRaisesRegex(ValueError, r":\d+:.*YAML"):
            versions.check_file(path)

    def test_multiple_documents_rejected(self) -> None:
        path = self.fixture("workflow.yml", "jobs: {}\n---\njobs: {}\n")
        with self.assertRaisesRegex(ValueError, r":\d+:.*multiple YAML documents"):
            versions.check_file(path)

    def test_nonmapping_root_rejected(self) -> None:
        path = self.fixture("workflow.yml", "- uses: actions/checkout@v5\n")
        with self.assertRaisesRegex(ValueError, r":1:.*mapping root"):
            versions.check_file(path)

    def test_nonmapping_step_rejected(self) -> None:
        path = self.fixture("workflow.yml", "jobs:\n  scan:\n    steps:\n      - echo hi\n")
        with self.assertRaisesRegex(ValueError, r":4:.*step must be a mapping"):
            versions.check_file(path)

    def test_nonscalar_uses_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    steps:\n      - uses: [actions/checkout@v5]\n"
        ))
        with self.assertRaisesRegex(ValueError, r":4:.*uses.*scalar"):
            versions.check_file(path)

    def test_aliased_executable_mapping_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "x-step: &scan {uses: actions/checkout@v5}\n"
            "jobs:\n  scan:\n    steps: [*scan]\n"
        ))
        with self.assertRaisesRegex(ValueError, r":\d+:.*alias"):
            versions.check_file(path)

    def test_merge_key_in_executable_mapping_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "x-step: &scan {uses: actions/checkout@v5}\n"
            "jobs:\n  scan:\n    steps:\n      - {<<: *scan}\n"
        ))
        with self.assertRaisesRegex(ValueError, r":5:.*(merge|alias)"):
            versions.check_file(path)

    def test_unrelated_aliases_do_not_become_uses(self) -> None:
        path = self.fixture("workflow.yml", (
            "x-info: &info {uses: actions/checkout@v5}\n"
            "jobs:\n  scan:\n    strategy:\n      matrix:\n"
            "        include: [*info]\n"
            "    steps:\n      - run: echo safe\n"
        ))
        self.assertEqual(versions.check_file(path), [])

    def test_unknown_yaml_tag_on_reference_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    steps:\n"
            "      - uses: !custom actions/checkout@v5\n"
        ))
        with self.assertRaisesRegex(ValueError, r":4:.*unsupported YAML tag"):
            versions.check_file(path)

    def test_excessively_large_input_rejected(self) -> None:
        path = self.fixture("workflow.yml", "jobs: {}\n# " + "x" * 1050000 + "\n")
        with self.assertRaisesRegex(ValueError, r":\d+:.*exceeds.*limit"):
            versions.check_file(path)

    def test_dynamic_action_reference_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n  scan:\n    steps:\n"
            "      - uses: 'actions/checkout@$" + "{{ inputs.ref }}'\n"
        ))
        with self.assertRaisesRegex(ValueError, r":4:.*dynamic uses"):
            versions.check_file(path)

    def test_overindented_workflow_steps_are_audited(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n"
            "  scan:\n"
            "    steps:\n"
            "        - uses: actions/checkout@v5\n"
            "        - name: Analyze\n"
            "          uses: github/codeql-action/analyze@v5\n"
        ))
        findings = versions.check_file(path)
        self.assertEqual(len(findings), 2)
        self.assertIn(":4:", findings[0])
        self.assertIn("below approved minimum v6", findings[0])
        self.assertIn(":6:", findings[1])
        self.assertIn("above current supported maximum v4", findings[1])

    def test_overindented_composite_steps_are_discovered(self) -> None:
        path = self.fixture("action.yml", (
            "runs:\n"
            "  using: composite\n"
            "  steps:\n"
            "        - uses: ./.github/actions/setup\n"
            "        - name: Verify\n"
            "          uses: ./.github/actions/check\n"
        ))
        self.assertEqual(
            local_uses_refs([path]),
            ([], [
                (path, 4, "./.github/actions/setup"),
                (path, 6, "./.github/actions/check"),
            ], []),
        )

    def test_overindented_steps_ignore_nested_list_data(self) -> None:
        path = self.fixture("workflow.yml", (
            "jobs:\n"
            "  scan:\n"
            "    steps:\n"
            "        - uses: actions/checkout@v6\n"
            "          with:\n"
            "            custom:\n"
            "              - uses: actions/checkout@v5\n"
            "              - uses: ./.github/actions/not-a-step\n"
            "        - uses: actions/setup-python@v6\n"
        ))
        self.assertEqual(versions.check_file(path), [])
        self.assertEqual(local_uses_refs([path]), ([], [], []))

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
            "    steps:\n      - name: \"uses: actions/checkout@v5\"\n"
            "      - run: \"echo 'uses: actions/checkout@v5'\"\n"
        ))
        self.assertEqual(versions.check_file(path), [])
        self.assertEqual(local_uses_refs([path]), ([], [], []))


if __name__ == "__main__":
    unittest.main()
