from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class WorkflowSnippetBlockMarkerTests(InventoryTestCase):
    def test_block_scalar_digit_markers_preserve_body(self) -> None:
        for marker in ["|2", "|2-", "|+2", ">2", ">2-", ">+2"]:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/block-{marker.replace('|', 'pipe').replace('>', 'fold')}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Uses block digit marker\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n"
                        "          Write-Host ok\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                snippets = result["surfaces"][0]["embedded_snippets"]
                self.assertEqual(len(snippets), 1)
                self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")

    def test_block_scalar_auto_indent_markers_preserve_body(self) -> None:
        for marker in ["|", ">"]:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/block-auto-indent-{marker.replace('|', 'pipe').replace('>', 'fold')}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Uses auto block indentation marker\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n"
                        "         Write-Host ok\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                snippets = result["surfaces"][0]["embedded_snippets"]
                self.assertEqual(len(snippets), 1)
                self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")
                self.assertEqual(
                    snippets[0]["command_sha256"],
                    inventory.hashlib.sha256(b"Write-Host ok").hexdigest(),
                )

    def test_block_scalar_explicit_indent_markers_preserve_body(self) -> None:
        for marker, content_indent in [("|1", 9), ("|3", 11), ("|4", 12), ("|9", 17)]:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/block-explicit-indent-{marker.replace('|', 'pipe')}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Uses explicit block indentation marker\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n"
                        f"{' ' * content_indent}Write-Host ok\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                snippets = result["surfaces"][0]["embedded_snippets"]
                self.assertEqual(len(snippets), 1)
                self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")
                self.assertEqual(
                    snippets[0]["command_sha256"],
                    inventory.hashlib.sha256(b"Write-Host ok").hexdigest(),
                )

    def test_block_scalar_explicit_indent_rejects_too_shallow_body(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = ".github/workflows/block-explicit-indent-too-shallow.yml"
            write(
                root / rel,
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - name: Uses too-shallow explicit block indentation\n"
                "        shell: pwsh\n"
                "        run: |4\n"
                "          Write-Host ok\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertFalse(result["validation"]["success"])
        self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")

    def test_invalid_block_scalar_markers_fail_closed(self) -> None:
        for marker in ["|++", "|--", "|22", "|0", "|2+3", ">+2-", "'|'", '"|"']:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    marker_slug = marker.replace("|", "pipe").replace(">", "fold").replace("'", "quote").replace('"', "dquote")
                    rel = f".github/workflows/invalid-block-{marker_slug}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Invalid block marker\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n"
                        "          Write-Host ok\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertFalse(result["validation"]["success"])
                self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")

    def test_bare_invalid_block_scalar_markers_fail_closed(self) -> None:
        for marker in ["|++", "|--", "|22", "|0", "|2+3", ">+2-", "'|'", '"|"']:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    marker_slug = marker.replace("|", "pipe").replace(">", "fold").replace("'", "quote").replace('"', "dquote")
                    rel = f".github/workflows/bare-invalid-block-{marker_slug}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Bare invalid block marker\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertFalse(result["validation"]["success"])
                self.assertEqual(result["surfaces"][0]["category"], "invalid_workflow_surface")

    def test_block_scalar_marker_with_comment_preserves_body(self) -> None:
        for marker in ["| # keep literal", "|- # strip trailing newline"]:
            with self.subTest(marker=marker):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    rel = f".github/workflows/block-comment-{marker.split()[0].replace('|', 'pipe')}.yml"
                    write(
                        root / rel,
                        "jobs:\n"
                        "  test:\n"
                        "    steps:\n"
                        "      - name: Uses block marker comment\n"
                        "        shell: pwsh\n"
                        f"        run: {marker}\n"
                        "          Write-Host ok\n",
                    )
                    result = inventory.build_inventory(root, changed_files=[rel])

                self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
                snippets = result["surfaces"][0]["embedded_snippets"]
                self.assertEqual(len(snippets), 1)
                self.assertEqual(snippets[0]["command_preview"], "Write-Host ok")
