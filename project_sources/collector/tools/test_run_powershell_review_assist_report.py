#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_review_assist_report as review

REPO_ROOT = Path(__file__).resolve().parents[3]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def mutate_json(path: Path, mutator) -> None:
    data = read_json(path)
    mutator(data)
    write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


class PowerShellReviewAssistReportTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for path in (
            review.DEFAULT_SCHEMA_PATH,
            review.DEFAULT_SURFACE_INVENTORY,
            review.DEFAULT_RULE_RISK_REPORT,
            review.DEFAULT_RULE_RISK_MATRIX,
            review.DEFAULT_CUSTOM_REPORT,
            review.DEFAULT_ASSEMBLY_PARITY_REPORT,
            review.DEFAULT_GOVERNANCE_REPORT,
            review.DEFAULT_ENGINE_BOUNDARY_REPORT,
            review.DEFAULT_FUNCTION_REACHABILITY_REPORT,
        ):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / path, target)
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": str(root),
            "schema": review.DEFAULT_SCHEMA_PATH.as_posix(),
            "surface_inventory": review.DEFAULT_SURFACE_INVENTORY.as_posix(),
            "rule_risk_report": review.DEFAULT_RULE_RISK_REPORT.as_posix(),
            "rule_risk_matrix": review.DEFAULT_RULE_RISK_MATRIX.as_posix(),
            "custom_report": review.DEFAULT_CUSTOM_REPORT.as_posix(),
            "assembly_parity_report": review.DEFAULT_ASSEMBLY_PARITY_REPORT.as_posix(),
            "governance_report": review.DEFAULT_GOVERNANCE_REPORT.as_posix(),
            "engine_boundary_report": review.DEFAULT_ENGINE_BOUNDARY_REPORT.as_posix(),
            "function_reachability_report": review.DEFAULT_FUNCTION_REACHABILITY_REPORT.as_posix(),
            "analyzer_report": review.DEFAULT_ANALYZER_REPORT.as_posix(),
            "json_output": review.DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown_output": review.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            "no_write": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def build(self, root: Path, **overrides: object) -> dict[str, object]:
        report, _errors, _warnings = review.build_report(self.args(root, **overrides))
        return report

    def test_real_report_contract_passes_and_preserves_boundaries(self) -> None:
        with self.make_repo() as temp:
            report = self.build(Path(temp))

        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["normalized_finding_count"], 22)
        self.assertEqual(report["evidence_channels"]["analyzer"]["state"], "optional_missing")
        self.assertEqual(report["changed_file_context"]["changed_file_count"], None)
        self.assertEqual(report["summary"]["required_source_reports_present"], 8)
        self.assertEqual(report["summary"]["optional_source_reports_missing"], 1)
        self.assertGreaterEqual(report["summary"]["carried_forward_warning_count"], 8)
        self.assertTrue(any("No workflow YAML" in claim for claim in report["non_claims"]))
        self.assertEqual(report["artifact_contract"]["workflow_behavior"], "none")
        self.assertEqual(report["surface_inventory"]["summary"]["total_surfaces"], 243)
        self.assertTrue(report["surface_inventory"]["excluded_paths"])
        self.assertTrue(report["surface_inventory"]["reference_paths"])
        self.assertTrue(
            any(item["path"] == "compiled_runtime/DCOIR_Collector.ps1" for item in report["evidence_channels"]["assembly_parity"]["generated_outputs"])
        )
        self.assertEqual(report["evidence_channels"]["finding_governance"]["baseline_delta"]["baseline_record_count"], 0)
        self.assertEqual(report["evidence_channels"]["finding_governance"]["baseline_delta"]["suppression_count"], 0)
        self.assertEqual(report["evidence_channels"]["function_reachability"]["function_count"], 171)
        self.assertEqual(report["evidence_channels"]["function_reachability"]["classification_counts"]["literal_referenced"], 167)
        self.assertEqual(report["evidence_channels"]["function_reachability"]["coverage_state"], "not_collected")

    def test_schema_validates_generated_report_and_seeded_good_example(self) -> None:
        schema = read_json(REPO_ROOT / review.DEFAULT_SCHEMA_PATH)
        with self.make_repo() as temp:
            report = self.build(Path(temp))
        self.assertEqual([], review.validate_against_schema_contract(report, schema))

        fixture = REPO_ROOT / "project_sources/collector/fixtures/powershell_review_assist/good_report.json"
        self.assertTrue(fixture.exists())
        seeded = read_json(fixture)
        self.assertEqual([], review.validate_against_schema_contract(seeded, schema))
        self.assertTrue(seeded["validation"]["success"])
        self.assertEqual("compact_sample", seeded["fixture_contract"]["kind"])
        self.assertEqual(review.DEFAULT_JSON_OUTPUT.as_posix(), seeded["fixture_contract"]["full_report_path"])
        self.assertEqual(22, seeded["fixture_contract"]["full_report_summary"]["normalized_finding_count"])
        self.assertEqual(len(seeded["findings"]), seeded["summary"]["normalized_finding_count"])
        self.assertEqual(
            dict(sorted(Counter(finding["evidence_kind"] for finding in seeded["findings"]).items())),
            seeded["summary"]["finding_count_by_evidence_kind"],
        )
        self.assertEqual(
            {
                "exclude": len(seeded["surface_inventory"]["excluded_paths"]),
                "include": len(seeded["surface_inventory"]["included_paths"]),
                "reference": len(seeded["surface_inventory"]["reference_paths"]),
                "skip": len(seeded["surface_inventory"]["skipped_paths"]),
            },
            seeded["surface_inventory"]["path_decision_counts"],
        )
        self.assertLess(
            seeded["summary"]["normalized_finding_count"],
            seeded["fixture_contract"]["full_report_summary"]["normalized_finding_count"],
        )

    def test_markdown_parity_covers_source_counts_findings_warnings_and_non_claims(self) -> None:
        with self.make_repo() as temp:
            report = self.build(Path(temp))
        markdown = review.render_markdown(report)

        self.assertEqual([], review.validate_markdown_parity(report, markdown))
        for fragment in (
            "optional_missing",
            "project_sources/collector/powershell_rule_risk_fixture_report.json",
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            "No #269, #270, PR/workflow readiness, or parent #260 closeability claim is made by #268.",
            "compiled_runtime/DCOIR_Collector.ps1",
            "Baseline records: `0`",
            "function_reachability",
            "coverage not_collected",
        ):
            self.assertIn(fragment, markdown)

    def test_markdown_divergence_is_detected(self) -> None:
        with self.make_repo() as temp:
            report = self.build(Path(temp))
        markdown = review.render_markdown(report).replace(
            "project_sources/collector/powershell_rule_risk_fixture_report.json",
            "removed-source-report",
        )

        self.assertTrue(review.validate_markdown_parity(report, markdown))

    def test_missing_required_report_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / review.DEFAULT_RULE_RISK_REPORT).unlink()
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(
            any("required source report is missing" in (item.get("absent_reason") or "") for item in report["source_reports"])
        )
        self.assertTrue(any("is missing" in error for error in report["validation"]["errors"]))

    def test_malformed_json_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(root / review.DEFAULT_CUSTOM_REPORT, "{not json")
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("invalid JSON" in error for error in report["validation"]["errors"]))

    def test_wrong_schema_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            mutate_json(root / review.DEFAULT_CUSTOM_REPORT, lambda data: data.update({"schema_version": "wrong"}))
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("schema mismatch" in error for error in report["validation"]["errors"]))

    def test_upstream_validation_failure_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)

            def fail(data: dict[str, object]) -> None:
                data["validation"] = {"success": False, "errors": ["upstream failed"], "warnings": []}

            mutate_json(root / review.DEFAULT_SURFACE_INVENTORY, fail)
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("validation.success is false" in error for error in report["validation"]["errors"]))

    def test_missing_consumed_field_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            mutate_json(root / review.DEFAULT_RULE_RISK_REPORT, lambda data: data.pop("environment_gap", None))
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("missing environment_gap" in error for error in report["validation"]["errors"]))

    def test_optional_analyzer_absence_is_honest_but_present_failure_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report = self.build(root)
            self.assertTrue(report["validation"]["success"])
            self.assertEqual(report["evidence_channels"]["analyzer"]["state"], "optional_missing")

            analyzer = {
                "schema_version": review.SCHEMA_VERSIONS["analyzer_report"],
                "validation": {"success": False, "errors": ["analyzer failed"], "warnings": []},
                "summary": {"finding_count": 0},
                "findings": [],
                "targets": [],
                "skipped_surfaces": [],
                "analyzer": {},
                "powershell": {},
                "settings": {},
                "inventory": {},
                "baseline": {},
                "outputs": {},
            }
            write(root / review.DEFAULT_ANALYZER_REPORT, json.dumps(analyzer, indent=2) + "\n")
            failed_report = self.build(root)

        self.assertFalse(failed_report["validation"]["success"])
        self.assertEqual(failed_report["evidence_channels"]["analyzer"]["state"], "present_failed")
        self.assertTrue(any("validation.success is false" in error for error in failed_report["validation"]["errors"]))
