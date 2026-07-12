from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowShapeEmptyValueTests(InventoryTestCase):
    def test_empty_workflow_run_and_shell_values_fail_closed(self) -> None:
        cases = [
            ("direct-run-empty", "      - shell: pwsh\n        run:\n", "run"),
            ("direct-run-quoted-empty", '      - shell: pwsh\n        run: ""\n', "run"),
            ("direct-shell-empty", "      - shell:\n        run: Write-Host ok\n", "shell"),
            ("direct-shell-quoted-empty", '      - shell: ""\n        run: Write-Host ok\n', "shell"),
            ("flow-run-empty", "      - { name: Flow, shell: pwsh, run: }\n", "run"),
            ("flow-run-quoted-empty", '      - { name: Flow, shell: pwsh, run: "" }\n', "run"),
            ("flow-shell-empty", "      - { name: Flow, shell: , run: Write-Host ok }\n", "shell"),
            ("flow-shell-quoted-empty", '      - { name: Flow, shell: "", run: Write-Host ok }\n', "shell"),
            (
                "default-shell-empty",
                "    defaults:\n"
                "      run:\n"
                "        shell:\n"
                "    steps:\n"
                "      - name: Uses invalid empty default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "default-shell-quoted-empty",
                "    defaults:\n"
                "      run:\n"
                '        shell: ""\n'
                "    steps:\n"
                "      - name: Uses invalid quoted-empty default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "inline-default-shell-empty",
                "    steps:\n"
                "      - name: Uses invalid inline default shell\n"
                "        run: Write-Host ok\n"
                "defaults: { run: { shell: } }\n",
                "defaults.run.shell",
            ),
            (
                "inline-default-shell-quoted-empty",
                "    steps:\n"
                "      - name: Uses invalid quoted-empty inline default shell\n"
                "        run: Write-Host ok\n"
                'defaults: { run: { shell: "" } }\n',
                "defaults.run.shell",
            ),
            (
                "job-inline-default-shell-empty",
                "    defaults: { run: { shell: } }\n"
                "    steps:\n"
                "      - name: Uses invalid job inline default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "nested-inline-default-shell-empty",
                "    defaults:\n"
                "      run: { shell: }\n"
                "    steps:\n"
                "      - name: Uses invalid nested inline default shell\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
            (
                "nested-inline-default-shell-quoted-empty",
                "    defaults:\n"
                '      run: { shell: "" }\n'
                "    steps:\n"
                "      - name: Uses invalid nested quoted-empty default shell\n"
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

    def test_empty_block_scalar_run_fails_closed(self) -> None:
        for marker in ["|", ">"]:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/empty-block-run-{marker.replace('|', 'pipe').replace('>', 'fold')}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Empty block scalar run\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertFalse(result["validation"]["success"])
                self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
                self.assertTrue(any("empty workflow run value" in error for error in result["validation"]["errors"]))

    def test_block_scalar_shell_values_fail_closed(self) -> None:
        cases = [
            (
                "direct-shell-block-scalar",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Direct shell block scalar\n"
                "        shell: |\n"
                "          pwsh\n"
                "        run: Write-Host ok\n",
                "shell",
            ),
            (
                "default-shell-block-scalar",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: |\n"
                "          pwsh\n"
                "    steps:\n"
                "      - name: Default shell block scalar\n"
                "        run: Write-Host ok\n",
                "defaults.run.shell",
            ),
        ]
        for name, text, key in cases:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/{name}.yml"
                    write(root / rel, text)
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertFalse(result["validation"]["success"])
                self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")
                self.assertTrue(
                    any(
                        f"unsupported block-scalar workflow {key} value" in error
                        for error in result["validation"]["errors"]
                    )
                )
