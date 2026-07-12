#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.gemini_production_like_harness_blind import (
    validate_blind_scenarios,
    validate_collector_fixtures,
)
from lib.gemini_production_like_harness_common import validate_gitignore
from lib.gemini_production_like_harness_construct import validate_construct
from lib.gemini_production_like_harness_reports import build_summary, write_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--fixtures-root", default="project_sources/gemini/fixtures/behavioral_replay")
    parser.add_argument("--output-dir", default="project_sources/validation/out_gemini_production_like_harness")
    parser.add_argument("--mode", choices=["light", "medium", "full"], default="light")
    parser.add_argument("--require-stored-artifacts", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    messages: list[dict[str, str]] = []

    gitignore_report = validate_gitignore(root, messages)
    blind_report = validate_blind_scenarios(
        root,
        (root / args.fixtures_root).resolve(),
        output_dir,
        messages,
        args.require_stored_artifacts,
    )
    collector_report = validate_collector_fixtures(root, messages)
    construct_report = validate_construct(root, output_dir, messages, args.mode)
    summary = build_summary(messages, blind_report, collector_report, args.mode)

    report = {
        "summary": summary,
        "messages": messages,
        "gitignore": gitignore_report,
        "construct": construct_report,
        "blind_scenarios": blind_report,
        "collector_fixtures": collector_report,
    }
    write_reports(output_dir, report)
    print(json.dumps(summary, indent=2))
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
