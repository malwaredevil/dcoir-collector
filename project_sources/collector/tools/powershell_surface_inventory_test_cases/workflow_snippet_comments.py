from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowSnippetCommentTests(InventoryTestCase):
    def test_flow_style_step_with_trailing_comment_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/flow-step-comment.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - { name: Flow style, shell: pwsh, run: Write-Host ok } # normal comment\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], "Flow style")
        self.assertEqual(snippets[0]["shell"], "pwsh")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_steps_key_with_trailing_comment_is_detected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/commented-steps.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps: # test steps\n"
                "      - name: Commented step # display-only comment\n"
                "        shell: pwsh # explicit shell\n"
                "        run: Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["step_or_action"], "Commented step")
        self.assertEqual(snippets[0]["shell"], "pwsh")
        self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_scalar_run_comments_are_not_command_markers(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/run-comment-marker.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Bash step\n"
                "        run: echo ok # powershell note\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_block_scalar_comments_are_not_command_markers(self) -> None:
        for body in [
            "          echo ok\n          # powershell note\n",
            "          echo ok # powershell note\n",
        ]:
            with self.subTest(body=body):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = ".github/workflows/block-comment-marker.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Bash block step\n"
                        "        run: |\n"
                        f"{body}",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                self.assertEqual(result["surfaces"], [])

    def test_plain_scalar_apostrophe_before_comment_is_not_a_quote(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/run-apostrophe-comment-marker.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Bash step\n"
                "        run: echo Collector's log # powershell note\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["surfaces"], [])

    def test_single_quoted_run_with_escaped_apostrophe_and_hash_is_preserved(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/single-quoted-run.yml"
            expected = "Write-Host Bob's # literal hash"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Single quoted command\n"
                "        shell: pwsh\n"
                "        run: 'Write-Host Bob''s # literal hash' # trailing YAML comment\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        snippets = result["surfaces"][0]["embedded_snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["command_preview"], expected)
        self.assertEqual(snippets[0]["command_sha256"], inventory.hashlib.sha256(expected.encode("utf-8")).hexdigest())
