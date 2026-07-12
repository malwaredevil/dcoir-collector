from __future__ import annotations

import io
import json
import sys
import unittest
import unittest.mock

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class InventoryCliManifestTests(InventoryTestCase):
    def test_empty_included_powershell_surface_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = "operator_tools/sample/empty.psm1"
            write(root / rel, "")
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("included PowerShell surface is empty" in error for error in result["validation"]["errors"]))

    def test_file_facts_are_line_ending_stable(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = "operator_tools/sample/CrLf.ps1"
            crlf_bytes = b"Write-Output 'ok'\r\n"
            lf_bytes = b"Write-Output 'ok'\n"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(crlf_bytes)

            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["file_facts_policy"], "text_bytes_with_line_endings_normalized_to_lf")
        self.assertEqual(result["surfaces"][0]["size_bytes"], len(lf_bytes))
        self.assertEqual(result["surfaces"][0]["line_count"], 1)
        self.assertEqual(result["surfaces"][0]["sha256"], inventory.hashlib.sha256(lf_bytes).hexdigest())

    def test_git_discovery_filters_ignored_segments(self) -> None:
        class Completed:
            returncode = 0
            stdout = (
                b"operator_tools/sample/Invoke-DcoirSample.ps1\0"
                b"operator_tools/sample/node_modules/vendor.ps1\0"
                b"project_sources/collector/source/DCOIR_Collector.ps1\0"
            )

        with unittest.mock.patch.object(inventory.subprocess, "run", return_value=Completed()):
            files = inventory.git_tracked_files(Path("/repo"))

        self.assertEqual(
            files,
            [
                "operator_tools/sample/Invoke-DcoirSample.ps1",
                "project_sources/collector/source/DCOIR_Collector.ps1",
            ],
        )

    def test_powershell_analyzer_policy_is_validation_tooling(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/PSScriptAnalyzerSettings.psd1"
            write(root / rel, "@{ Severity = @('Error', 'Warning') }\n")
            result = inventory.build_inventory(root, changed_files=[rel])

        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(len(result["surfaces"]), 1)
        self.assertEqual(result["surfaces"][0]["category"], "collector_validation_tooling")
        self.assertEqual(result["surfaces"][0]["inclusion_decision"], "include")
        self.assertEqual(result["surfaces"][0]["source_type"], ".psd1")

    def test_empty_generated_output_fails_when_present(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = inventory.HARNESS_GENERATED_OUTPUT.as_posix()
            write(root / rel, "")
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("included PowerShell surface is empty" in error for error in result["validation"]["errors"]))

    def test_baseline_shrink_fails_without_exception(self) -> None:
        with self.make_minimal_repo() as temp:
            baseline = {
                "summary": {
                    "by_category": {
                        "collector_runtime_source_part": 2,
                    }
                }
            }
            result = inventory.build_inventory(Path(temp), baseline=baseline)
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("unexpectedly shrank" in error for error in result["validation"]["errors"]))

    def test_baseline_and_shrink_exception_paths_must_stay_inside_repo_before_read(self) -> None:
        scenarios = [
            ("--baseline-json", "ABSOLUTE_BASELINE", "PowerShell surface inventory baseline path"),
            ("--shrink-exception-json", "../outside-shrink-exception.json", "PowerShell surface inventory shrink exception path"),
        ]
        for arg_name, unsafe_value, expected_label in scenarios:
            with self.subTest(arg_name=arg_name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp).resolve()
                    outside_name = "outside-shrink-evidence.json"
                    if unsafe_value.startswith("../"):
                        outside_name = unsafe_value.removeprefix("../")
                    outside = root.parent / outside_name
                    write(outside, "{not-json")
                    if unsafe_value == "ABSOLUTE_BASELINE":
                        unsafe_value = outside.as_posix()
                    argv = [
                        "build_powershell_surface_inventory.py",
                        "--repo-root",
                        str(root),
                        "--no-write",
                        arg_name,
                        unsafe_value,
                    ]
                    with unittest.mock.patch.object(sys, "argv", argv), unittest.mock.patch(
                        "sys.stderr",
                        new_callable=io.StringIO,
                    ) as stderr:
                        rc = inventory.main()

                self.assertEqual(rc, 1)
                self.assertIn(f"{expected_label} must be a repo-relative path without traversal", stderr.getvalue())
                self.assertNotIn("Invalid JSON", stderr.getvalue())

    def test_changed_files_from_path_must_stay_inside_repo_before_read(self) -> None:
        scenarios = [
            ("absolute", "ABSOLUTE_CHANGED_FILES"),
            ("traversal", "../outside-changed-files.txt"),
        ]
        for name, unsafe_value in scenarios:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp).resolve()
                    outside_name = "outside-changed-files.txt"
                    if unsafe_value.startswith("../"):
                        outside_name = unsafe_value.removeprefix("../")
                    outside = root.parent / outside_name
                    write(outside, "\n")
                    if unsafe_value == "ABSOLUTE_CHANGED_FILES":
                        unsafe_value = outside.as_posix()
                    argv = [
                        "build_powershell_surface_inventory.py",
                        "--repo-root",
                        str(root),
                        "--no-write",
                        "--changed-files-from",
                        unsafe_value,
                    ]
                    with unittest.mock.patch.object(sys, "argv", argv), unittest.mock.patch(
                        "sys.stderr",
                        new_callable=io.StringIO,
                    ) as stderr:
                        rc = inventory.main()

                self.assertEqual(rc, 1)
                self.assertIn(
                    "PowerShell surface inventory changed-files input path must be a repo-relative path without traversal",
                    stderr.getvalue(),
                )
                self.assertNotIn("Changed-file input must not be blank", stderr.getvalue())

    def test_missing_changed_files_from_fails_closed(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp).resolve()
            argv = [
                "build_powershell_surface_inventory.py",
                "--repo-root",
                str(root),
                "--no-write",
                "--changed-files-from",
                "missing-changed-files.txt",
            ]
            with unittest.mock.patch.object(sys, "argv", argv), unittest.mock.patch(
                "sys.stderr",
                new_callable=io.StringIO,
            ) as stderr:
                rc = inventory.main()

        self.assertEqual(rc, 1)
        self.assertIn("Changed-files input is missing", stderr.getvalue())

    def test_report_output_paths_must_stay_inside_repo(self) -> None:
        scenarios = [
            (
                "json traversal",
                Path("../outside-inventory-report.json"),
                Path("inventory-report.md"),
                "PowerShell surface inventory JSON report output path",
                "outside-inventory-report.json",
            ),
            (
                "markdown absolute",
                Path("inventory-report.json"),
                "ABSOLUTE_MARKDOWN",
                "PowerShell surface inventory Markdown report output path",
                "outside-inventory-report.md",
            ),
        ]
        for name, json_output, markdown_output, expected_label, outside_name in scenarios:
            with self.subTest(name=name):
                with self.make_minimal_repo() as temp:
                    root = Path(temp).resolve()
                    outside = root.parent / outside_name
                    outside.unlink(missing_ok=True)
                    if markdown_output == "ABSOLUTE_MARKDOWN":
                        markdown_output = outside
                    result = inventory.build_inventory(root)
                    errors = inventory.write_outputs(root, result, Path(json_output), Path(markdown_output))

                self.assertTrue(
                    any(f"{expected_label} must be a repo-relative path without traversal" in error for error in errors),
                    errors,
                )
                self.assertFalse(outside.exists())

    def test_cli_rewrites_json_as_failed_when_markdown_write_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp).resolve()
            (root / "markdown-output-as-directory").mkdir()
            argv = [
                "build_powershell_surface_inventory.py",
                "--repo-root",
                str(root),
                "--json-output",
                "report.json",
                "--markdown-output",
                "markdown-output-as-directory",
            ]
            with unittest.mock.patch.object(sys, "argv", argv), unittest.mock.patch(
                "sys.stderr",
                new_callable=io.StringIO,
            ):
                rc = inventory.main()
            written = json.loads((root / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(rc, 1)
        self.assertFalse(written["validation"]["success"])
        self.assertTrue(
            any("PowerShell surface inventory report write failure" in error for error in written["validation"]["errors"])
        )

    def test_report_output_paths_must_not_alias(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp).resolve()
            result = inventory.build_inventory(root)
            errors = inventory.write_outputs(root, result, Path("same-report"), Path("same-report"))

        self.assertTrue(
            any("PowerShell surface inventory JSON and Markdown report output paths must be different" in error for error in errors),
            errors,
        )

    def test_changed_manifest_invalid_json_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            (root / "project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json").write_text(
                "{not-json",
                encoding="utf-8",
            )
            result = inventory.build_inventory(
                root,
                changed_files=["project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json"],
            )
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("Invalid JSON" in error for error in result["validation"]["errors"]))

    def test_changed_manifest_missing_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            (root / "project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json").unlink()
            result = inventory.build_inventory(
                root,
                changed_files=["project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json"],
            )
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("manifest is missing" in error for error in result["validation"]["errors"]))

    def test_changed_collector_file_requires_valid_manifest(self) -> None:
        manifest_rel = "project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json"
        collector_rel = "project_sources/collector/source/DCOIR_Collector.ps1"
        for manifest_content, expected_error in [
            (None, "manifest is missing"),
            ("{not-json", "Invalid JSON"),
            ("{}\n", "did not provide any expected PowerShell source paths"),
        ]:
            with self.subTest(expected_error=expected_error):
                with self.make_minimal_repo() as temp:
                    root = Path(temp)
                    manifest_path = root / manifest_rel
                    if manifest_content is None:
                        manifest_path.unlink()
                    else:
                        manifest_path.write_text(manifest_content, encoding="utf-8")
                    result = inventory.build_inventory(root, changed_files=[collector_rel])
                self.assertFalse(result["validation"]["success"])
                self.assertTrue(any(expected_error in error for error in result["validation"]["errors"]))

    def test_changed_collector_file_passes_with_valid_manifest(self) -> None:
        with self.make_minimal_repo() as temp:
            result = inventory.build_inventory(
                Path(temp),
                changed_files=["project_sources/collector/source/DCOIR_Collector.ps1"],
            )
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["summary"]["by_category"]["collector_runtime_wrapper"], 1)
