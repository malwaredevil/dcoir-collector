from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_runner import load_fixture_entry, load_fixture_index, repo_root_from_script
from lib.gemini_behavioral_replay_utils import csv


RUNNER_MODE_TO_FIXTURE_MODE = {
    "deterministic": "deterministic",
    "live": "live_gemini",
    "fallback": "fallback_emulation",
}


def resolve_fixtures(
    args: argparse.Namespace,
    fixtures_root: Path,
    script_path: Path,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    repo_root = repo_root_from_script(script_path)
    all_active_entries = [e for e in load_fixture_index(fixtures_root).get("fixtures", []) if e.get("status") == "active"]
    required_fixture_mode = RUNNER_MODE_TO_FIXTURE_MODE.get(args.mode)
    if required_fixture_mode is None:
        raise ValueError(f"Unsupported replay runner mode: {args.mode!r}")

    mode_eligible_entries = [
        e for e in all_active_entries if required_fixture_mode in e.get("mode_support", [])
    ]
    excluded_from_mode = [
        e.get("fixture_id")
        for e in all_active_entries
        if required_fixture_mode not in e.get("mode_support", [])
    ]
    excluded_from_live_api = [
        e.get("fixture_id")
        for e in all_active_entries
        if args.mode == "live" and not e.get("live_api_eligible", True)
    ]
    if args.mode == "live":
        entries = [e for e in mode_eligible_entries if e.get("live_api_eligible", True)]
    else:
        entries = mode_eligible_entries

    active = [e.get("fixture_id") for e in entries]
    checked = csv(args.fixture_ids_csv)
    if args.fixture_ids_csv is None and not checked:
        checked = [args.fixture_id] if args.fixture_id else active
    custom = csv(args.custom_fixtures_csv)
    rejected: List[Dict[str, str]] = []

    def rejection_reason(fid: str) -> str:
        if args.mode == "live" and fid in excluded_from_live_api:
            return "not eligible for raw live Gemini API replay"
        if fid in excluded_from_mode:
            return f"does not support runner mode {args.mode!r} ({required_fixture_mode})"
        return "not in active fixture index"

    if args.run_all_active_fixtures:
        selected, source = active, "all_active_fixtures"
    elif custom:
        selected, source = [], "custom_fixtures_csv"
        for fid in custom:
            if fid in active:
                selected.append(fid)
            else:
                rejected.append({"fixture_id": fid, "reason": rejection_reason(fid)})
    elif args.mode == "deterministic" and not checked:
        selected, source = active, "deterministic_response_pack_default"
    else:
        selected, source = [], "checkbox_fixtures"
        for fid in checked:
            if fid in active:
                selected.append(fid)
            else:
                rejected.append({"fixture_id": fid, "reason": rejection_reason(fid)})

    loaded = [load_fixture_entry(repo_root, e) for e in entries if e.get("fixture_id") in set(selected)]
    return loaded, {
        "selection_source": source,
        "required_fixture_mode": required_fixture_mode,
        "active_fixtures": active,
        "selected_fixtures_to_run": selected,
        "rejected_selected_fixtures": rejected,
        "excluded_from_mode": excluded_from_mode,
        "excluded_from_live_api": excluded_from_live_api,
    }
