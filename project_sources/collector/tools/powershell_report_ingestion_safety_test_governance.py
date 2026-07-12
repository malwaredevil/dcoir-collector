from __future__ import annotations

from powershell_report_ingestion_safety_test_support import *  # noqa: F403


class ReportIngestionGovernanceSafetyTestsMixin:
    def test_finding_governance_rejects_failed_assembly_report_before_using_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, assembly_success=False)
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("powershell_assembly_parity_report.json does not report successful validation" in error for error in errors))
        self.assertFalse(report["assembly_parity_report"]["validation_success"])
        self.assertEqual(report["assembly_parity_report"]["generated_output_paths"], [])

    def test_finding_governance_rejects_traversing_generated_output_path_before_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, assembly_generated_path="../outside-generated.ps1")
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(
            any("PowerShell assembly parity generated output path must be a repo-relative path without traversal" in error for error in errors)
        )
        self.assertEqual(report["assembly_parity_report"]["generated_output_paths"], [])

    def test_finding_governance_rejects_traversing_finding_path_before_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, finding_path="../outside-finding.ps1")
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("finding path must be a repo-relative path without traversal" in error for error in errors))

    def test_finding_governance_rejects_traversing_classification_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, classification_path_prefixes=["../outside/"])
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("path_prefixes[1] prefix must be a repo-relative prefix without traversal" in error for error in errors))

    def test_finding_governance_classification_prefix_respects_path_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(
                root,
                finding_path="project_sources/collector/tools/finding.ps1",
                classification_path_prefixes=["project_sources/collector/tool"],
            )
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(
            any(
                "new unclassified PowerShell finding: project_sources/collector/tools/finding.ps1"
                in error
                for error in errors
            )
        )

    def test_finding_governance_rejects_traversing_classification_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, classification_paths=["../outside-finding.ps1"])
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("paths[1] path must be a repo-relative path without traversal" in error for error in errors))

    def test_finding_governance_rejects_traversing_baseline_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, baseline_path="../outside-baseline.ps1")
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("baseline record unsafe-baseline path must be a repo-relative path without traversal" in error for error in errors))

    def test_finding_governance_rejects_traversing_suppression_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root, suppression_path="../outside-suppression.ps1")
            report, errors, _warnings = governance.build_report(governance_args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("suppression unsafe-suppression path must be a repo-relative path without traversal" in error for error in errors))

    def test_finding_governance_rejects_traversing_optional_report_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root)
            write(root.parent / "outside-finding-report.json", "not json\n")
            report, errors, _warnings = governance.build_report(
                governance_args(root, optional_finding_report=["../outside-finding-report.json"])
            )

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("PowerShell finding report path must be a repo-relative path without traversal" in error for error in errors))
        self.assertFalse(any("invalid JSON" in error for error in errors))

    def test_finding_governance_rejects_traversing_assembly_report_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_governance_repo(root)
            write(root.parent / "outside-assembly-report.json", "not json\n")
            report, errors, _warnings = governance.build_report(
                governance_args(root, assembly_parity_report="../outside-assembly-report.json")
            )

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("PowerShell assembly parity report path must be a repo-relative path without traversal" in error for error in errors))
        self.assertFalse(any("invalid JSON" in error for error in errors))
