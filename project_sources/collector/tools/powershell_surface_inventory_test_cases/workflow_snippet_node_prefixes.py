from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowSnippetNodePrefixTests(InventoryTestCase):
    def test_yaml_node_prefix_scalar_shell_and_run_values_are_normalized(self) -> None:
        cases = [
            (
                "anchored-shell",
                ".github/workflows/anchored-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Anchored shell\n"
                "        shell: &ps pwsh\n"
                "        run: Write-Host ok\n",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "tagged-shell",
                ".github/workflows/tagged-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Tagged shell\n"
                "        shell: !dcoir pwsh\n"
                "        run: Write-Host ok\n",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "anchored-run",
                ".github/workflows/anchored-run.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Anchored run\n"
                "        shell: pwsh\n"
                "        run: &cmd Write-Host ok\n",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "tagged-run",
                ".github/workflows/tagged-run.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Tagged run\n"
                "        shell: pwsh\n"
                "        run: !dcoir Write-Host ok\n",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "anchored-default-shell",
                ".github/workflows/anchored-default-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: &ps pwsh\n"
                "    steps:\n"
                "      - name: Anchored default shell\n"
                "        run: Write-Host ok\n",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "tagged-default-shell",
                ".github/workflows/tagged-default-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: !dcoir pwsh\n"
                "    steps:\n"
                "      - name: Tagged default shell\n"
                "        run: Write-Host ok\n",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "flow-anchored-shell-tagged-run",
                ".github/workflows/flow-anchored-shell-tagged-run.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - { name: Flow prefixes, shell: &ps pwsh, run: !dcoir Write-Host ok }\n",
                "pwsh",
                "Write-Host ok",
            ),
        ]
        for name, rel, text, expected_shell, expected_command in cases:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    write(root / rel, text)
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                snippets = result["surfaces"][0]["embedded_snippets"]
                self.assertEqual(len(snippets), 1)
                self.assertEqual(snippets[0]["shell"], expected_shell)
                self.assertEqual(snippets[0]["command_preview"], expected_command)

    def test_yaml_node_prefix_first_step_key_is_normalized(self) -> None:
        cases = [
            (
                "anchored-first-shell",
                ".github/workflows/anchored-first-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - &step shell: pwsh\n"
                "        run: Write-Host ok\n",
                "(unnamed step)",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "tagged-first-shell",
                ".github/workflows/tagged-first-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - !dcoir shell: pwsh\n"
                "        run: Write-Host ok\n",
                "(unnamed step)",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "anchored-first-run",
                ".github/workflows/anchored-first-run.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - &step run: Write-Host ok\n"
                "        shell: pwsh\n",
                "(unnamed step)",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "tagged-first-run",
                ".github/workflows/tagged-first-run.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - !dcoir run: Write-Host ok\n"
                "        shell: pwsh\n",
                "(unnamed step)",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "anchored-first-name",
                ".github/workflows/anchored-first-name.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - &step name: Anchored first name\n"
                "        shell: pwsh\n"
                "        run: Write-Host ok\n",
                "Anchored first name",
                "pwsh",
                "Write-Host ok",
            ),
            (
                "tagged-first-name",
                ".github/workflows/tagged-first-name.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - !dcoir name: Tagged first name\n"
                "        shell: pwsh\n"
                "        run: Write-Host ok\n",
                "Tagged first name",
                "pwsh",
                "Write-Host ok",
            ),
        ]
        for name, rel, text, expected_name, expected_shell, expected_command in cases:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    write(root / rel, text)
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                snippets = result["surfaces"][0]["embedded_snippets"]
                self.assertEqual(len(snippets), 1)
                self.assertEqual(snippets[0]["step_or_action"], expected_name)
                self.assertEqual(snippets[0]["shell"], expected_shell)
                self.assertEqual(snippets[0]["command_preview"], expected_command)
