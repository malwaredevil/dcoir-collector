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
            "gemini-3.1-flash-lite",
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
