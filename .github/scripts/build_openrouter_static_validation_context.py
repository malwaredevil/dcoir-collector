#!/usr/bin/env python3
"""Build bounded static validation context for the OpenRouter PR review workflow."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from openrouter_static_context_common import safe_extract
from openrouter_static_context_reports import build_report


def export_env(report_path: Path, github_env: Path) -> None:
    if not report_path.is_file():
        raise SystemExit("static validation context file disappeared before env export")
    run_id = os.getenv("RUN_ID", "")
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        run_id = "invalid-metadata"
    run_conclusion = os.getenv("RUN_CONCLUSION", "")
    if not re.fullmatch(r"[a-z_]{1,32}", run_conclusion):
        run_conclusion = "invalid-metadata"
    with github_env.open("a", encoding="utf-8") as env_file:
        env_file.write(f"REVIEW_ASSIST_CONTEXT_PATH={report_path.as_posix()}\n")
    print(
        "Static validation context loaded from validate-on-pr run "
        f"{run_id} ({run_conclusion}), {report_path.stat().st_size} bytes."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--context-root", required=True)
    parser.add_argument("--changed-files", required=True)
    parser.add_argument("--github-env", default="")
    args = parser.parse_args()

    context_root = Path(args.context_root)
    report_path = context_root / "project_sources/collector/powershell_review_assist_workflow_report.md"
    safe_extract(Path(args.artifact_zip), context_root)
    reports_loaded = build_report(context_root, Path(args.changed_files), report_path)
    if not reports_loaded:
        return 0
    print("static-validation-context-reports: " + ", ".join(reports_loaded))
    if args.github_env:
        export_env(report_path, Path(args.github_env))
    elif report_path.is_file():
        print(f"Static validation context generated at {report_path.as_posix()}")
    else:
        print("No static validation context file generated; no context injection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
