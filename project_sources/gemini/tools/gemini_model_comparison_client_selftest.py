#!/usr/bin/env python3
"""Offline Gemini comparison resolution and report-output regression tests."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import gemini_model_comparison_api as gemini_compare
import run_gemini_model_comparison as comparison_runner


class GeminiComparisonClientTests(unittest.TestCase):
    def test_model_resolution_never_silently_substitutes_latest_alias(self):
        def model(name, methods=("generateContent",)):
            return {"name": "models/" + name, "supportedGenerationMethods": list(methods)}

        catalog = [
            model("gemini-3.1-pro-latest"),
            model("gemini-3.5-flash-preview"),
            model("gemini-3.5-flash"),
            model("gemini-3.1-pro-preview"),
            model("gemini-3.5-flash-image"),
            model("gemini-3.1-flash-lite", ("embedContent",)),
        ]
        resolved = gemini_compare.resolve_requested_models([
            "gemini-3.1-pro-preview", "models/gemini-3.1-pro-preview",
            "gemini-3.1-pro-latest", "gemini-3.5-flash",
            "models/nested/gemini-3.5-flash", "gemini-3.5-flash?x",
            "gemini-3.5-flash-preview", "gemini-3.5-flash-image",
            "gemini-3.1-flash-lite",
        ], catalog)
        self.assertEqual(
            resolved["gemini-3.1-pro-preview"]["name"],
            "models/gemini-3.1-pro-preview",
        )
        self.assertEqual(
            resolved["models/gemini-3.1-pro-preview"]["name"],
            "models/gemini-3.1-pro-preview",
        )
        self.assertEqual(
            resolved["gemini-3.5-flash"]["name"],
            "models/gemini-3.5-flash",
        )
        self.assertEqual(
            resolved["gemini-3.5-flash-preview"]["name"],
            "models/gemini-3.5-flash-preview",
        )
        for unsupported in (
            "gemini-3.1-pro-latest", "gemini-3.5-flash-image",
            "gemini-3.1-flash-lite", "models/nested/gemini-3.5-flash",
            "gemini-3.5-flash?x",
        ):
            self.assertNotIn(unsupported, resolved)
        only_alias = [model("gemini-3.1-pro-latest")]
        self.assertNotIn(
            "gemini-3.1-pro-preview",
            gemini_compare.resolve_requested_models(["gemini-3.1-pro-preview"], only_alias),
        )
        self.assertEqual(
            gemini_compare.model_resolution_warning(
                "gemini-3.1-pro-preview", only_alias,
            ), "similar_model_alias_not_selected",
        )
        self.assertEqual(
            gemini_compare.model_resolution_warning(
                "gemini-3.1-pro-latest", catalog,
            ), "unpinned_latest_alias_rejected",
        )

    def test_model_resolution_rejects_nested_catalog_paths(self):
        malformed_catalog = [
            {
                "name": "models/nested/gemini-3.5-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-3.5-flash?x",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
        self.assertEqual(
            gemini_compare.resolve_requested_models(
                ["gemini-3.5-flash"], malformed_catalog,
            ),
            {},
        )

    def test_empty_or_zero_repeat_cases_do_not_claim_called_models(self):
        catalog = [{
            "name": "models/gemini-3.1-pro-preview",
            "supportedGenerationMethods": ["generateContent"],
        }]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for cases, repeats in (([], 1), ([{"id": "MOCK-001", "turns": []}], 0)):
                with self.subTest(case_count=len(cases), repeat_count=repeats):
                    fixture = root / "fixtures.json"
                    fixture.write_text(json.dumps({"cases": cases}), encoding="utf-8")
                    output_dir = root / f"report_{len(cases)}"
                    argv = [
                        "run_gemini_model_comparison.py", "--fixtures", str(fixture),
                        "--output-dir", str(output_dir),
                        "--reference-model", "gemini-3.1-pro-preview",
                        "--candidate-models", "", "--repeat-count", str(repeats),
                    ]
                    with patch.dict(os.environ, {"DCOIR_GEMINI_API": "fake-key"}), \
                         patch.object(sys, "argv", argv), \
                         patch.object(comparison_runner, "list_models", return_value=catalog), \
                         patch.object(comparison_runner, "call_gemini") as generate, \
                         contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(comparison_runner.main(), 2)
                    generate.assert_not_called()
                    report = json.loads((output_dir / "gemini_model_comparison_report.json").read_text())
                    self.assertEqual(report["case_results"], [])
                    self.assertIsNone(report["reference_model_called"])
                    self.assertIsNone(report["recommended_model_called"])
                    self.assertEqual(report["resolved_models"]["gemini-3.1-pro-preview"], "models/gemini-3.1-pro-preview")

    def test_qualified_model_reports_generation_identity_not_catalog_guess(self):
        catalog = [{
            "name": "models/gemini-3.1-pro-preview",
            "supportedGenerationMethods": ["generateContent"],
        }]
        response = json.dumps({
            "protocol_version": "1", "decision_summary": "Evidence reviewed",
            "state_gaps": [], "recommended_actions": [], "caution_notes": [],
            "final_response_markdown": "Grounded response with no forbidden markers",
        })
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps({"cases": [{
                "id": "MOCK-GOOD", "forbidden_markers": ["not-in-answer"],
            }]}), encoding="utf-8")
            output_dir = root / "out"
            argv = [
                "run_gemini_model_comparison.py", "--fixtures", str(fixture),
                "--output-dir", str(output_dir),
                "--reference-model", "gemini-3.1-pro-preview",
                "--candidate-models", "", "--critical-case-ids", "",
                "--inter-request-delay-seconds", "0",
            ]
            observed_model = "models/provider-reported-identity"
            mocked_result = {
                "ok": True, "called_model": observed_model, "response_text": response,
                "attempts": [{"attempt": 1, "status_code": 200, "latency_ms": 1}],
                "usage_metadata": {},
            }
            with patch.dict(os.environ, {"DCOIR_GEMINI_API": "fake-key"}), \
                 patch.object(sys, "argv", argv), \
                 patch.object(comparison_runner, "list_models", return_value=catalog), \
                 patch.object(comparison_runner, "call_gemini", return_value=mocked_result) as generate, \
                 patch.object(comparison_runner.time, "sleep", return_value=None), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(comparison_runner.main(), 0)
            generate.assert_called_once()
            report = json.loads((output_dir / "gemini_model_comparison_report.json").read_text())
            self.assertEqual(report["reference_model_called"], observed_model)
            self.assertEqual(report["recommended_model_called"], observed_model)
            self.assertEqual(report["case_results"][0]["called_model"], observed_model)
            self.assertEqual(report["resolved_models"]["gemini-3.1-pro-preview"], catalog[0]["name"])

    def test_comparison_report_names_actual_called_model_and_flags_alias(self):
        catalog = [
            {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.5-flash-latest", "supportedGenerationMethods": ["generateContent"]},
        ]
        calls = []

        def simulated_call(api_key, args, model, prompt, *, generation_config=None):
            calls.append((model, generation_config))
            # Test a bounded failed generation: no real requests, and the
            # report must still identify the actual attempted model.
            return {
                "ok": False, "attempts": [{"attempt": 1, "status_code": 503, "latency_ms": 1.0}],
                "error": "http_503", "called_model": model,
            }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture.json"
            out = root / "reports"
            fixture.write_text(json.dumps({"cases": [{"id": "GEM-MOCK-001", "turns": []}]}), encoding="utf-8")
            argv = [
                "run_gemini_model_comparison.py", "--fixtures", str(fixture),
                "--output-dir", str(out),
                "--reference-model", "gemini-3.5-flash",
                "--candidate-models", "gemini-3.5-flash-preview",
                "--inter-request-delay-seconds", "0",
                "--critical-case-ids", "",
            ]
            with patch.dict(os.environ, {"DCOIR_GEMINI_API": "fake-key"}), \
                 patch.object(sys, "argv", argv), \
                 patch.object(comparison_runner, "list_models", return_value=catalog), \
                 patch.object(comparison_runner, "call_gemini", side_effect=simulated_call), \
                 patch.object(comparison_runner.time, "sleep", return_value=None), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = comparison_runner.main()
            self.assertEqual(status, 2)  # All modeled calls deliberately fail.
            self.assertEqual(calls, [(
                "models/gemini-3.5-flash",
                {"temperature": 0.1, "responseMimeType": "application/json"},
            )])
            report = json.loads((out / "gemini_model_comparison_report.json").read_text(encoding="utf-8"))
            self.assertEqual(
                report["reference_model_called"], "models/gemini-3.5-flash",
            )
            self.assertEqual(report["recommended_model_called"], None)
            self.assertEqual(
                report["model_resolution_warnings"],
                {"gemini-3.5-flash-preview": "similar_model_alias_not_selected"},
            )
            actual = [r for r in report["case_results"] if r["requested_model"] == "gemini-3.5-flash"]
            self.assertEqual(len(actual), 1)
            self.assertEqual(actual[0]["called_model"], "models/gemini-3.5-flash")
            rejected = [r for r in report["case_results"] if r["requested_model"].endswith("-preview")]
            self.assertEqual(len(rejected), 1)
            self.assertIsNone(rejected[0]["called_model"])
            self.assertEqual(rejected[0]["protocol_error"], "model_not_available")


if __name__ == "__main__":
    unittest.main()
