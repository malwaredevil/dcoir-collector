from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_runner import load_fixture_entry, load_fixture_index, repo_root_from_script
from lib.gemini_behavioral_replay_utils import csv

def resolve_fixtures(
    args: argparse.Namespace,
    fixtures_root: Path,
    script_path: Path,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    repo_root = repo_root_from_script(script_path)
    entries = [e for e in load_fixture_index(fixtures_root).get("fixtures", []) if e.get("status") == "active"]
    active = [e.get("fixture_id") for e in entries]
    checked = csv(args.fixture_ids_csv)
    if args.fixture_ids_csv is None and not checked:
        checked = [args.fixture_id] if args.fixture_id else active
    custom = csv(args.custom_fixtures_csv)
    rejected: List[Dict[str, str]] = []
    if args.run_all_active_fixtures:
        selected, source = active, "all_active_fixtures"
    elif custom:
        selected, source = [], "custom_fixtures_csv"
        for fid in custom:
            if fid in active:
                selected.append(fid)
            else:
                rejected.append({"fixture_id": fid, "reason": "not in active fixture index"})
    elif args.mode == "deterministic" and not checked:
        selected, source = active, "deterministic_response_pack_default"
    else:
        selected, source = [], "checkbox_fixtures"
        for fid in checked:
            if fid in active:
                selected.append(fid)
            else:
                rejected.append({"fixture_id": fid, "reason": "not in active fixture index"})
    loaded = [load_fixture_entry(repo_root, e) for e in entries if e.get("fixture_id") in set(selected)]
    return loaded, {"selection_source": source, "active_fixtures": active, "selected_fixtures_to_run": selected, "rejected_selected_fixtures": rejected}
