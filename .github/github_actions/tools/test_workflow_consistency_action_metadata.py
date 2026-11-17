#!/usr/bin/env python3
"""Regression tests: audit follows the action metadata GitHub Actions actually executes."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from check_workflow_consistency_drift import (
    add_string_findings,
    expanded_local_text,
    expanded_local_text_or_findings,
    local_uses_references,
)

REQUIRED_SURFACES_HELPER = ".github/github_actions/tools/check_required_surfaces.py"


class WorkflowConsistencyActionMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous_cwd = Path.cwd()
        self.addCleanup(os.chdir, self.previous_cwd)
        os.chdir(self.tmp.name)
        self.workflow = Path(".github/workflows/validate.yml")

    def write(self, relative_path: str, contents: str) -> None:
        path = Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def call(self, action: str) -> None:
        self.write(self.workflow.as_posix(), (
            "name: Validation\njobs:\n  scan:\n    steps:\n"
            f"      - uses: ./.github/actions/{action}\n"
        ))

    def test_action_yaml_only_expands_required_surface_helper(self) -> None:
        self.call("yaml-only")
        self.write(".github/actions/yaml-only/action.yaml", (
            "name: yaml-only\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            f"      run: python {REQUIRED_SURFACES_HELPER}\n"
        ))
        self.assertIn(REQUIRED_SURFACES_HELPER, expanded_local_text(self.workflow))

    def test_action_yml_only_remains_supported(self) -> None:
        self.call("yml-only")
        self.write(".github/actions/yml-only/action.yml", (
            "name: yml-only\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            "      run: echo yml-only-metadata\n"
        ))
        self.assertIn("yml-only-metadata", expanded_local_text(self.workflow))

    def test_action_yml_wins_when_both_names_exist(self) -> None:
        self.call("both")
        self.write(".github/actions/both/action.yml", (
            "name: selected-yml\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            "      run: echo selected-yml-metadata\n"
        ))
        self.write(".github/actions/both/action.yaml", (
            "name: shadowed-yaml\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            "      run: echo shadowed-yaml-metadata\n"
        ))
        expanded = expanded_local_text(self.workflow)
        self.assertIn("selected-yml-metadata", expanded)
        self.assertNotIn("shadowed-yaml-metadata", expanded)

    def test_mixed_case_and_unrecognized_metadata_are_not_loaded(self) -> None:
        self.call("wrong-case")
        self.write(".github/actions/wrong-case/ACTION.YAML", "must-not-expand")
        self.assertNotIn("must-not-expand", expanded_local_text(self.workflow))

    def test_missing_metadata_is_not_invented(self) -> None:
        self.call("missing")
        self.write(".github/actions/missing/notes.txt", "must-not-expand")
        self.assertNotIn("must-not-expand", expanded_local_text(self.workflow))

    def test_nested_yaml_actions_resolve_recursively(self) -> None:
        self.call("outer")
        self.write(".github/actions/outer/action.yaml", (
            "name: outer\nruns:\n  using: composite\n  steps:\n"
            "    - uses: ./.github/actions/outer/deeper\n"
        ))
        self.write(".github/actions/outer/deeper/action.yaml", (
            "name: deeper\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            f"      run: python {REQUIRED_SURFACES_HELPER}\n"
        ))
        self.assertIn(REQUIRED_SURFACES_HELPER, expanded_local_text(self.workflow))

    def test_run_block_uses_text_is_not_treated_as_an_action_step(self) -> None:
        self.call("script")
        self.write(".github/actions/script/action.yaml", (
            "name: script\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            "      run: |\n"
            "        - uses: ./.github/actions/marker\n"
        ))
        self.write(".github/actions/marker/action.yaml", (
            "name: marker\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            f"      run: python {REQUIRED_SURFACES_HELPER}\n"
        ))
        expanded = expanded_local_text(self.workflow)
        self.assertNotIn(".github/actions/marker/action.yaml", expanded)
        self.assertNotIn(REQUIRED_SURFACES_HELPER, expanded)

    def test_reference_after_run_block_is_not_skipped(self) -> None:
        text = (
            "jobs:\n  scan:\n    steps:\n"
            "      - run: |-\n"
            "          script contents\n"
            "        uses: ./.github/actions/following\n"
        )
        self.assertEqual(
            ["./.github/actions/following"],
            local_uses_references(text, self.workflow),
        )

    def test_indentless_workflow_and_composite_steps_are_discovered(self) -> None:
        workflow = (
            "jobs:\n  scan:\n    steps:\n"
            "    - uses: ./.github/actions/workflow-step\n"
        )
        action = (
            "runs:\n  using: composite\n  steps:\n"
            "  - uses: ./.github/actions/composite-step\n"
        )
        self.assertEqual(
            ["./.github/actions/workflow-step"],
            local_uses_references(workflow, self.workflow),
        )
        self.assertEqual(
            ["./.github/actions/composite-step"],
            local_uses_references(action, Path(".github/actions/test/action.yaml")),
        )

    def test_invalid_yaml_fails_closed_with_path_context(self) -> None:
        self.write(self.workflow.as_posix(), "jobs:\n  scan: [\n")
        findings: list[str] = []
        self.assertEqual(expanded_local_text_or_findings(self.workflow, findings), "")
        self.assertEqual(len(findings), 1)
        self.assertIn("validate.yml:1: invalid YAML:", findings[0])

    def test_local_reusable_workflow_calls_are_preserved(self) -> None:
        self.write(self.workflow.as_posix(), (
            "name: Validation\non: workflow_dispatch\njobs:\n"
            "  scan:\n    uses: ./.github/workflows/reusable-validation.yml\n"
        ))
        self.write(".github/workflows/reusable-validation.yml", (
            "name: Reusable validation\non: workflow_call\njobs:\n"
            "  scan:\n    steps:\n      - uses: ./.github/actions/verified\n"
        ))
        self.write(".github/actions/verified/action.yaml", (
            "name: verified\nruns:\n  using: composite\n  steps:\n"
            "    - shell: bash\n"
            f"      run: python {REQUIRED_SURFACES_HELPER}\n"
        ))
        self.assertIn(REQUIRED_SURFACES_HELPER, expanded_local_text(self.workflow))

    def test_cycles_do_not_expand_forever(self) -> None:
        self.call("cycle-a")
        self.write(".github/actions/cycle-a/action.yaml", (
            "name: cycle-a-marker\nruns:\n  using: composite\n"
            "  steps:\n    - uses: ./.github/actions/cycle-b\n"
        ))
        self.write(".github/actions/cycle-b/action.yaml", (
            "name: cycle-b-marker\nruns:\n  using: composite\n"
            "  steps:\n    - uses: ./.github/actions/cycle-a\n"
        ))
        expanded = expanded_local_text(self.workflow)
        self.assertEqual(expanded.count("cycle-a-marker"), 1)
        self.assertEqual(expanded.count("cycle-b-marker"), 1)

    def test_stale_authority_marker_detection_in_workflow_is_preserved(self) -> None:
        self.write(self.workflow.as_posix(), "name: Example\n# Airtable routing: stale\n")
        findings: list[str] = []
        add_string_findings(findings, self.workflow, "Airtable routing:")
        self.assertEqual(len(findings), 1)
        self.assertIn(":2:", findings[0])


if __name__ == "__main__":
    unittest.main()
