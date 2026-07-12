#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
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


class PowerShellReviewAssistSafetyTests(unittest.TestCase):
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

    def test_unsafe_input_path_rejected_before_read(self) -> None:
        with self.make_repo() as temp:
            report = self.build(Path(temp), surface_inventory="../outside.json")

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("repo-relative without traversal" in error for error in report["validation"]["errors"]))

    def test_unsafe_embedded_path_rejected_before_rendering(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)

            def make_unsafe(data: dict[str, object]) -> None:
                findings = data["findings"]
                findings[0]["path"] = "../outside.ps1"

            mutate_json(root / review.DEFAULT_RULE_RISK_REPORT, make_unsafe)
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("repo-relative without traversal" in error for error in report["validation"]["errors"]))

    def test_duplicate_source_path_alias_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report = self.build(Path(temp), rule_risk_matrix=review.DEFAULT_RULE_RISK_REPORT.as_posix())

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("duplicate or aliased source report path" in error for error in report["validation"]["errors"]))

    def test_unsafe_output_and_output_alias_are_rejected_before_write(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report = self.build(root)

            with self.assertRaises(review.ReviewAssistError):
                review.write_outputs(root, report, Path("../out.json"), review.DEFAULT_MARKDOWN_OUTPUT)
            with self.assertRaises(review.ReviewAssistError):
                review.write_outputs(root, report, review.DEFAULT_JSON_OUTPUT, review.DEFAULT_JSON_OUTPUT)
            with self.assertRaises(review.ReviewAssistError):
                review.write_outputs(root, report, Path(".github/workflows/adva_probe.yml"), review.DEFAULT_MARKDOWN_OUTPUT)
            with self.assertRaises(review.ReviewAssistError):
                review.write_outputs(
                    root,
                    report,
                    review.DEFAULT_JSON_OUTPUT,
                    Path("project_sources/collector/powershell_review_assist_report.sarif"),
                )

    def test_output_write_failure_persists_failed_json_when_possible(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report = self.build(root)
            original_write_text = Path.write_text

            def fail_markdown(path_self: Path, data: str, *args: object, **kwargs: object) -> int:
                if path_self.suffix == ".md":
                    raise OSError("simulated markdown write failure")
                return original_write_text(path_self, data, *args, **kwargs)

            with unittest.mock.patch.object(Path, "write_text", fail_markdown):
                with self.assertRaises(review.ReviewAssistError):
                    review.write_outputs(root, report, review.DEFAULT_JSON_OUTPUT, review.DEFAULT_MARKDOWN_OUTPUT)

            persisted = read_json(root / review.DEFAULT_JSON_OUTPUT)

        self.assertFalse(persisted["validation"]["success"])
        self.assertTrue(any("write failure" in error for error in persisted["validation"]["errors"]))

    def test_schema_contract_rejects_missing_required_field(self) -> None:
        schema = read_json(REPO_ROOT / review.DEFAULT_SCHEMA_PATH)
        with self.make_repo() as temp:
            report = self.build(Path(temp))
        report.pop("evidence_channels")

        errors = review.validate_against_schema_contract(report, schema)

        self.assertTrue(any("$.evidence_channels is required" == error for error in errors))

    def test_schema_contract_rejects_loose_summary_and_channel_shapes(self) -> None:
        schema = read_json(REPO_ROOT / review.DEFAULT_SCHEMA_PATH)
        with self.make_repo() as temp:
            report = self.build(Path(temp))

        bad_summary = json.loads(json.dumps(report))
        bad_summary["summary"]["normalized_finding_count"] = "22"
        bad_channel = json.loads(json.dumps(report))
        bad_channel["evidence_channels"]["analyzer"] = {}

        summary_errors = review.validate_against_schema_contract(bad_summary, schema)
        channel_errors = review.validate_against_schema_contract(bad_channel, schema)

        self.assertTrue(any("$.summary.normalized_finding_count type mismatch" in error for error in summary_errors))
        self.assertTrue(any("$.evidence_channels.analyzer.state is required" == error for error in channel_errors))

    def test_schema_contract_rejects_missing_and_unclaimed_artifact_shape_loss(self) -> None:
        schema = read_json(REPO_ROOT / review.DEFAULT_SCHEMA_PATH)
        with self.make_repo() as temp:
            report = self.build(Path(temp))

        bad_missing = json.loads(json.dumps(report))
        bad_missing["missing_artifacts"] = [{"source_issue": 262}]
        bad_unclaimed = json.loads(json.dumps(report))
        bad_unclaimed["unclaimed_artifacts"] = [{"source_issue": 267, "path": "future artifact"}]

        missing_errors = review.validate_against_schema_contract(bad_missing, schema)
        unclaimed_errors = review.validate_against_schema_contract(bad_unclaimed, schema)

        self.assertTrue(any("$.missing_artifacts[0].path is required" == error for error in missing_errors))
        self.assertTrue(any("$.missing_artifacts[0].reason is required" == error for error in missing_errors))
        self.assertTrue(any("$.unclaimed_artifacts[0].artifact_status is required" == error for error in unclaimed_errors))
        self.assertTrue(any("$.unclaimed_artifacts[0].reason is required" == error for error in unclaimed_errors))

    def test_schema_contract_rejects_validation_status_contradiction(self) -> None:
        schema = read_json(REPO_ROOT / review.DEFAULT_SCHEMA_PATH)
        with self.make_repo() as temp:
            report = self.build(Path(temp))

        report["validation"]["success"] = False
        report["summary"]["validation_success"] = True
        errors = review.validate_against_schema_contract(report, schema)

        self.assertTrue(any("$.summary.validation_success must match $.validation.success" == error for error in errors))

    def test_missing_rule_risk_matrix_context_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)

            def remove_matrix_row(data: dict[str, object]) -> None:
                data["checks"] = [
                    check
                    for check in data["checks"]
                    if check.get("rule_name") != "DCOIR.NoAnalyzerSkipSuccess"
                ]

            mutate_json(root / review.DEFAULT_RULE_RISK_MATRIX, remove_matrix_row)
            report = self.build(root)

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("missing #263 matrix risk_classes" in error for error in report["validation"]["errors"]))
        self.assertTrue(any("missing #263 matrix impact" in error for error in report["validation"]["errors"]))

    def test_unsafe_schema_path_returns_validation_error_without_traceback(self) -> None:
        with self.make_repo() as temp:
            report = self.build(Path(temp), schema="../outside.schema.json")

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("PowerShell review-assist schema path must be repo-relative" in error for error in report["validation"]["errors"]))
