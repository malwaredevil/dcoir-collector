from __future__ import annotations

from .common import InventoryTestCase, Path, write
import build_powershell_surface_inventory as inventory


class ManifestAndProfileTests(InventoryTestCase):
    def test_superseded_part02_pointer_is_reference_not_runtime_source(self):
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/parts/DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1"
            write(root / rel, "# Superseded pointer only\n")
            surface = inventory.classify_surface(root, rel)

        self.assertEqual(surface["category"], "generated_or_assembled_output")
        self.assertEqual(surface["inclusion_decision"], "reference")

    def test_unmanifested_collector_part_fails_full_inventory(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(root / "project_sources/collector/source/parts/DCOIR_Collector.02_Unmanifested.ps1")
            result = inventory.build_inventory(root)
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("not listed" in error for error in result["validation"]["errors"]))

    def test_unmanifested_collector_part_fails_changed_mode(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/parts/DCOIR_Collector.02_Unmanifested.ps1"
            write(root / rel)
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("not listed" in error for error in result["validation"]["errors"]))

    def test_temp_named_collector_part_cannot_hide_from_manifest_enforcement(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/parts/temp/DCOIR_Collector.02_TempNamed.ps1"
            write(root / rel)
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertEqual(result["surfaces"][0]["category"], "collector_runtime_source_part")
        self.assertTrue(any("not listed" in error for error in result["validation"]["errors"]))

    def test_profile_required_harness_part_missing_fails_full_inventory(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/github_actions/workflow_required_surface_profiles.json",
                '{\n'
                '  "validate_on_pr": [\n'
                '    "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1",\n'
                '    "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-001.ps1"\n'
                "  ]\n"
                "}\n",
            )
            result = inventory.build_inventory(root)
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("required by" in error for error in result["validation"]["errors"]))

    def test_required_surface_profile_only_change_expands_harness_parts(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = inventory.REQUIRED_SURFACE_PROFILES_PATH.as_posix()
            write(
                root / rel,
                '{\n'
                '  "validate_on_pr": [\n'
                '    "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1"\n'
                "  ]\n"
                "}\n",
            )
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertTrue(result["validation"]["success"], result["validation"]["errors"])
        self.assertEqual(result["summary"]["by_category"]["collector_harness_source_part"], 1)
        self.assertIn("project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1", result["changed_file_dependency_expansion"]["expanded_paths"])

    def test_deleted_required_surface_profile_change_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = inventory.REQUIRED_SURFACE_PROFILES_PATH.as_posix()
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("Required surface profile is missing" in error for error in result["validation"]["errors"]))

    def test_malformed_required_surface_profile_fails(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = inventory.REQUIRED_SURFACE_PROFILES_PATH.as_posix()
            write(root / rel, "{not-json")
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("Invalid JSON in required surface profile" in error for error in result["validation"]["errors"]))

    def test_required_surface_profile_without_harness_parts_fails_when_changed(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            rel = inventory.REQUIRED_SURFACE_PROFILES_PATH.as_posix()
            write(root / rel, '{"validate_on_pr": ["README.md"]}\n')
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("did not provide any harness source parts" in error for error in result["validation"]["errors"]))

    def test_unprofiled_harness_part_fails_when_profile_exists(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            write(
                root / ".github/github_actions/workflow_required_surface_profiles.json",
                '{\n'
                '  "validate_on_pr": [\n'
                '    "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1"\n'
                "  ]\n"
                "}\n",
            )
            rel = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-001.ps1"
            write(root / rel)
            result = inventory.build_inventory(root, changed_files=[rel])
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("not listed" in error for error in result["validation"]["errors"]))

    def test_baseline_rejected_in_changed_mode(self) -> None:
        with self.make_minimal_repo() as temp:
            result = inventory.build_inventory(
                Path(temp),
                changed_files=["project_sources/collector/source/DCOIR_Collector.ps1"],
                baseline={"summary": {"by_category": {"collector_runtime_source_part": 2}}},
            )
        self.assertFalse(result["validation"]["success"])
        self.assertTrue(any("Baseline shrink checks require full inventory mode" in error for error in result["validation"]["errors"]))
