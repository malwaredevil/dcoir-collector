#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest.mock
from pathlib import Path

from powershell_rule_risk_fixtures_test_support import RuleRiskFixtureTestCase, harness, write


class PowerShellRuleRiskFixturePathSafetyTests(RuleRiskFixtureTestCase):
    def test_unsafe_absolute_fixture_path_is_not_hashed(self) -> None:
        with self.make_repo(matrix_fixtures=["bad-write-host", "outside-fixture"]) as temp:
            root = Path(temp)
            outside = root / "outside.ps1"
            write(outside, 'Write-Host "outside"\n')
            manifest_path = root / harness.DEFAULT_MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixtures"].append(
                {
                    "id": "outside-fixture",
                    "kind": "negative",
                    "path": outside.as_posix(),
                    "description": "Unsafe absolute fixture path.",
                    "expected_findings": [
                        {
                            "check_id": "pssa-avoid-write-host",
                            "rule_name": "PSAvoidUsingWriteHost",
                            "severity": "Warning",
                            "line": 1,
                            "risk_class": "review_assist_output_quality",
                        }
                    ],
                }
            )
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")
            original_sha256_file = harness.sha256_file

            def guarded_sha256(path: Path) -> str:
                if path.resolve() == outside.resolve():
                    raise AssertionError("unsafe hash attempted")
                return original_sha256_file(path)

            with unittest.mock.patch.object(harness, "sha256_file", side_effect=guarded_sha256):
                report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("fixture path must be repo-relative" in error for error in errors))
        self.assertTrue(any("matrix references missing fixture ids: outside-fixture" in error for error in errors))

    def test_parent_traversal_fixture_path_is_not_hashed(self) -> None:
        with self.make_repo(matrix_fixtures=["bad-write-host", "outside-fixture"]) as temp:
            root = Path(temp)
            write(root / "project_sources/collector/fixtures/powershell_analysis/escape.ps1", 'Write-Host "safe"\n')
            write(root / "project_sources/collector/fixtures/outside.ps1", 'Write-Host "outside"\n')
            manifest_path = root / harness.DEFAULT_MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixtures"].append(
                {
                    "id": "outside-fixture",
                    "kind": "negative",
                    "path": "project_sources/collector/fixtures/powershell_analysis/../outside.ps1",
                    "description": "Unsafe traversal fixture path.",
                    "expected_findings": [
                        {
                            "check_id": "pssa-avoid-write-host",
                            "rule_name": "PSAvoidUsingWriteHost",
                            "severity": "Warning",
                            "line": 1,
                            "risk_class": "review_assist_output_quality",
                        }
                    ],
                }
            )
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")
            unsafe = root / "project_sources/collector/fixtures/outside.ps1"
            original_sha256_file = harness.sha256_file

            def guarded_sha256(path: Path) -> str:
                if path.resolve() == unsafe.resolve():
                    raise AssertionError("unsafe hash attempted")
                return original_sha256_file(path)

            with unittest.mock.patch.object(harness, "sha256_file", side_effect=guarded_sha256):
                report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("fixture path must be repo-relative" in error for error in errors))
        self.assertTrue(any("matrix references missing fixture ids: outside-fixture" in error for error in errors))

    def test_fixture_symlink_resolving_outside_root_is_not_hashed(self) -> None:
        with self.make_repo(matrix_fixtures=["bad-write-host", "outside-fixture"]) as temp:
            root = Path(temp)
            outside = root / "outside.ps1"
            write(outside, 'Write-Host "outside"\n')
            link = root / "project_sources/collector/fixtures/powershell_analysis/bad/outside_link.ps1"
            try:
                link.unlink(missing_ok=True)
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            manifest_path = root / harness.DEFAULT_MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixtures"].append(
                {
                    "id": "outside-fixture",
                    "kind": "negative",
                    "path": "project_sources/collector/fixtures/powershell_analysis/bad/outside_link.ps1",
                    "description": "Unsafe symlink fixture path.",
                    "expected_findings": [
                        {
                            "check_id": "pssa-avoid-write-host",
                            "rule_name": "PSAvoidUsingWriteHost",
                            "severity": "Warning",
                            "line": 1,
                            "risk_class": "review_assist_output_quality",
                        }
                    ],
                }
            )
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")
            original_sha256_file = harness.sha256_file

            def guarded_sha256(path: Path) -> str:
                if path.resolve() == outside.resolve():
                    raise AssertionError("unsafe hash attempted")
                return original_sha256_file(path)

            with unittest.mock.patch.object(harness, "sha256_file", side_effect=guarded_sha256):
                report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("fixture path resolves outside" in error for error in errors))
        self.assertTrue(any("matrix references missing fixture ids: outside-fixture" in error for error in errors))

    def test_symlinked_fixture_root_is_not_hashed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            fixture_root = root / harness.FIXTURE_ROOT
            redirected_root = root / "redirected_fixture_root"
            try:
                fixture_root.rename(redirected_root)
                fixture_root.symlink_to(redirected_root, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            unsafe = redirected_root / "bad/write_host.ps1"
            original_sha256_file = harness.sha256_file

            def guarded_sha256(path: Path) -> str:
                if path.resolve() == unsafe.resolve():
                    raise AssertionError("unsafe hash attempted")
                return original_sha256_file(path)

            with unittest.mock.patch.object(harness, "sha256_file", side_effect=guarded_sha256):
                report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("fixture root must not be a symlink" in error for error in errors))
        self.assertTrue(any("matrix references missing fixture ids: bad-write-host" in error for error in errors))

    def test_directory_shaped_fixture_path_is_not_hashed(self) -> None:
        with self.make_repo(matrix_fixtures=["bad-write-host", "directory-fixture"]) as temp:
            root = Path(temp)
            directory_fixture = root / "project_sources/collector/fixtures/powershell_analysis/bad/directory.ps1"
            directory_fixture.mkdir()
            manifest_path = root / harness.DEFAULT_MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixtures"].append(
                {
                    "id": "directory-fixture",
                    "kind": "negative",
                    "path": "project_sources/collector/fixtures/powershell_analysis/bad/directory.ps1",
                    "description": "Directory-shaped fixture path.",
                    "expected_findings": [
                        {
                            "check_id": "pssa-avoid-write-host",
                            "rule_name": "PSAvoidUsingWriteHost",
                            "severity": "Warning",
                            "line": 1,
                            "risk_class": "review_assist_output_quality",
                        }
                    ],
                }
            )
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")
            original_sha256_file = harness.sha256_file

            def guarded_sha256(path: Path) -> str:
                if path.resolve() == directory_fixture.resolve():
                    raise AssertionError("unsafe hash attempted")
                return original_sha256_file(path)

            with unittest.mock.patch.object(harness, "sha256_file", side_effect=guarded_sha256):
                report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("fixture path must be a file" in error for error in errors))
        self.assertTrue(any("matrix references missing fixture ids: directory-fixture" in error for error in errors))
