from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class BasicAndShapeFailureTests(InventoryTestCase):
    def test_control_inventory_succeeds(self) -> None:
        with self.make_minimal_repo() as temp:
            result = inventory.build_inventory(Path(temp))
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        categories = result["summary"]["by_category"]
        self.assertEqual(categories["collector_runtime_wrapper"], 1)
        self.assertEqual(categories["collector_runtime_source_part"], 1)
        self.assertEqual(categories["collector_harness_script"], 1)
        self.assertEqual(categories["collector_harness_source_part"], 1)
        self.assertEqual(categories["workflow_embedded_powershell"], 1)
        operator_surface = next(
            surface for surface in result["surfaces"] if surface["path"] == "operator_tools/sample/Invoke-DcoirSample.ps1"
        )
        self.assertEqual(operator_surface["marker_lines"], [])

    def test_unclassified_changed_file_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(root / "misc/unknown.ps1")
            result = inventory.build_inventory(root, changed_files=["misc/unknown.ps1"])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("no inventory category" in error for error in result["validation"]["errors"]))

    def test_changed_file_paths_accept_windows_separators(self) -> None:
        with self.make_minimal_repo() as temp:
            result = inventory.build_inventory(
                Path(temp),
                changed_files=["project_sources\\collector\\source\\DCOIR_Collector.ps1"],
            )

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"][0]["path"], "project_sources/collector/source/DCOIR_Collector.ps1")

    def test_missing_changed_file_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            result = inventory.build_inventory(Path(temp), changed_files=["project_sources/collector/source/missing.ps1"])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("missing from the working tree" in error for error in result["validation"]["errors"]))

    def test_missing_changed_workflow_yaml_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            for changed_path in [
                ".github/workflows/deleted.yml",
                ".github/actions/deleted/action.yml",
            ]:
                with self.subTest(changed_path=changed_path):
                    result = inventory.build_inventory(Path(temp), changed_files=[changed_path])
                self.assertFalse(result["validation"]["success"])
                self.assertTrue(any("workflow/action YAML path is missing" in error for error in result["validation"]["errors"]))

    def test_empty_changed_workflow_yaml_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/empty.yml"
            write(root / rel, "")
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("workflow/action YAML is empty" in error for error in result["validation"]["errors"]))

    def test_malformed_workflow_yaml_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "        run: [Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("unclosed '['" in error for error in result["validation"]["errors"]))

    def test_malformed_flow_mapping_value_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-flow-map.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "        run: { command: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("unclosed '{'" in error for error in result["validation"]["errors"]))

    def test_malformed_node_prefixed_flow_values_fail_closed(self) -> None:
        cases = [
            (
                "anchored-run-flow-list",
                ".github/workflows/anchored-run-flow-list.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "        run: &cmd [Write-Host ok\n",
                "unclosed '['",
            ),
            (
                "tagged-run-flow-map",
                ".github/workflows/tagged-run-flow-map.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "        run: !dcoir { command: Write-Host ok\n",
                "unclosed '{'",
            ),
            (
                "anchored-top-level-jobs-flow",
                ".github/workflows/anchored-top-level-jobs-flow.yml",
                "jobs: &j { test: { steps: [ { shell: pwsh, run: Write-Host ok }\n",
                "unclosed '['",
            ),
            (
                "tagged-job-level-flow",
                ".github/workflows/tagged-job-level-flow.yml",
                "jobs:\n"
                "  test: !dcoir { steps: [ { shell: pwsh, run: Write-Host ok }\n",
                "unclosed '['",
            ),
            (
                "tagged-composite-runs-flow",
                ".github/actions/tagged-composite/action.yml",
                "name: Tagged composite\n"
                "runs: !dcoir { using: composite, steps: [ { shell: pwsh, run: Write-Host ok }\n",
                "unclosed '['",
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

    def test_malformed_flow_mapping_fragment_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-flow-fragment.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - { name: Flow, shell: pwsh, run: Write-Host one, two }\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertFalse(result["validation"]["success"])
        self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
        self.assertTrue(any("unsupported flow mapping fragment" in error for error in result["validation"]["errors"]))

    def test_flow_mapping_parentheses_do_not_hide_comma_fragments(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-flow-parentheses.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - { name: Flow, shell: pwsh, run: Write-Host (one, two) }\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertFalse(result["validation"]["success"])
        self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
        self.assertTrue(any("unsupported flow mapping fragment" in error for error in result["validation"]["errors"]))

    def test_flow_mapping_colon_fragment_after_run_fails_closed(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-flow-colon-fragment.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - { name: Flow, shell: pwsh, run: Write-Host (one, two: three) }\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertFalse(result["validation"]["success"])
        self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
        self.assertTrue(any("unsupported flow step key 'two'" in error for error in result["validation"]["errors"]))

    def test_malformed_workflow_indentation_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-indent.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "       run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("unsupported odd indentation" in error for error in result["validation"]["errors"]))

    def test_workflow_marker_without_extractable_snippet_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-even-indent.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "      run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("non-list entry directly under steps" in error for error in result["validation"]["errors"]))

    def test_overindented_workflow_step_keys_fail_closed(self) -> None:
        cases = [
            (
                "overindented-run",
                ".github/workflows/overindented-run.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell: pwsh\n"
                "          run: Write-Host ok\n",
                "misindented workflow run value",
            ),
            (
                "overindented-shell",
                ".github/workflows/overindented-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Bad shell indent\n"
                "          shell: pwsh\n"
                "        run: Write-Host ok\n",
                "misindented workflow shell value",
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

    def test_malformed_step_list_item_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/malformed-step-item.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - shell pwsh\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("non-mapping step entry" in error for error in result["validation"]["errors"]))

    def test_changed_workflow_yaml_without_powershell_markers_can_pass(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/no-powershell.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Bash step\n"
                "        run: echo ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])


