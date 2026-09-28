from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from . import gemini_behavioral_replay_selection as replay_selection
from .gemini_behavioral_replay_schema import validate_fixture_shape

TARGET_FIXTURE = "dcoir_agent_designer_visible_writer_issue_398"


def _selection_args() -> argparse.Namespace:
    return argparse.Namespace(
        mode="deterministic",
        fixture_ids_csv=None,
        fixture_id=None,
        custom_fixtures_csv=TARGET_FIXTURE,
        run_all_active_fixtures=False,
    )


def run_fixture_schema_precision_selftest() -> None:
    fixtures_root = Path("project_sources/gemini/fixtures/behavioral_replay")
    script_path = Path("project_sources/gemini/tools/run_gemini_behavioral_replay.py").resolve()
    original_load = replay_selection.load_fixture_entry
    malformed_values = (None, "handoff", [" "], [1], {"handoff": True})

    for malformed in malformed_values:
        def malformed_loader(repo_root, entry, malformed=malformed):
            row = original_load(repo_root, entry)
            if entry.get("fixture_id") != TARGET_FIXTURE:
                return row
            fixture = deepcopy(row["fixture"])
            fixture["literal_forbidden_markers"] = malformed
            return {
                **row,
                "fixture": fixture,
                "validation_messages": validate_fixture_shape(fixture),
            }

        with patch.object(replay_selection, "load_fixture_entry", side_effect=malformed_loader):
            selected, metadata = replay_selection.resolve_fixtures(
                _selection_args(), fixtures_root, script_path
            )

        if selected:
            raise SystemExit(
                "Malformed fixture-level literal_forbidden_markers reached replay selection: "
                + repr(malformed)
            )
        rejected = metadata.get("rejected_selected_fixtures") or []
        matching = [
            row for row in rejected
            if row.get("fixture_id") == TARGET_FIXTURE
            and "literal_forbidden_markers" in str(row.get("reason", ""))
        ]
        if len(matching) != 1:
            raise SystemExit(
                "Malformed fixture-level literal_forbidden_markers was not rejected by schema selection: "
                + repr({"value": malformed, "rejected": rejected})
            )
