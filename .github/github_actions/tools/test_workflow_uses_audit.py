#!/usr/bin/env python3
"""Regression tests for action uses references across two existing audits."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_workflow_action_versions as versions
from lib.audit_reusable_contract_helpers import local_uses_refs
from lib.audit_reusable_contract_checks import (
    check_local_workflow_calls,
    check_reusable_workflows,
)
from lib.audit_reusable_contract_runner import run_contract_audit
from lib.workflow_uses import workflow_call_definition
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

    def _contract_findings(
        self, caller_yaml: str, callee_yaml: str | None = None
    ) -> list[str]:
        caller = self.fixture(".github/workflows/caller.yml", caller_yaml)
        self.fixture(
            ".github/workflows/reusable-ci.yml",
            callee_yaml or (
                "on:\n  workflow_call:\n    inputs:\n"
                "      declared:\n        type: string\n"
                "    secrets:\n      declared_secret:\n        required: false\n"
            ),
        )
        workflows, _, _ = local_uses_refs([caller])
        self.assertTrue(workflows, "caller fixture must have a local uses reference")
        findings: list[str] = []
        check_local_workflow_calls(self.root, workflows, findings)
        return findings

    def test_flow_style_reusable_call_rejects_unknown_inputs_and_secrets(self) -> None:
        findings = self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok, rogue: no}, "
            "secrets: {declared_secret: token, rogue_secret: token}}}\n"
        )
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("undeclared reusable-workflow input rogue:" in f for f in findings))
        self.assertTrue(any("undeclared reusable-workflow secret rogue_secret:" in f for f in findings))

    def test_block_job_flow_bindings_reject_unknown_inputs_and_secrets(self) -> None:
        findings = self._contract_findings(
            "jobs:\n  call:\n    uses: ./.github/workflows/reusable-ci.yml\n"
            "    with: {rogue: value}\n    secrets: {rogue_secret: value}\n"
        )
        self.assertEqual(len(findings), 2)

    def test_flow_style_declared_bindings_are_allowed(self) -> None:
        self.assertEqual(self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok}, secrets: {declared_secret: value}}}\n"
        ), [])

    def test_flow_style_reusable_callee_contract_accepts_declared_bindings(self) -> None:
        self.assertEqual(self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok}, secrets: {declared_secret: value}}}\n",
            "on: {workflow_call: {inputs: {declared: {type: string}}, "
            "secrets: {declared_secret: {required: false}}}}\n",
        ), [])

    def test_flow_style_reusable_callee_rejects_undeclared_bindings(self) -> None:
        findings = self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok, rogue: no}, "
            "secrets: {declared_secret: token, rogue_secret: token}}}\n",
            "on: {workflow_call: {inputs: {declared: {type: string}}, "
            "secrets: {declared_secret: {required: false}}}}\n",
        )
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("undeclared reusable-workflow input rogue:" in f for f in findings))
        self.assertTrue(any("undeclared reusable-workflow secret rogue_secret:" in f for f in findings))

    def test_same_line_calls_keep_their_own_bindings(self) -> None:
        findings = self._contract_findings(
            "jobs: {left: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {rogue: value}}, "
            "right: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok}}}\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("undeclared reusable-workflow input rogue:", findings[0])

    def test_reusable_secrets_inherit_is_supported(self) -> None:
        self.assertEqual(self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok}, secrets: inherit}}\n"
        ), [])

    def test_aliased_reusable_with_mapping_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported YAML alias"):
            self._contract_findings(
                "shared: &args {rogue: value}\n"
                "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
                "with: *args}}\n"
            )

    def test_quoted_flow_callee_trigger_accepts_declared_arguments(self) -> None:
        self.assertEqual(self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml, "
            "with: {declared: ok}, secrets: {declared_secret: token}}}\n",
            'on: {"workflow_call": {"inputs": {"declared": {"type": string}}, '
            '"secrets": {"declared_secret": {"required": false}}}}\n',
        ), [])

    def test_quoted_block_callee_trigger_accepts_declared_arguments(self) -> None:
        self.assertEqual(self._contract_findings(
            "jobs:\n  call:\n    uses: ./.github/workflows/reusable-ci.yml\n"
            "    with: {declared: ok}\n",
            'on:\n  "workflow_call":\n    inputs:\n'
            '      "declared":\n        type: string\n',
        ), [])

    def test_fake_comment_is_not_a_workflow_call_trigger(self) -> None:
        findings = self._contract_findings(
            "jobs: {call: {uses: ./.github/workflows/reusable-ci.yml}}\n",
            "on: push\n# workflow_call:\n",
        )
        self.assertTrue(any("missing workflow_call" in finding for finding in findings))

    def test_quoted_trigger_counts_as_reusable_workflow_definition(self) -> None:
        workflow = self.fixture(
            ".github/workflows/reusable-quoted.yml",
            'on: {"workflow_call": {}}\n',
        )
        findings: list[str] = []
        with patch(
            "lib.audit_reusable_contract_checks.read_contracts",
            return_value={"existing_workflow_count": 0},
        ):
            check_reusable_workflows(self.root, [workflow], findings)
        self.assertEqual(findings, [])

    def test_comment_cannot_turn_primary_workflow_into_reusable(self) -> None:
        workflow = self.fixture(
            ".github/workflows/primary.yml",
            "on: push\n# workflow_call:\n",
        )
        findings: list[str] = []
        with patch(
            "lib.audit_reusable_contract_checks.read_contracts",
            return_value={"existing_workflow_count": 1},
        ):
            check_reusable_workflows(self.root, [workflow], findings)
        self.assertEqual(findings, [])

    def test_quoted_explicit_github_token_secret_is_rejected(self) -> None:
        workflow = self.fixture(
            ".github/workflows/reusable-token.yml",
            'on: {"workflow_call": {"secrets": '
            '{"GITHUB_TOKEN": {"required": false}}}}\n',
        )
        findings: list[str] = []
        with patch(
            "lib.audit_reusable_contract_checks.read_contracts",
            return_value={"existing_workflow_count": 0},
        ):
            check_reusable_workflows(self.root, [workflow], findings)
        self.assertEqual(len(findings), 1)
        self.assertIn("must not declare GITHUB_TOKEN", findings[0])

    def test_unrelated_token_comment_does_not_declare_token_secret(self) -> None:
        workflow = self.fixture(
            ".github/workflows/reusable-safe.yml",
            'on: {"workflow_call": {"secrets": {"allowed": {}}}}\n'
            "# GITHUB_TOKEN:\n",
        )
        findings: list[str] = []
        with patch(
            "lib.audit_reusable_contract_checks.read_contracts",
            return_value={"existing_workflow_count": 0},
        ):
            check_reusable_workflows(self.root, [workflow], findings)
        self.assertEqual(findings, [])

    def test_workflow_call_event_scalar_and_sequence_are_detected(self) -> None:
        for value in ("on: workflow_call\n", "on: [push, workflow_call]\n"):
            workflow = self.fixture("callee.yml", value)
            self.assertEqual(workflow_call_definition(workflow), (True, set(), set()))
        workflow = self.fixture("callee.yml", "on: [push, pull_request]\n")
        self.assertEqual(workflow_call_definition(workflow), (False, set(), set()))

    def test_reusable_workflow_summary_counts_quoted_call(self) -> None:
        self.fixture(
            ".github/workflows/primary.yml",
            "on: workflow_dispatch\njobs:\n  scan:\n    steps:\n"
            "      - run: echo safe\n",
        )
        self.fixture(
            ".github/workflows/reusable-quoted.yml",
            'on: {"workflow_call": {}}\n',
        )
        with patch(
            "lib.audit_reusable_contract_checks.read_contracts",
            return_value={"existing_workflow_count": 1},
        ):
            findings, summary = run_contract_audit(self.root)
        self.assertEqual(summary["reusable_workflows"], 1)
        self.assertEqual(findings, [])

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

    def test_same_line_flow_alias_executable_mapping_rejected(self) -> None:
        path = self.fixture("workflow.yml", (
            "{x: &step {uses: actions/checkout@v5}, "
            "jobs: {scan: {steps: [*step]}}}\n"
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
