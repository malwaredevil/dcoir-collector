from __future__ import annotations

from powershell_engine_pester_boundary_test_support import *  # noqa: F403


class EngineBoundaryReportTestsMixin:
    def test_dependency_report_accepts_documented_top_level_success(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report_path = root / boundary.DEFAULT_CUSTOM_REPORT
            dependency = json.loads(report_path.read_text(encoding="utf-8"))
            dependency.pop("validation", None)
            dependency["success"] = True
            write(report_path, json.dumps(dependency, indent=2) + "\n")
            report, errors, _warnings = boundary.build_report(self.args(root))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        custom_fact = next(
            fact
            for fact in report["dependency_reports"]
            if fact["path"] == boundary.DEFAULT_CUSTOM_REPORT.as_posix()
        )
        self.assertTrue(custom_fact["success"])

    def test_dependency_report_rejects_non_boolean_validation_success(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report_path = root / boundary.DEFAULT_CUSTOM_REPORT
            dependency = json.loads(report_path.read_text(encoding="utf-8"))
            dependency["validation"]["success"] = "true"
            dependency["success"] = True
            write(report_path, json.dumps(dependency, indent=2) + "\n")
            report, errors, _warnings = boundary.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("validation.success must be boolean true" in error for error in errors))

    def test_dependency_report_validation_object_blocks_top_level_success_fallback(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report_path = root / boundary.DEFAULT_CUSTOM_REPORT
            dependency = json.loads(report_path.read_text(encoding="utf-8"))
            dependency["validation"] = {"errors": ["stale report"], "warnings": []}
            dependency["success"] = True
            write(report_path, json.dumps(dependency, indent=2) + "\n")
            report, errors, _warnings = boundary.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("validation.success is missing" in error for error in errors))

    def test_traversing_repo_artifact_path_fails_before_claiming_evidence(self) -> None:
        doc = good_boundary_doc()
        rows = doc["engine_matrix"]  # type: ignore[assignment]
        rows[0]["output_artifact"] = "project_sources/collector/../../../outside-report.json"  # type: ignore[index]
        with self.make_repo(doc) as temp:
            root = Path(temp)
            write(root.parent / "outside-report.json", '{"unsafe": true}\n')
            report, errors, _warnings = boundary.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("output_artifact path must be a repo-relative path without traversal" in error for error in errors))
        artifact = report["declared_output_artifacts"][0]
        self.assertFalse(artifact["exists"])
        self.assertFalse(artifact["evidence_claimed_by_boundary"])

    def test_missing_blocking_repo_artifact_fails_without_explicit_status(self) -> None:
        doc = good_boundary_doc()
        rows = doc["engine_matrix"]  # type: ignore[assignment]
        rows[0]["output_artifact"] = "project_sources/collector/missing-report.json"  # type: ignore[index]
        with self.make_repo(doc) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("blocking engine matrix artifact missing" in error for error in errors))

    def test_explicit_not_committed_artifact_is_not_claimed_boundary_evidence(self) -> None:
        doc = good_boundary_doc()
        rows = doc["engine_matrix"]  # type: ignore[assignment]
        rows[0]["output_artifact"] = "project_sources/collector/missing-report.json"  # type: ignore[index]
        rows[0]["artifact_status"] = "not_committed_in_267_boundary"  # type: ignore[index]
        with self.make_repo(doc) as temp:
            report, errors, warnings = boundary.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertTrue(any("not committed or claimed" in warning for warning in warnings))
        artifact = report["declared_output_artifacts"][0]
        self.assertFalse(artifact["exists"])
        self.assertFalse(artifact["evidence_claimed_by_boundary"])
        self.assertEqual(artifact["artifact_status"], "not_committed_in_267_boundary")

    def test_custom_finding_proof_is_required(self) -> None:
        with self.make_repo(custom_findings=0) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("missing custom check findings" in error for error in errors))

    def test_governance_unclassified_findings_fail_closed(self) -> None:
        with self.make_repo(unclassified=1) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("unclassified governance findings" in error for error in errors))
