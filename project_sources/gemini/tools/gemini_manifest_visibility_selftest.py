#!/usr/bin/env python3
"""Offline regression tests for the canonical Gemini manifest and scenario checks."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import gemini_behavior_scenario_validation as scenario_validation
from lib import gemini_bundle_validation_common as common
from lib import gemini_bundle_validation_runtime as runtime
from lib import gemini_production_like_harness_construct as harness
from lib.gemini_behavior_scenario_catalog import SCENARIOS

PROMOTED_REQUIREMENTS = {
    "GeminiCollectorArtifactInterpretation": ("targeted collection",),
    "GeminiIOCEnrichmentTrigger": ("provenance",),
    "GeminiOutputContractConsistency": (
        "starter prompt 1", "starter prompt 2", "starter prompt 3",
    ),
}


class GeminiManifestVisibilityTests(unittest.TestCase):
    def test_single_helper_owner(self):
        self.assertIs(scenario_validation.load_manifest, common.load_manifest)
        self.assertIs(scenario_validation.gather_text, common.gather_text)
        self.assertIs(harness.load_manifest, common.load_manifest)
        self.assertEqual(harness.MANIFEST_NAME, common.MANIFEST_NAME)
        self.assertFalse(hasattr(common, "VISIBILITY_CHECKS"))
        self.assertFalse(hasattr(runtime, "validate_visibility_markers"))

    def test_required_marker_ownership(self):
        for name, markers in PROMOTED_REQUIREMENTS.items():
            with self.subTest(scenario=name):
                self.assertIn(name, SCENARIOS)
                config = SCENARIOS[name]
                for marker in markers:
                    self.assertIn(marker, config["all_markers"])

    def test_actual_scenario_runner_fails_if_any_required_marker_is_missing(self):
        for name, markers in PROMOTED_REQUIREMENTS.items():
            config = SCENARIOS[name]
            required = list(config["all_markers"])
            # First marker of each OR group is a positive control.
            required += [group[0] for group in config["any_marker_groups"]]
            intact = "\n".join(required)
            self.assertTrue(scenario_validation.evaluate_scenario(intact, config)["success"])
            for missing in markers:
                with self.subTest(scenario=name, absent=missing):
                    altered = intact.replace(missing, "<omitted>")
                    self.assertNotEqual(altered, intact)
                    self.assertFalse(
                        scenario_validation.evaluate_scenario(altered, config)["success"]
                    )
                    with tempfile.TemporaryDirectory() as directory:
                        source = Path(directory) / "project_sources/gemini/bundle_source"
                        source.mkdir(parents=True)
                        manifest = {"bundle_name": "fixture", "bundle_version": "0", "topology": {}}
                        (source / common.MANIFEST_NAME).write_text(
                            json.dumps(manifest), encoding="utf-8"
                        )
                        quick = source / common.QUICK_START
                        quick.parent.mkdir(parents=True)
                        for content, expected_code in ((intact, 0), (altered, 1)):
                            quick.write_text(content, encoding="utf-8")
                            with patch.object(scenario_validation, "SCENARIOS", {name: config}):
                                with contextlib.redirect_stdout(io.StringIO()):
                                    rc = scenario_validation.validate_behavior_scenarios(
                                        source, Path(directory) / "report"
                                    )
                            self.assertEqual(rc, expected_code)
                            report = json.loads(
                                (Path(directory) / "report" /
                                 "validate_dcoir_gemini_behavior_scenarios_report.json")
                                .read_text(encoding="utf-8")
                            )
                            self.assertEqual(report["success"], expected_code == 0)
                            if expected_code:
                                self.assertIn(
                                    missing,
                                    report["scenario_results"][name]["missing_all_markers"],
                                )
                                self.assertIn(name, report["errors"][0])

    def test_or_groups_remain_alternatives_not_all_required(self):
        config = SCENARIOS["GeminiOutputContractConsistency"]
        text = "\n".join(config["all_markers"] + ["analyst"])
        self.assertTrue(scenario_validation.evaluate_scenario(text, config)["success"])
        text = "\n".join(config["all_markers"])
        self.assertFalse(scenario_validation.evaluate_scenario(text, config)["success"])


if __name__ == "__main__":
    unittest.main()
