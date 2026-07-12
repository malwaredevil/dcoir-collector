from __future__ import annotations

from powershell_finding_governance_test_support import *  # noqa: F403


class FindingGovernanceSourceTestsMixin:
    def test_default_missing_analyzer_report_fails_closed(self) -> None:
        with self.make_repo(write_analyzer_report=False) as temp:
            report, errors, _warnings = governance.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("powershell_analyzer_report.json" in error for error in errors))

    def test_custom_required_reports_still_require_analyzer_without_opt_out(self) -> None:
        with self.make_repo(write_analyzer_report=False) as temp:
            report, errors, _warnings = governance.build_report(
                self.args(
                    Path(temp),
                    finding_report=[governance.DEFAULT_CUSTOM_REPORT.as_posix()],
                )
            )

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("powershell_analyzer_report.json" in error for error in errors))

    def test_missing_analyzer_report_requires_explicit_opt_out(self) -> None:
        with self.make_repo(write_analyzer_report=False) as temp:
            report, errors, warnings = governance.build_report(
                self.args(Path(temp), allow_missing_analyzer_report=True)
            )

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertTrue(any("powershell_analyzer_report.json" in warning for warning in warnings))
        analyzer_input = next(
            item
            for item in report["input_reports"]
            if item["path"] == governance.DEFAULT_ANALYZER_REPORT.as_posix()
        )
        self.assertFalse(analyzer_input["required"])
        self.assertFalse(analyzer_input["present"])

    def test_analyzer_opt_out_is_recorded_with_other_optional_reports(self) -> None:
        with self.make_repo(write_analyzer_report=False) as temp:
            report, errors, warnings = governance.build_report(
                self.args(
                    Path(temp),
                    allow_missing_analyzer_report=True,
                    optional_finding_report=["extra-optional-report.json"],
                )
            )

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertTrue(any("extra-optional-report.json" in warning for warning in warnings))
        self.assertTrue(any("powershell_analyzer_report.json" in warning for warning in warnings))
        optional_paths = [
            item["path"]
            for item in report["input_reports"]
            if item.get("required") is False and item.get("present") is False
        ]
        self.assertIn("extra-optional-report.json", optional_paths)
        self.assertIn(governance.DEFAULT_ANALYZER_REPORT.as_posix(), optional_paths)

    def test_cli_rewrites_json_as_failed_when_markdown_write_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / "markdown-output-as-directory").mkdir()
            argv = [
                "run_powershell_finding_governance.py",
                "--repo-root",
                str(root),
                "--json-output",
                "report.json",
                "--markdown-output",
                "markdown-output-as-directory",
            ]
            with unittest.mock.patch.object(sys, "argv", argv):
                rc = governance.main()
            written = json.loads((root / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(rc, 1)
        self.assertFalse(written["validation"]["success"])
        self.assertTrue(any("report write failure" in error for error in written["validation"]["errors"]))

    def test_failed_required_source_report_is_not_collected(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report_path = root / governance.DEFAULT_CUSTOM_REPORT
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["validation"]["success"] = False
            write(report_path, json.dumps(report, indent=2) + "\n")
            built, errors, _warnings = governance.build_report(self.args(root))

        self.assertFalse(built["validation"]["success"])
        self.assertTrue(any("does not report successful validation: validation.success is false" in error for error in errors))
        self.assertEqual(built["summary"]["finding_count"], 0)

    def test_required_source_report_validation_object_blocks_top_level_success_fallback(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report_path = root / governance.DEFAULT_CUSTOM_REPORT
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["validation"] = {"errors": ["stale report"], "warnings": []}
            report["success"] = True
            write(report_path, json.dumps(report, indent=2) + "\n")
            built, errors, _warnings = governance.build_report(self.args(root))

        self.assertFalse(built["validation"]["success"])
        self.assertTrue(any("does not report successful validation: validation.success is missing" in error for error in errors))
        self.assertEqual(built["summary"]["finding_count"], 0)

    def test_failed_optional_source_report_is_not_collected(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            optional_path = root / "extra-optional-report.json"
            optional_report = {
                "schema_version": "extra_optional_schema_v1",
                "findings": [finding(fingerprint="optional-finding")],
                "validation": {"success": False, "errors": ["failed upstream"], "warnings": []},
                "summary": {"finding_count": 1},
            }
            write(optional_path, json.dumps(optional_report, indent=2) + "\n")
            built, errors, _warnings = governance.build_report(
                self.args(root, optional_finding_report=["extra-optional-report.json"])
            )

        self.assertFalse(built["validation"]["success"])
        self.assertTrue(any("extra-optional-report.json does not report successful validation" in error for error in errors))
        self.assertEqual(built["summary"]["finding_count"], 1)
        self.assertEqual(built["summary"]["decision_counts"], {"advisory": 1})
