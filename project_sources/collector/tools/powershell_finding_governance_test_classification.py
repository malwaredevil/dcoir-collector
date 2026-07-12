from __future__ import annotations

from powershell_finding_governance_test_support import *  # noqa: F403


class FindingGovernanceClassificationTestsMixin:
    def test_fixture_classification_passes(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["finding_count"], 1)
        self.assertEqual(report["summary"]["decision_counts"], {"advisory": 1})

    def test_new_finding_without_classification_fails_closed(self) -> None:
        source_finding = finding(path="project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1")
        with self.make_repo(report_findings=[source_finding]) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("new unclassified PowerShell finding" in error for error in errors))

    def test_baseline_record_classifies_source_finding(self) -> None:
        source_finding = finding(path="project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1")
        with self.make_repo(
            report_findings=[source_finding],
            governance_overrides={"baseline_records": [baseline_record()]},
        ) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["decision_counts"], {"baseline-temporary": 1})

    def test_malformed_baseline_fails_closed(self) -> None:
        bad_record = baseline_record()
        bad_record.pop("fingerprint")
        with self.make_repo(governance_overrides={"baseline_records": [bad_record]}) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("missing fingerprint" in error for error in errors))

    def test_severity_increase_fails_closed(self) -> None:
        source_finding = finding(
            path="project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
            severity="Error",
        )
        record = baseline_record(severity="Warning")
        with self.make_repo(
            report_findings=[source_finding],
            governance_overrides={"baseline_records": [record]},
        ) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("severity increase" in error for error in errors))

    def test_unexpected_baseline_disappearance_fails_closed(self) -> None:
        with self.make_repo(report_findings=[], governance_overrides={"baseline_records": [baseline_record()]}) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("unexpected disappearance" in error for error in errors))

    def test_blanket_suppression_fails_closed(self) -> None:
        suppression = suppression_record(path="*", rule_name="PS*")
        with self.make_repo(governance_overrides={"suppressions": [suppression]}) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("blanket or wildcard path" in error for error in errors))
        self.assertTrue(any("blanket or wildcard rule" in error for error in errors))

    def test_generated_output_suppression_requires_assembly_coverage(self) -> None:
        suppression = suppression_record(
            path="compiled_runtime/DCOIR_Collector.ps1",
            target_kind="generated_output",
        )
        with self.make_repo(governance_overrides={"suppressions": [suppression]}) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("#265 assembly coverage" in error for error in errors))

    def test_real_repo_contract_passes(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        report, errors, _warnings = governance.build_report(
            self.args(repo_root, allow_missing_analyzer_report=True)
        )

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["finding_count"], 22)
        self.assertEqual(report["summary"]["unclassified_finding_count"], 0)
        self.assertEqual(report["summary"]["decision_counts"], {"advisory": 22})
        self.assertEqual(report["summary"]["baseline_record_count"], 0)
        self.assertEqual(report["summary"]["suppression_count"], 0)
