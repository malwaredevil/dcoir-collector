from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowShapeCollectionTests(InventoryTestCase):
    def test_workflow_collection_run_and_shell_values_fail_closed(self) -> None:
        cases = [
            ("direct-run-list", "      - shell: pwsh\n        run: [Write-Host ok]\n", "run"),
            ("direct-run-map", "      - shell: pwsh\n        run: { command: Write-Host ok }\n", "run"),
            ("direct-run-alias", "      - shell: pwsh\n        run: *cmd\n", "run"),
            ("direct-run-block-list", "      - shell: pwsh\n        run:\n          - Write-Host ok\n", "run"),
            ("direct-run-block-map", "      - shell: pwsh\n        run:\n          command: Write-Host ok\n", "run"),
            ("direct-shell-list", "      - shell: [pwsh]\n        run: Write-Host ok\n", "shell"),
            ("direct-shell-expression", "      - shell: ${{ matrix.shell }}\n        run: Write-Host ok\n", "shell"),
            ("direct-shell-alias", "      - shell: *ps\n        run: Write-Host ok\n", "shell"),
            ("direct-shell-block-list", "      - shell:\n          - pwsh\n        run: Write-Host ok\n", "shell"),
            ("direct-shell-block-map", "      - shell:\n          executable: pwsh\n        run: Write-Host ok\n", "shell"),
            ("flow-step-run-list", "      - { name: Flow, shell: pwsh, run: [Write-Host ok] }\n", "run"),
            ("flow-step-run-map", "      - { name: Flow, shell: pwsh, run: { command: Write-Host ok } }\n", "run"),
            ("flow-step-run-alias", "      - { name: Flow, shell: pwsh, run: *cmd }\n", "run"),
            ("flow-step-shell-list", "      - { name: Flow, shell: [pwsh], run: Write-Host ok }\n", "shell"),
            ("flow-step-shell-expression", "      - { name: Flow, shell: ${{ matrix.shell }}, run: Write-Host ok }\n", "shell"),
            ("flow-step-shell-alias", "      - { name: Flow, shell: *ps, run: Write-Host ok }\n", "shell"),
            ("commented-flow-step-run-list", "      - { name: Flow, shell: pwsh, run: [Write-Host ok] } # comment\n", "run"),
            ("commented-flow-step-shell-list", "      - { name: Flow, shell: [pwsh], run: Write-Host ok } # comment\n", "shell"),
            (
                "block-default-shell-alias",
                "    defaults:\n"
                "      run:\n"
                "        shell: *ps\n"
                "    steps:\n"
                "      - name: Uses invalid default shell alias\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "block-default-shell-list",
                "    defaults:\n"
                "      run:\n"
                "        shell: [pwsh]\n"
                "    steps:\n"
                "      - name: Uses invalid default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "block-default-shell-expression",
                "    defaults:\n"
                "      run:\n"
                "        shell: ${{ matrix.shell }}\n"
                "    steps:\n"
                "      - name: Uses invalid default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "block-default-shell-block-list",
                "    defaults:\n"
                "      run:\n"
                "        shell:\n"
                "          - pwsh\n"
                "    steps:\n"
                "      - name: Uses invalid default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "block-default-shell-block-map",
                "    defaults:\n"
                "      run:\n"
                "        shell:\n"
                "          executable: pwsh\n"
                "    steps:\n"
                "      - name: Uses invalid default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "inline-default-shell-alias",
                "    steps:\n"
                "      - name: Uses invalid inline default shell alias\n"
                "        run: Write-Host ok\n"
                "defaults: { run: { shell: *ps } }\n",
                "defaults.run.shell",
            ),
            (
                "inline-default-shell-list",
                "    steps:\n"
                "      - name: Uses invalid inline default shell\n"
                "        run: Write-Host ok\n"
                "defaults: { run: { shell: [pwsh] } }\n",
                "defaults.run.shell",
            ),
            (
                "inline-default-shell-multi-list",
                "    steps:\n"
                "      - name: Uses invalid multi-item inline default shell\n"
                "        run: Write-Host ok\n"
                "defaults: { run: { shell: [pwsh, -NoProfile] } }\n",
                "defaults.run.shell",
            ),
            (
                "job-inline-default-shell-expression",
                "    defaults: { run: { shell: ${{ matrix.shell }} } }\n"
                "    steps:\n"
                "      - name: Uses invalid job inline default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "nested-inline-default-shell-list",
                "    defaults:\n"
                "      run: { shell: [pwsh] }\n"
                "    steps:\n"
                "      - name: Uses invalid nested inline default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
        ]
        for name, body, key in cases:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/{name}.yml"
                    steps_header = "" if "    steps:" in body else "    steps:\n"
                    write(root / rel, "jobs:\n  test:\n" + steps_header + body)
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertFalse(result["validation"]["success"])
                self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
                self.assertTrue(
                    any(f"non-scalar workflow {key} value" in error for error in result["validation"]["errors"])
                )

    def test_workflow_default_shell_expression_fails_closed(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/top-default-shell-expression.yml"
            write(
                root / rel,
                "defaults:\n"
                "  run:\n"
                "    shell: ${{ matrix.shell }}\n"
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses workflow default shell\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertFalse(result["validation"]["success"])
        self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
        self.assertTrue(
            any("non-scalar workflow defaults.run.shell value" in error for error in result["validation"]["errors"])
        )
