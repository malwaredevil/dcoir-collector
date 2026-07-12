#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import textwrap
import unittest
import unittest.mock
from pathlib import Path

try:
    from .powershell_analyzer_test_support import (
        PowerShellAnalyzerTestCase,
        analyzer,
        surface,
        update_inventory_sha256,
        write,
    )
except ImportError:  # pragma: no cover - direct file execution support
    from powershell_analyzer_test_support import (
        PowerShellAnalyzerTestCase,
        analyzer,
        surface,
        update_inventory_sha256,
        write,
    )


class PowerShellAnalyzerBaselineTests(PowerShellAnalyzerTestCase):
    def test_expected_bad_fixture_without_findings_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            bad = root / "project_sources/collector/source/DCOIR_Collector.ps1"
            bad_text = "Write-Host 'should be caught'\n"
            bad.write_text(bad_text, encoding="utf-8")
            update_inventory_sha256(root, "project_sources/collector/source/DCOIR_Collector.ps1", bad_text)
            args = self.make_args(
                root,
                "no_findings",
                target_path=["project_sources/collector/source/DCOIR_Collector.ps1"],
                allow_findings=True,
                expect_finding_rule="PSAvoidUsingWriteHost",
                expect_finding_path="project_sources/collector/source/DCOIR_Collector.ps1",
            )
            report, errors, _warnings = analyzer.build_report(args)

        self.assertIsNotNone(report)
        self.assertTrue(any("expected analyzer finding PSAvoidUsingWriteHost" in error for error in errors))

    def test_bad_fixture_finding_fails_and_normalizes(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            bad_text = "Write-Host 'bad'\n"
            write(root / rel, bad_text)
            update_inventory_sha256(root, rel, bad_text)
            args = self.make_args(root, target_path=[rel])
            report, errors, _warnings = analyzer.build_report(args)

        self.assertIsNotNone(report)
        assert report is not None
        self.assertTrue(any("unsuppressed analyzer findings" in error for error in errors))
        self.assertEqual(report["findings"][0]["path"], rel)
        self.assertEqual(report["findings"][0]["rule_name"], "PSAvoidUsingWriteHost")
        self.assertEqual(report["findings"][0]["severity"], "Warning")

    def test_baseline_parse_failure_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            baseline = root / "bad-baseline.json"
            write(baseline, "{not-json")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, baseline_json=baseline.name))

        self.assertIsNotNone(report)
        self.assertTrue(any("baseline" in error and "invalid JSON" in error for error in errors))

    def test_baseline_path_outside_repo_fails_before_reading(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            outside = root.parent / "outside-baseline.json"
            write(outside, "{not-json")
            report, errors, _warnings = analyzer.build_report(
                self.make_args(root, baseline_json=outside.as_posix())
            )

        self.assertIsNotNone(report)
        self.assertTrue(
            any("PowerShell analyzer baseline path must be a repo-relative path without traversal" in error for error in errors),
            errors,
        )
        self.assertFalse(any("invalid JSON" in error for error in errors), errors)
        assert report is not None
        self.assertFalse(report["baseline"]["accepted"])

    def test_baseline_traversal_path_fails_before_reading(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(root.parent / "outside-baseline.json", "{not-json")
            report, errors, _warnings = analyzer.build_report(
                self.make_args(root, baseline_json="../outside-baseline.json")
            )

        self.assertIsNotNone(report)
        self.assertTrue(
            any("PowerShell analyzer baseline path must be a repo-relative path without traversal" in error for error in errors),
            errors,
        )
        self.assertFalse(any("invalid JSON" in error for error in errors), errors)
        assert report is not None
        self.assertFalse(report["baseline"]["accepted"])

    def test_baseline_symlink_loop_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            loop = root / "loop-baseline.json"
            try:
                loop.symlink_to(loop)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            report, errors, _warnings = analyzer.build_report(
                self.make_args(root, baseline_json=loop.name)
            )

        self.assertIsNotNone(report)
        self.assertTrue(
            any("PowerShell analyzer baseline path must resolve inside the repository root" in error for error in errors),
            errors,
        )
        assert report is not None
        self.assertFalse(report["baseline"]["accepted"])

    def test_inventory_and_settings_paths_must_stay_inside_repo(self) -> None:
        scenarios = [
            ("inventory", "../outside-inventory.json", "PowerShell surface inventory path", "inventory"),
            ("settings", "../outside-settings.psd1", "analyzer settings path", "settings"),
        ]
        for arg_name, unsafe_path, expected_label, report_key in scenarios:
            with self.subTest(arg_name=arg_name):
                with self.make_repo() as temp:
                    root = Path(temp)
                    report, errors, _warnings = analyzer.build_report(
                        self.make_args(root, **{arg_name: unsafe_path})
                    )

                self.assertIsNotNone(report)
                self.assertTrue(
                    any(f"{expected_label} must be a repo-relative path without traversal" in error for error in errors),
                    errors,
                )
                assert report is not None
                self.assertFalse(report[report_key]["accepted"])

    def test_inventory_surface_symlink_loop_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            rel = "project_sources/collector/source/loop.ps1"
            loop = root / rel
            try:
                loop.symlink_to(loop)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            inventory_path = root / analyzer.DEFAULT_INVENTORY
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["surfaces"].append(
                surface(rel, "collector_runtime_source_part", ".ps1", sha256="0" * 64)
            )
            write(inventory_path, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any(f"{rel}: inventory path resolves outside repo root" in error for error in errors), errors)

    def test_suppressed_rule_mismatch_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            write(
                baseline,
                json.dumps(
                    {
                        "schema_version": analyzer.BASELINE_SCHEMA_VERSION,
                        "suppressions": [
                            {
                                "path": "project_sources/collector/source/DCOIR_Collector.ps1",
                                "rule_name": "PSAvoidUsingWriteHost",
                                "fingerprint": "0" * 64,
                                "reason": "test",
                            }
                        ],
                    }
                ),
            )
            report, errors, _warnings = analyzer.build_report(self.make_args(root, baseline_json=baseline.name))

        self.assertIsNotNone(report)
        self.assertTrue(any("suppressed-rule mismatch" in error for error in errors))

    def test_baseline_suppression_requires_fingerprint(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            write(
                baseline,
                json.dumps(
                    {
                        "schema_version": analyzer.BASELINE_SCHEMA_VERSION,
                        "suppressions": [
                            {
                                "path": "project_sources/collector/source/DCOIR_Collector.ps1",
                                "rule_name": "PSAvoidUsingWriteHost",
                                "reason": "test",
                            }
                        ],
                    }
                ),
            )
            report, errors, _warnings = analyzer.build_report(self.make_args(root, baseline_json=baseline.name))

        self.assertIsNotNone(report)
        self.assertTrue(any("baseline suppression missing fingerprint" in error for error in errors))

    def test_baseline_suppression_must_match_one_finding(self) -> None:
        finding = {
            "path": "project_sources/collector/source/DCOIR_Collector.ps1",
            "rule_name": "PSAvoidUsingWriteHost",
            "fingerprint": "abc",
            "suppressed_by_baseline": False,
        }
        errors = analyzer.apply_baseline(
            [finding.copy(), finding.copy()],
            {
                "schema_version": analyzer.BASELINE_SCHEMA_VERSION,
                "suppressions": [
                    {
                        "path": finding["path"],
                        "rule_name": finding["rule_name"],
                        "fingerprint": finding["fingerprint"],
                        "reason": "duplicate fixture",
                    }
                ],
            },
        )

        self.assertTrue(any("matched 2 analyzer findings, expected 1" in error for error in errors))

    def test_duplicate_baseline_suppressions_fail_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            suppression = {
                "path": "project_sources/collector/source/DCOIR_Collector.ps1",
                "rule_name": "PSAvoidUsingWriteHost",
                "fingerprint": "abc",
                "reason": "duplicate fixture",
            }
            write(
                baseline,
                json.dumps(
                    {
                        "schema_version": analyzer.BASELINE_SCHEMA_VERSION,
                        "suppressions": [suppression, suppression],
                    }
                ),
            )
            report, errors, _warnings = analyzer.build_report(self.make_args(root, baseline_json=baseline.name))

        self.assertIsNotNone(report)
        self.assertTrue(any("baseline duplicate suppression" in error for error in errors))

    def test_matching_baseline_suppresses_finding(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            bad_text = "Write-Host 'baseline accepted for now'\n"
            write(root / rel, bad_text)
            update_inventory_sha256(root, rel, bad_text)
            initial_report, initial_errors, _warnings = analyzer.build_report(
                self.make_args(root, target_path=[rel], allow_findings=True)
            )
            self.assertEqual(initial_errors, [])
            assert initial_report is not None
            fingerprint = initial_report["findings"][0]["fingerprint"]
            baseline = root / "baseline.json"
            write(
                baseline,
                json.dumps(
                    {
                        "schema_version": analyzer.BASELINE_SCHEMA_VERSION,
                        "suppressions": [
                            {
                                "path": rel,
                                "rule_name": "PSAvoidUsingWriteHost",
                                "fingerprint": fingerprint,
                                "reason": "temporary reviewed baseline in test",
                            }
                        ],
                    }
                ),
            )
            report, errors, _warnings = analyzer.build_report(
                self.make_args(root, target_path=[rel], baseline_json=baseline.name)
            )

        self.assertEqual(errors, [])
        assert report is not None
        self.assertEqual(report["summary"]["suppressed_finding_count"], 1)
        self.assertEqual(report["summary"]["unsuppressed_finding_count"], 0)
        self.assertEqual(report["baseline"]["matched_suppression_count"], 1)
        self.assertEqual(report["baseline"]["suppression_keys"][0]["fingerprint"], fingerprint)



if __name__ == "__main__":
    unittest.main()
