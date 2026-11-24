#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from lib.gemini_behavioral_replay_runner import (
    load_fixture_entry,
    load_fixture_index,
    repo_root_from_script,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    fixtures_root = Path(args.fixtures_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_root = repo_root_from_script(Path(__file__))

    index_payload = load_fixture_index(fixtures_root)
    fixture_entries = index_payload.get("fixtures", [])

    report_rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    for entry in fixture_entries:
        loaded = load_fixture_entry(repo_root, entry)
        fixture_path = loaded["fixture_path"]
        fixture_payload = loaded["fixture"]
        messages = loaded["validation_messages"]
        report_rows.append(
            {
                "fixture_id": fixture_payload.get("fixture_id", entry.get("fixture_id")),
                "path": str(fixture_path),
                "messages": [
                    {"level": message.level, "message": message.message}
                    for message in messages
                ],
                "success": not any(message.level == "error" for message in messages),
            }
        )
        for message in messages:
            if message.level == "error":
                errors.append(message.message)

    report = {
        "success": len(errors) == 0,
        "fixture_family": index_payload.get("fixture_family"),
        "fixture_count": len(fixture_entries),
        "model_split": index_payload.get("model_split", {}),
        "rows": report_rows,
        "errors": errors,
    }

    report_path = output_dir / "validate_gemini_behavioral_replay_fixtures_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
