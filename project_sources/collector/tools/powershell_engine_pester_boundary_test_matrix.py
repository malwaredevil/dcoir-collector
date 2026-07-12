from __future__ import annotations

from powershell_engine_pester_boundary_test_support import *  # noqa: F403


class EngineBoundaryMatrixTestsMixin:
    def test_control_boundary_passes(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["required_category_count"], len(boundary.REQUIRED_CHECK_CATEGORIES))
        self.assertFalse(report["summary"]["pester_blocking_for_static_validation"])
        self.assertFalse(report["independent_analyzer_enforcement_proof"]["requires_pester"])

    def test_missing_windows_51_category_fails_closed(self) -> None:
        doc = good_boundary_doc()
        doc["engine_matrix"] = [
            row
            for row in doc["engine_matrix"]  # type: ignore[index]
            if row["check_category"] != "windows_powershell_51_parser_runtime_compatibility"
        ]
        with self.make_repo(doc) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("engine_matrix missing categories" in error for error in errors))

    def test_ambiguous_engine_fails_closed(self) -> None:
        doc = good_boundary_doc()
        rows = doc["engine_matrix"]  # type: ignore[assignment]
        rows[0]["required_engine"] = "pwsh"  # type: ignore[index]
        with self.make_repo(doc) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("ambiguous engine" in error for error in errors))

    def test_pester_cannot_replace_analyzer_or_custom_checks(self) -> None:
        doc = good_boundary_doc()
        doc["policy"]["pester_may_replace_analyzer_or_custom_checks"] = True  # type: ignore[index]
        with self.make_repo(doc) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("Pester must not be allowed" in error for error in errors))

    def test_missing_pester_evidence_requirement_fails_closed(self) -> None:
        doc = good_boundary_doc()
        doc["pester_boundary"]["required_evidence_when_used"] = ["Pester version"]  # type: ignore[index]
        with self.make_repo(doc) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("required_evidence_when_used missing" in error for error in errors))

    def test_independent_proof_cannot_require_pester(self) -> None:
        doc = good_boundary_doc()
        doc["independent_analyzer_enforcement_proof"]["requires_pester"] = True  # type: ignore[index]
        with self.make_repo(doc) as temp:
            report, errors, _warnings = boundary.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("must not require Pester" in error for error in errors))

    def test_missing_dependency_report_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / boundary.DEFAULT_CUSTOM_REPORT).unlink()
            report, errors, _warnings = boundary.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("dependency report missing" in error for error in errors))

    def test_dependency_report_requires_explicit_validation_success(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report_path = root / boundary.DEFAULT_CUSTOM_REPORT
            dependency = json.loads(report_path.read_text(encoding="utf-8"))
            dependency["validation"] = {"errors": [], "warnings": []}
            write(report_path, json.dumps(dependency, indent=2) + "\n")
            report, errors, _warnings = boundary.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("validation.success is missing" in error for error in errors))
