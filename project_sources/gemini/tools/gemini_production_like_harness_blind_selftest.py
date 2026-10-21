#!/usr/bin/env python3
"""Fail-closed blind-harness coverage and canonical collector fixture tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lib.gemini_production_like_harness_blind import (
    validate_blind_scenarios, validate_collector_fixtures,
)


class BlindHarnessOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.fixtures = self.root / "fixtures"
        self.blind = self.fixtures / "blind"
        self.blind.mkdir(parents=True)

    def put_json(self, path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def scenario(self, name: str, **changes: object) -> dict[str, str]:
        data: dict[str, object] = {
            "id": name, "owner": name + "_owner", "family": name + "_family",
            "tier": "medium", "visible": {"turn": "Sanitized evidence only."},
            "hidden": {"expected_verdict": "needs_more_evidence"},
            "artifact_expectations": {"must_find": [], "must_not_find": []},
        }
        data.update(changes)
        path = "scenarios/" + name + "/scenario.json"
        self.put_json(self.blind / path, data)
        return {"id": name, "path": path}

    def blind_report(self, index: dict) -> tuple[dict, list[dict]]:
        self.put_json(self.blind / "index.json", index)
        messages: list[dict] = []
        result = validate_blind_scenarios(
            self.root, self.fixtures, self.root / "out",
            messages, require_stored_artifacts=False,
        )
        return result, messages

    def test_legacy_matrix_without_real_scenario_does_not_claim_coverage(self) -> None:
        valid = self.scenario("good")
        report, messages = self.blind_report({
            "matrix": [["ghost", "legacy_owner", "phantom_coverage"]],
            "scenarios": [valid],
        })
        self.assertFalse([m for m in messages if m["level"] == "error"], messages)
        self.assertEqual(report["legacy_matrix_count"], 1)
        self.assertEqual(report["scenario_count"], 1)
        self.assertEqual(report["coverage_tags"], [
            "good_family", "good_owner", "medium",
        ])
        self.assertEqual(len(report["prompts"]), 1)

    def test_scenario_missing_required_fields_does_not_claim_coverage(self) -> None:
        valid = self.scenario("good")
        invalid = self.scenario("broken", hidden={})
        # A required field must be absent, not merely empty.
        invalid_path = self.blind / invalid["path"]
        payload = json.loads(invalid_path.read_text(encoding="utf-8"))
        del payload["hidden"]
        self.put_json(invalid_path, payload)
        report, messages = self.blind_report({"scenarios": [valid, invalid]})
        self.assertTrue(any("broken missing required field hidden" in m["message"] for m in messages))
        self.assertEqual(report["coverage_tags"], [
            "good_family", "good_owner", "medium",
        ])
        # Keep legacy report row counts intact; only coverage truthfulness changes.
        self.assertEqual(report["scenario_count"], 2)
        self.assertEqual(len(report["prompts"]), 2)

    def test_prompt_leak_or_signal_failure_does_not_claim_coverage(self) -> None:
        leaked = self.scenario(
            "leaked", visible={"turn": "NEVER_EXPOSE_KEYWORD"},
            artifact_expectations={
                "must_find": [], "must_not_find": ["NEVER_EXPOSE_KEYWORD"],
            },
        )
        report, messages = self.blind_report({
            "redaction_prohibited_terms": ["never_expose_keyword"],
            "scenarios": [leaked],
        })
        self.assertGreaterEqual(len([m for m in messages if m["level"] == "error"]), 2)
        self.assertEqual(report["coverage_tags"], [])
        self.assertEqual(report["scenario_count"], 1)

    def test_blank_required_scenario_identity_does_not_create_coverage(self) -> None:
        for field in ("id", "owner", "family"):
            with self.subTest(field=field):
                entry = self.scenario("invalid_" + field, **{field: " "})
                report, messages = self.blind_report({"scenarios": [entry]})
                self.assertTrue(
                    any("invalid required field " + field in m["message"] for m in messages),
                    messages,
                )
                self.assertEqual(report["coverage_tags"], [])

    def test_prior_invalid_scenario_does_not_mask_later_valid_tags(self) -> None:
        broken = self.scenario("broken", owner="ghost_owner")
        path = self.blind / broken["path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["hidden"]
        self.put_json(path, payload)
        valid = self.scenario("good")
        report, messages = self.blind_report({"scenarios": [broken, valid]})
        self.assertTrue(any(m["level"] == "error" for m in messages))
        self.assertEqual(report["coverage_tags"], [
            "good_family", "good_owner", "medium",
        ])

    def test_missing_listed_scenario_fails_without_inventing_coverage(self) -> None:
        report, messages = self.blind_report({
            "scenarios": [{"id": "absent", "path": "scenarios/absent/scenario.json",
                           "owner": "ghost", "family": "ghost", "tier": "full"}],
        })
        self.assertTrue(any("listed scenario is missing: absent" in m["message"] for m in messages))
        self.assertEqual(report["coverage_tags"], [])
        self.assertEqual(report["scenario_count"], 0)

    def collector_report(self, fixtures: list[dict]) -> tuple[dict, list[dict]]:
        index = self.root / "project_sources/collector/fixtures/blind/index.json"
        self.put_json(index, {"fixtures": fixtures})
        messages: list[dict] = []
        return validate_collector_fixtures(self.root, messages), messages

    def test_legacy_only_collector_manifest_and_fixture_id_are_rejected(self) -> None:
        self.put_json(self.root / "fixtures/existing.json", {
            "artifacts": ["present"], "derived_scenarios": ["one"],
        })
        report, messages = self.collector_report([{
            "fixture_id": "obsolete", "manifest_path": "fixtures/existing.json",
        }])
        self.assertEqual(report["fixture_count"], 1)
        self.assertEqual(report["manifests"], [])
        self.assertTrue(any("collector fixture missing required id" in m["message"] for m in messages))
        self.assertTrue(any("collector fixture missing required manifest" in m["message"] for m in messages))

    def test_empty_canonical_collector_id_and_manifest_fail_closed(self) -> None:
        report, messages = self.collector_report([{"id": "", "manifest": ""}])
        self.assertEqual(report["manifests"], [])
        self.assertTrue(any("collector fixture missing required id" in m["message"] for m in messages))
        self.assertTrue(any("collector fixture missing required manifest" in m["message"] for m in messages))

    def test_canonical_collector_fields_keep_report_output(self) -> None:
        manifest = "fixtures/actual.json"
        self.put_json(self.root / manifest, {
            "artifacts": ["a", "b"], "derived_scenarios": ["real"],
        })
        report, messages = self.collector_report([{
            "id": "valid", "manifest": manifest,
            "fixture_id": "legacy_ignored", "manifest_path": "missing-legacy.json",
        }])
        self.assertFalse([m for m in messages if m["level"] == "error"], messages)
        self.assertEqual(report, {
            "present": True, "fixture_count": 1,
            "manifests": [{
                "fixture_id": "valid", "manifest_path": manifest,
                "artifact_count": 2, "derived_scenarios": ["real"],
            }],
        })


if __name__ == "__main__":
    unittest.main()
