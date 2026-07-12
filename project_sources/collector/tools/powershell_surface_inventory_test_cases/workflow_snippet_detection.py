from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowSnippetDetectionTests(InventoryTestCase):
    def test_workflow_run_before_shell_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/run-before-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Run before shell\n"
                "        run: Write-Host ok\n"
                "        shell: pwsh\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/run-before-shell.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["summary"]["by_category"]["workflow_embedded_powershell"], 1)
        snippet = result["surfaces"][0]["embedded_snippets"][0]
        self.assertEqual(snippet["shell"], "pwsh")
        self.assertEqual(snippet["line_start"], 5)
        self.assertEqual(snippet["line_end"], 6)

    def test_compact_block_scalar_run_before_shell_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/compact-block-run-before-shell.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - run: |\n"
                "          Write-Host ok\n"
                "        shell: pwsh\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")
        self.assertEqual(snippets[0]["line_start"], 4)
        self.assertEqual(snippets[0]["line_end"], 6)

    def test_quoted_custom_shell_template_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/custom-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Custom shell template\n"
                '        shell: "pwsh -NoProfile -File {0}"\n'
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/custom-shell.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh -NoProfile -File {0}")

    def test_custom_shell_template_preserves_inner_quotes(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/custom-shell-inner-quotes.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Custom shell template with inner quotes\n"
                "        shell: \"pwsh -NoProfile -Command '& {0}'\"\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(
                root,
                changed_files=[".github/workflows/custom-shell-inner-quotes.yml"],
            )
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh -NoProfile -Command '& {0}'")

    def test_unquoted_custom_shell_template_is_preserved(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/unquoted-custom-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Unquoted custom shell\n"
                "        shell: pwsh -NoProfile -File {0}\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/unquoted-custom-shell.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh -NoProfile -File {0}")

    def test_unquoted_windows_powershell_shell_path_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/windows-powershell-path.yml"
            shell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -File {0}"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Windows PowerShell path\n"
                f"        shell: {shell}\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], shell)
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_flow_style_step_with_powershell_shell_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/flow-step.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - { name: Flow style, shell: pwsh, run: Write-Host ok }\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/flow-step.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], "Flow style")
        self.assertEqual(snippets[0]["shell"], "pwsh")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_anchored_flow_style_step_with_powershell_shell_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/anchored-flow-step.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - &ps { name: Anchored Flow, shell: pwsh, run: Write-Host ok }\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], "Anchored Flow")
        self.assertEqual(snippets[0]["shell"], "pwsh")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_tagged_flow_style_step_with_powershell_shell_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/tagged-flow-step.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - !dcoir { name: Tagged Flow, shell: pwsh, run: Write-Host ok }\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], "Tagged Flow")
        self.assertEqual(snippets[0]["shell"], "pwsh")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")
