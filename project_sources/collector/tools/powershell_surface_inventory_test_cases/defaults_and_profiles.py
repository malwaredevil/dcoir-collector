from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class DefaultsAndProfileTests(InventoryTestCase):
    def test_defaults_run_shell_is_inherited_without_fake_snippet(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/default-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: powershell\n"
                "    steps:\n"
                "      - name: Uses default shell\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/default-shell.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "powershell")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_job_defaults_after_steps_still_apply(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/default-after-steps.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses later default\n"
                "        run: Write-Host ok\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: pwsh\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/default-after-steps.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh")

    def test_top_level_defaults_after_jobs_still_apply(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/top-default-after-jobs.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses top default\n"
                "        run: Write-Host ok\n"
                "defaults:\n"
                "  run:\n"
                "    shell: pwsh\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/top-default-after-jobs.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh")

    def test_inline_top_level_default_shell_applies(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/inline-top-default.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses inline default\n"
                "        run: Write-Host ok\n"
                "defaults: { run: { shell: pwsh } }\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/inline-top-default.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh")

    def test_inline_job_default_shell_applies(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/inline-job-default.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses inline job default\n"
                "        run: Write-Host ok\n"
                "    defaults: { run: { shell: powershell } }\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/inline-job-default.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "powershell")

    def test_custom_default_shell_template_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/custom-default-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                '        shell: "powershell.exe -NoProfile -File {0}"\n'
                "    steps:\n"
                "      - name: Uses custom default shell\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/custom-default-shell.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "powershell.exe -NoProfile -File {0}")

    def test_unquoted_custom_default_shell_template_is_preserved(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/unquoted-custom-default.yml",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: pwsh -NoProfile -File {0}\n"
                "    steps:\n"
                "      - name: Uses unquoted custom default shell\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/unquoted-custom-default.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh -NoProfile -File {0}")

    def test_inline_custom_default_shell_template_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/inline-custom-default.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses inline custom default\n"
                "        run: Write-Host ok\n"
                'defaults: { run: { shell: "pwsh -NoProfile -File {0}" } }\n',
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/inline-custom-default.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh -NoProfile -File {0}")

    def test_nested_shell_key_does_not_override_step_default_shell(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/nested-shell.yml",
                "jobs:\n"
                "  test:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: pwsh\n"
                "    steps:\n"
                "      - name: Has nested env shell\n"
                "        run: Write-Host ok\n"
                "        env:\n"
                "          shell: bash\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/nested-shell.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["shell"], "pwsh")

    def test_nested_defaults_do_not_create_workflow_surface(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/nested-defaults.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Plain run with metadata defaults\n"
                "        run: echo not-powershell\n"
                "        metadata:\n"
                "          defaults:\n"
                "            run:\n"
                "              shell: pwsh\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/nested-defaults.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_job_default_shell_does_not_leak_to_sibling_job(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/two-jobs.yml",
                "jobs:\n"
                "  first:\n"
                "    defaults:\n"
                "      run:\n"
                "        shell: pwsh\n"
                "    steps:\n"
                "      - name: First PowerShell job\n"
                "        run: Write-Host ok\n"
                "  second:\n"
                "    steps:\n"
                "      - name: Plain shell job\n"
                "        run: echo not-powershell\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/two-jobs.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], "First PowerShell job")

    def test_hyphenated_powershell_words_do_not_create_workflow_surface(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/workflows/hyphenated-mentions.yml",
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Prefix hyphen\n"
                "        run: echo not-powershell\n"
                "      - name: Suffix hyphen\n"
                "        run: echo powershell-validation\n",
            )
            result = inventory.build_inventory(root, changed_files=[".github/workflows/hyphenated-mentions.yml"])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])
