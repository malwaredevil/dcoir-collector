"""Retention cleanup planning for ChatGPT workflow reports."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from workflow_report_common import (
    OUT_ROOT,
    REPORT_ROOT,
    REQUEST_ROOT,
    iso,
    newest_report_per_workflow,
    parse_report_result,
    path_age_days,
    safe_segment,
    utc_now,
)


def make_cleanup_plan(args: argparse.Namespace) -> int:
    now = utc_now()
    root = REPORT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    reports = sorted(root.glob("**/workflow_report.md"))
    request_files = sorted(p for p in REQUEST_ROOT.glob("**/*.json") if p.is_file())
    out_dirs = sorted(p for p in OUT_ROOT.iterdir() if p.is_dir()) if OUT_ROOT.exists() else []
    current_run = safe_segment(os.environ.get("GITHUB_RUN_ID", "manual"))
    report_id = safe_segment(args.report_id or f"retention-cleanup-{current_run}")
    cleanup_dir = root / "retention-cleanup" / report_id
    cleanup_report = cleanup_dir / "workflow_report.md"
    cleanup_dir.mkdir(parents=True, exist_ok=True)

    newest_keep = newest_report_per_workflow([p for p in reports if "repo-workflows" in p.parts]) if args.keep_latest else set()
    remove: list[tuple[Path, str, float, str]] = []
    keep: list[tuple[Path, str, float, str]] = []

    for path in reports:
        if path == cleanup_report or cleanup_dir in path.parents:
            keep.append((path, "cleanup_report", 0.0, "current cleanup report"))
            continue
        if any(part == ".gitkeep" for part in path.parts):
            keep.append((path, "scaffold", 0.0, "scaffold"))
            continue
        age = path_age_days(path, now)
        if args.workflow_filter and args.workflow_filter not in str(path):
            keep.append((path, "filtered", age, "workflow_filter did not match"))
            continue
        if path in newest_keep:
            keep.append((path, parse_report_result(path), age, "latest report for workflow"))
            continue
        result = parse_report_result(path)
        threshold = args.failure_days if result == "failure" else args.cleanup_days if "cleanup" in str(path) else args.success_days
        if age >= threshold:
            remove.append((path, result, age, f"age {age:.1f}d >= {threshold}d"))
        else:
            keep.append((path, result, age, f"age {age:.1f}d < {threshold}d"))

    for path in request_files:
        age = path_age_days(path, now)
        if args.workflow_filter and args.workflow_filter not in str(path):
            keep.append((path, "request", age, "workflow_filter did not match"))
            continue
        if age >= args.request_days:
            remove.append((path, "request", age, f"age {age:.1f}d >= {args.request_days}d"))
        else:
            keep.append((path, "request", age, f"age {age:.1f}d < {args.request_days}d"))

    for path in out_dirs:
        age = path_age_days(path, now)
        if args.workflow_filter and args.workflow_filter not in str(path):
            keep.append((path, "bundle", age, "workflow_filter did not match"))
            continue
        if age >= args.bundle_days:
            remove.append((path, "bundle", age, f"age {age:.1f}d >= {args.bundle_days}d"))
        else:
            keep.append((path, "bundle", age, f"age {age:.1f}d < {args.bundle_days}d"))

    removed_file = Path(args.removed_paths_file)
    removed_file.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        removed_file.write_text("", encoding="utf-8")
    else:
        removed_file.write_text("\n".join(str(p) for p, _, _, _ in remove) + ("\n" if remove else ""), encoding="utf-8")

    lines = [
        "# ChatGPT workflow report",
        "",
        "## Result",
        "",
        "- workflow: chatgpt-report-retention-cleanup",
        "- report_scope: retention-cleanup",
        "- report_family: retention-cleanup-summary",
        "- assistant_polling_target: false",
        "- identifier_type: cleanup_run_id",
        "- do_not_use_for_live_polling: true",
        "- result: success",
        f"- mode: {'dry-run' if args.dry_run else 'delete'}",
        f"- success_retention_days: {args.success_days}",
        f"- failure_retention_days: {args.failure_days}",
        f"- cleanup_retention_days: {args.cleanup_days}",
        f"- request_retention_days: {args.request_days}",
        f"- bundle_retention_days: {args.bundle_days}",
        f"- keep_latest_per_workflow: {str(args.keep_latest).lower()}",
        f"- workflow_filter: {args.workflow_filter or ''}",
        f"- candidate_count: {len(remove)}",
        f"- retained_count: {len(keep)}",
        f"- github_run_id: {os.environ.get('GITHUB_RUN_ID', 'unknown')}",
        f"- github_sha: {os.environ.get('GITHUB_SHA', 'unknown')}",
        f"- report_created_utc: {iso(now)}",
        "",
        "## Paths selected for cleanup" if not args.dry_run else "## Paths that would be cleaned",
    ]
    if remove:
        for path, kind, age, reason in remove:
            lines.append(f"- `{path}` | kind={kind} | age_days={age:.1f} | reason={reason}")
    else:
        lines.append("- none")
    lines += ["", "## Paths retained or skipped"]
    if keep:
        for path, kind, age, reason in keep[:200]:
            lines.append(f"- `{path}` | kind={kind} | age_days={age:.1f} | reason={reason}")
        if len(keep) > 200:
            lines.append(f"- ... {len(keep) - 200} additional retained paths omitted from summary")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Next ChatGPT action",
        "",
        "Read this cleanup report, verify scoped deletion/readback when cleanup was not a dry run, then record Airtable evidence if material. Do not use retention-cleanup reports for live workflow polling.",
    ]
    cleanup_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(cleanup_report)
    return 0
