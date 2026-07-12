from __future__ import annotations

from powershell_report_ingestion_safety_test_support import *  # noqa: F403


class ReportIngestionEngineSafetyTestsMixin:
    def test_engine_boundary_rejects_traversing_extra_report_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / boundary.DEFAULT_BOUNDARY, json.dumps(boundary_doc(), indent=2) + "\n")
            write_boundary_reports(root)
            write(root.parent / "outside-dependency.json", "not json\n")
            report, errors, _warnings = boundary.build_report(
                boundary_args(
                    root,
                    [boundary.DEFAULT_ASSEMBLY_REPORT.as_posix(), "../outside-dependency.json"],
                )
            )

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("dependency report path must be a repo-relative path without traversal" in error for error in errors))
        self.assertFalse(any("invalid JSON" in error for error in errors))
