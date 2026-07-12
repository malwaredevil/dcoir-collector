from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowShapeFlowValueTests(InventoryTestCase):
    def test_matrix_run_and_shell_data_are_not_validated_as_steps(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/matrix-run-shell-data.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    strategy:\n"
                "      matrix:\n"
                "        include:\n"
                "          - run: [unit, integration]\n"
                "            shell: [pwsh, bash]\n"
                "    steps:\n"
                "      - name: Bash step\n"
                "        run: echo ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_matrix_nested_steps_data_are_not_validated_as_executable_steps(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/matrix-nested-steps-data.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    strategy:\n"
                "      matrix:\n"
                "        include:\n"
                "          - name: data-only\n"
                "            steps:\n"
                "              - shell: pwsh\n"
                "                run: Write-Host fake\n"
                "    steps:\n"
                "      - name: Bash step\n"
                "        run: echo ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_flow_style_inline_steps_fail_closed(self) -> None:
        cases = [
            (
                "workflow-steps-value",
                ".github/workflows/inline-flow-steps.yml",
                "jobs:\n"
                "  test:\n"
                "    steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }]\n",
                "unsupported inline workflow steps value",
            ),
            (
                "workflow-job-value",
                ".github/workflows/inline-flow-job.yml",
                "jobs:\n"
                "  test: { steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] }\n",
                "unsupported inline workflow jobs.steps value",
            ),
            (
                "workflow-anchored-job-value",
                ".github/workflows/inline-flow-anchored-job.yml",
                "jobs:\n"
                "  test: &j { steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] }\n",
                "unsupported inline workflow jobs.steps value",
            ),
            (
                "workflow-tagged-job-value",
                ".github/workflows/inline-flow-tagged-job.yml",
                "jobs:\n"
                "  test: !dcoir { steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] }\n",
                "unsupported inline workflow jobs.steps value",
            ),
            (
                "workflow-jobs-value",
                ".github/workflows/inline-flow-jobs.yml",
                "jobs: { test: { steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] } }\n",
                "unsupported inline workflow jobs.steps value",
            ),
            (
                "workflow-anchored-jobs-value",
                ".github/workflows/inline-flow-anchored-jobs.yml",
                "jobs: &j { test: { steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] } }\n",
                "unsupported inline workflow jobs.steps value",
            ),
            (
                "workflow-tagged-jobs-value",
                ".github/workflows/inline-flow-tagged-jobs.yml",
                "jobs: !dcoir { test: { steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] } }\n",
                "unsupported inline workflow jobs.steps value",
            ),
            (
                "composite-runs-value",
                ".github/actions/inline-flow/action.yml",
                "name: Inline composite\n"
                "runs: { using: composite, steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] }\n",
                "unsupported inline workflow runs.steps value",
            ),
            (
                "composite-anchored-runs-value",
                ".github/actions/inline-flow-anchored/action.yml",
                "name: Inline composite\n"
                "runs: &r { using: composite, steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] }\n",
                "unsupported inline workflow runs.steps value",
            ),
            (
                "composite-tagged-runs-value",
                ".github/actions/inline-flow-tagged/action.yml",
                "name: Inline composite\n"
                "runs: !dcoir { using: composite, steps: [{ name: Inline, shell: pwsh, run: Write-Host ok }] }\n",
                "unsupported inline workflow runs.steps value",
            ),
            (
                "workflow-step-sequence-item",
                ".github/workflows/inline-flow-step-sequence-item.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - [shell: pwsh, run: Write-Host ok]\n",
                "unsupported inline workflow step value",
            ),
            (
                "workflow-step-overindented-sequence-item",
                ".github/workflows/inline-flow-overindented-step-sequence-item.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "        - [shell: pwsh, run: Write-Host ok]\n",
                "unsupported inline workflow step value",
            ),
            (
                "workflow-step-anchored-sequence-item",
                ".github/workflows/inline-flow-anchored-step-sequence-item.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - &ps [shell: pwsh, run: Write-Host ok]\n",
                "unsupported inline workflow step value",
            ),
            (
                "workflow-step-tagged-sequence-item",
                ".github/workflows/inline-flow-tagged-step-sequence-item.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - !dcoir [shell: pwsh, run: Write-Host ok]\n",
                "unsupported inline workflow step value",
            ),
            (
                "workflow-step-alias-item",
                ".github/workflows/inline-flow-alias-step-item.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - *ps\n",
                "unsupported alias workflow step value",
            ),
            (
                "workflow-step-overindented-non-list-item",
                ".github/workflows/overindented-non-list-step-item.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "        run: Write-Host ok\n",
                "non-list entry directly under steps",
            ),
        ]
        for name, rel, text, expected_error in cases:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    write(root / rel, text)
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertFalse(result["validation"]["success"])
                self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
                self.assertTrue(any(expected_error in error for error in result["validation"]["errors"]))

    def test_flow_style_step_plain_scalar_apostrophe_is_not_a_quote(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/flow-apostrophe.yml"
            expected_name = "Collector's Flow"
            expected_command = "echo Collector's log"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                f"      - {{ name: {expected_name}, shell: pwsh, run: {expected_command} }}\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], expected_name)
        self.assertEqual(snippets[0]["command_preview"], expected_command)

    def test_plain_scalar_apostrophe_does_not_fail_workflow_shape(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/apostrophe.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Collector's plain shell step\n"
                "        run: echo ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_plain_scalar_unmatched_parenthesis_does_not_fail_workflow_shape(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/parenthesis.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Validate (preview\n"
                "        run: echo ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_plain_scalar_brackets_and_braces_do_not_fail_workflow_shape(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/plain-brackets.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Validate [preview\n"
                "        run: echo {ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_comment_delimiters_do_not_fail_workflow_shape(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/comment-delimiters.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Validate # [not yaml structure\n"
                "        run: echo ok # } also not yaml structure\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])
