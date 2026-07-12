"""Completed workflow_run report generation."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from workflow_report_common import (
    REPORT_ROOT,
    bounded_lines,
    iso,
    read_json,
    read_text_if_present,
    safe_segment,
    utc_now,
)


def make_workflow_report(args: argparse.Namespace) -> int:
    event_path = Path(args.event_json or os.environ.get("GITHUB_EVENT_PATH", ""))
    if not event_path.is_file():
        raise SystemExit(f"Missing GitHub event JSON: {event_path}")

    event = read_json(event_path)
    run = event.get("workflow_run") or {}
    workflow_name = run.get("name") or args.workflow_name or "unknown-workflow"
    workflow_safe = safe_segment(workflow_name)
    run_id = str(run.get("id") or args.run_id or os.environ.get("GITHUB_RUN_ID", "unknown-run"))
    run_safe = safe_segment(run_id)
    conclusion = str(run.get("conclusion") or "unknown")
    event_name = str(run.get("event") or "unknown")
    head_branch = str(run.get("head_branch") or "")
    head_sha = str(run.get("head_sha") or "")
    html_url = str(run.get("html_url") or "")
    run_attempt = str(run.get("run_attempt") or "")
    run_number = str(run.get("run_number") or "")
    created_at = str(run.get("created_at") or "")
    updated_at = str(run.get("updated_at") or "")
    actor = ((run.get("actor") or {}).get("login") or "unknown") if isinstance(run.get("actor"), dict) else "unknown"
    repository = ((run.get("repository") or {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY", "unknown")) if isinstance(run.get("repository"), dict) else os.environ.get("GITHUB_REPOSITORY", "unknown")

    out_dir = REPORT_ROOT / "repo-workflows" / workflow_safe / run_safe
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "workflow_report.md"

    failure_conclusions = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}
    result = "success" if conclusion == "success" else "failure" if conclusion in failure_conclusions else conclusion
    if result == "success":
        action_hint = "No repair needed; review changed paths/artifacts if this workflow protects a code, docs, packaging, or operational surface. Do not use this completed-run summary for live polling; active ChatGPT-staged jobs must be monitored through their live-heartbeat request_id report."
    elif result == "skipped":
        action_hint = "No repair is implied by a skipped conclusion. Confirm the skip condition matches the workflow's trigger or guard, then continue with the next applicable validation signal. Do not use this completed-run summary for live polling; active ChatGPT-staged jobs must be monitored through their live-heartbeat request_id report."
    else:
        action_hint = "Use the embedded bounded log excerpt first. If it is not enough, open workflow_run_url for full GitHub Actions logs/artifacts before asking the operator for screenshots or pasted logs. Do not use this completed-run summary for live polling; active ChatGPT-staged jobs must be monitored through their live-heartbeat request_id report."

    log_file = Path(args.log_file) if args.log_file else None
    log_error_file = Path(args.log_error_file) if args.log_error_file else None
    log_text = read_text_if_present(log_file, limit_chars=args.max_log_chars * 2)
    log_fetch_error = read_text_if_present(log_error_file, limit_chars=12000)
    log_excerpt = bounded_lines(log_text, args.max_log_lines, args.max_log_chars)

    lines = [
        "# ChatGPT workflow report",
        "",
        "## Result",
        "",
        f"- workflow: {workflow_name}",
        "- report_scope: repo-workflows",
        "- report_family: completed-run-summary",
        "- assistant_polling_target: false",
        "- identifier_type: github_run_id",
        "- do_not_use_for_live_polling: true",
        "- live_heartbeat_report_scope: progressive-in-session",
        f"- result: {result}",
        f"- conclusion: {conclusion}",
        f"- source_event: {event_name}",
        f"- workflow_run_id: {run_id}",
        f"- workflow_run_number: {run_number}",
        f"- workflow_run_attempt: {run_attempt}",
        f"- workflow_run_url: {html_url}",
        f"- repository: {repository}",
        f"- head_branch: {head_branch}",
        f"- head_sha: {head_sha}",
        f"- actor: {actor}",
        f"- source_created_at: {created_at}",
        f"- source_updated_at: {updated_at}",
        f"- reporter_run_id: {os.environ.get('GITHUB_RUN_ID', 'unknown')}",
        f"- reporter_sha: {os.environ.get('GITHUB_SHA', 'unknown')}",
        f"- report_created_utc: {iso(utc_now())}",
        "",
        "## Report routing",
        "",
        "This is a completed workflow_run summary under repo-workflows. Use it after a workflow has completed, especially for bounded failure-log excerpts. For active ChatGPT-staged jobs, poll the live-heartbeat report path by request_id instead.",
        "",
        "## Troubleshooting context",
        "",
        "This report was generated by the central ChatGPT workflow-run reporter after the source workflow completed.",
    ]
    if result == "skipped":
        lines.append("The source workflow was skipped. This report does not embed a failure log excerpt because a skipped conclusion is not a failure by itself.")
    elif result != "success":
        lines += [
            "The report includes bounded log context when GitHub log retrieval succeeded. Use the workflow_run_url for full logs/artifacts when deeper detail is required.",
            "",
            "### Bounded source workflow log excerpt",
            "",
        ]
        if log_excerpt:
            lines.append("```text")
            lines.extend(log_excerpt)
            lines.append("```")
        else:
            lines.append("No source workflow log excerpt was available to embed.")
        if log_fetch_error:
            lines += [
                "",
                "### Log retrieval notes",
                "",
                "```text",
                *bounded_lines(log_fetch_error, 80, 12000),
                "```",
            ]
    else:
        lines.append("The source workflow completed successfully; no failure log excerpt is embedded by default.")
    lines += [
        "",
        "## Next ChatGPT action",
        "",
        action_hint,
        "",
        "## Cleanup guidance",
        "",
        "This report is managed by chatgpt-report-retention-cleanup. Success reports, stale staged requests, and aged staged output bundles normally expire by policy.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_path)
    return 0
