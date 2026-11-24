#!/usr/bin/env python3
"""Offline regression checks for shared replay loader and schema-message ownership."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import score_gemini_behavioral_replay as scorer
import validate_gemini_behavioral_replay_fixtures as fixture_validator
from lib.gemini_behavioral_replay_runner import (
    load_fixture_entry, load_fixture_index, repo_root_from_script,
)
from lib.gemini_behavioral_replay_schema import ValidationMessage, validate_fixture_shape


class StrictValidationMessages(list):
    """Reject lookalike dynamically constructed validation messages."""
    def append(self, message: ValidationMessage) -> None:
        if not isinstance(message, ValidationMessage):
            raise AssertionError(
                f"Expected canonical ValidationMessage, got {type(message).__name__}"
            )
        super().append(message)


class ReplayOwnerTests(unittest.TestCase):
    def test_validator_uses_shared_index_and_entry_loaders_and_preserves_errors(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            fixture_path = root / "invalid_fixture.json"
            fixture = {"fixture_id": "fixture-missing-required-fields"}
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
            fixtures_root = root / "fixtures"
            fixtures_root.mkdir()
            entry = {"fixture_id": "index-id", "path": str(fixture_path)}
            (fixtures_root / "index.json").write_text(
                json.dumps({
                    "fixture_family": "test-family",
                    "model_split": {"test": 1},
                    "fixtures": [entry],
                }), encoding="utf-8",
            )
            report_dir = root / "out"
            stdout = io.StringIO()
            with (
                patch.object(
                    fixture_validator, "load_fixture_index",
                    wraps=load_fixture_index,
                ) as shared_index,
                patch.object(
                    fixture_validator, "load_fixture_entry",
                    wraps=load_fixture_entry,
                ) as shared_entry,
                patch.object(
                    sys, "argv", [
                        "validate", "--fixtures-root", str(fixtures_root),
                        "--output-dir", str(report_dir),
                    ],
                ),
                contextlib.redirect_stdout(stdout),
            ):
                exit_code = fixture_validator.main()
            expected_messages = [
                {"level": msg.level, "message": msg.message}
                for msg in validate_fixture_shape(fixture)
            ]
            report = json.loads(
                (report_dir / "validate_gemini_behavioral_replay_fixtures_report.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(exit_code, 1)
            self.assertFalse(report["success"])
            self.assertEqual(report["fixture_family"], "test-family")
            self.assertEqual(report["model_split"], {"test": 1})
            self.assertEqual(report["fixture_count"], 1)
            self.assertEqual(report["rows"], [{
                "fixture_id": fixture["fixture_id"],
                "path": str(fixture_path),
                "messages": expected_messages,
                "success": False,
            }])
            self.assertEqual(report["errors"], [
                msg["message"] for msg in expected_messages if msg["level"] == "error"
            ])
            self.assertEqual(json.loads(stdout.getvalue()), report)
            shared_index.assert_called_once_with(fixtures_root)
            shared_entry.assert_called_once_with(
                repo_root_from_script(Path(fixture_validator.__file__)), entry
            )

    def test_score_expected_mode_rejection_uses_schema_message_class(self):
        stdout = io.StringIO()
        with (
            patch.object(scorer, "load_fixtures", return_value=[{"fixture": {}}]),
            patch.object(scorer, "load_response_pack", return_value={"mode": "deterministic"}),
            patch.object(
                scorer, "validate_response_pack_shape",
                return_value=StrictValidationMessages(),
            ),
            patch.object(sys, "argv", [
                "score", "--fixtures-root", "/ignored", "--response-pack",
                "/ignored.json", "--fixture-id", "example",
                "--expected-mode", "live_gemini",
            ]),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = scorer.main()
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), {
            "success": False,
            "validation_messages": [{
                "level": "error",
                "message": "Response pack mode 'deterministic' does not match expected mode 'live_gemini'.",
            }],
        })

    def test_score_matching_mode_keeps_success_payload(self):
        stdout = io.StringIO()
        score_result = {"success": True, "score": 1}
        with (
            patch.object(scorer, "load_fixtures", return_value=[{"fixture": {}}]),
            patch.object(scorer, "load_response_pack", return_value={"mode": "deterministic"}),
            patch.object(
                scorer, "validate_response_pack_shape",
                return_value=StrictValidationMessages(),
            ),
            patch.object(scorer, "score_response_pack", return_value=score_result),
            patch.object(sys, "argv", [
                "score", "--fixtures-root", "/ignored", "--response-pack",
                "/ignored.json", "--fixture-id", "example",
            ]),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = scorer.main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), {
            "success": True, "validation_messages": [], "result": score_result,
        })


if __name__ == "__main__":
    unittest.main()
