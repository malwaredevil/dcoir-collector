#!/usr/bin/env python3
"""Manual collector test steps for the DCOIR manual test runner."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Tuple

from dcoir_manual_runner_context import *
from dcoir_manual_runner_package import ensure_runtime_available

from dcoir_manual_runner_checks_part_01 import (
    classify_collect_note,
    find_first_glob,
    safe_read_text,
)

def cleanup_transient_framework_artifacts() -> None:
    for path in [collector_script_path(), live_zip_path()]:
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
    for path in [stage_dir(), build_dir()]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def final_signoff() -> None:
    steps = STATE["steps"]
    counts: Dict[str, int] = {}
    for payload in steps.values():
        counts[payload["status"]] = counts.get(payload["status"], 0) + 1

    failed = counts.get("FAIL", 0) + counts.get("ERROR", 0)
    partial = counts.get("PARTIAL", 0)
    if failed == 0 and partial == 0:
        verdict = "READY TO SIGN OFF"
        note = "Everything in this framework passed cleanly."
    elif failed == 0:
        verdict = "READY WITH RESERVATIONS"
        note = "Nothing hard-failed, but there are partial results that should be reviewed before final signoff."
    else:
        verdict = "NOT READY"
        note = "At least one test failed or errored. Review the report before signing off."

    append_report("\n" + "=" * 90 + "\n")
    append_report("FINAL SUMMARY")
    append_report(f"Finished: {now_text()}")
    append_report(f"Verdict: {verdict}")
    append_report(f"Note: {note}")
    append_report("Per-step results:")
    for step_id, _label in STEP_ORDER:
        payload = STATE["steps"][step_id]
        append_report(f"  - {payload['label']}: {payload['status']} :: {payload.get('note', '')}")
    update_step("final_signoff", "PASS" if failed == 0 else "PARTIAL", f"{verdict} - {note}")
    set_message(f"Framework finished. Verdict: {verdict}. Open the report at {REPORT_PATH}")


def run_collect(step_id: str, outroot: Path, targeted: bool = False) -> Tuple[str, Dict[str, str], Path]:
    if outroot.exists():
        shutil.rmtree(outroot)
    outroot.mkdir(parents=True, exist_ok=True)
    ensure_runtime_available()

    if targeted:
        cmd = powershell_cmd(
            "-File", str(collector_script_path()),
            "-Quick", "collect-targeted-popup",
            "-Target", "User reported popup around 2026-04-08T09:00Z",
            "-WindowStart", "2026-04-08T08:45:00Z",
            "-WindowEnd", "2026-04-08T09:15:00Z",
            "-OutRoot", str(outroot),
        )
        note = "Running a targeted collect in the same local style a user would."
    else:
        cmd = powershell_cmd(
            "-File", str(collector_script_path()),
            "-Quick", "collect-t1",
            "-OutRoot", str(outroot),
        )
        note = "Running a full collect in the same local style a user would."

    result = run_command(step_id, cmd, BASE_DIR, note)
    combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
    markers = parse_markers(combined)
    run_id = markers.get("RUN_ID", "")
    run_root = newest_run_root(outroot, run_id=run_id)

    if targeted:
        ok = result["exit_code"] == 0 and "COLLECTION_SCOPE_PATH" in markers and "TARGETED_COLLECTION_PLAN_PATH" in markers
        if ok:
            update_step(step_id, "PASS", classify_collect_note(markers, targeted=True))
        else:
            update_step(step_id, "FAIL", "Targeted collect did not produce the expected targeted outputs.")
            raise RuntimeError("Targeted collect test failed.")
    else:
        ok = result["exit_code"] == 0 and "COLLECT_BUNDLE_PATH" in markers and "RUN_ID" in markers and "STATUS" in markers
        if ok:
            update_step(step_id, "PASS", classify_collect_note(markers, targeted=False))
        else:
            update_step(step_id, "FAIL", "Collect did not produce the expected live-style output markers.")
            raise RuntimeError("Collect test failed.")

    return combined, markers, run_root


def run_review_surfaces(run_root: Path) -> None:
    update_step("review_surfaces", "RUNNING", "Inspecting tuned first-review collector surfaces.")
    follow_up = find_first_glob(run_root, "final_artifacts/35_ANALYST_FOLLOW_UP_QUEUE_*.txt")
    high_signal = find_first_glob(run_root, "final_artifacts/25A_EVENT_TIMELINE_TEXT_security_high_signal_summary.txt")
    overview = find_first_glob(run_root, "DCOIR_ANALYST_OVERVIEW_*.txt")
    missing = []
    if not follow_up:
        missing.append("analyst follow-up queue")
    if not high_signal:
        missing.append("security high-signal summary")
    if not overview:
        missing.append("analyst overview")
    if missing:
        update_step("review_surfaces", "FAIL", "Missing required review-surface files: " + ", ".join(missing) + ".")
        raise RuntimeError("Review-surface files missing.")

    follow_up_text = safe_read_text(follow_up)
    high_signal_text = safe_read_text(high_signal)
    overview_text = safe_read_text(overview)

    noisy_follow_up_hits = []
    if "DlpUserAgent.exe" in follow_up_text:
        noisy_follow_up_hits.append("DlpUserAgent.exe")
    if "-Quick collect-t1" in follow_up_text or "DCOIR_Collector.ps1" in follow_up_text and "collect-t1" in follow_up_text:
        noisy_follow_up_hits.append("collector self-run command")

    process_review_lines = [line for line in follow_up_text.splitlines() if "Process review candidate PID" in line]
    process_review_missing_parent = [line for line in process_review_lines if " parent=" not in line]

    noisy_task_hits = []
    for task_name in [r"\UptimeCheck", r"\UptimePopup", r"\Deploy_Sysmon_Production", r"\Cleanup Old PS Transcripts"]:
        if task_name in high_signal_text:
            noisy_task_hits.append(task_name)

    missing_overview_fields = [token for token in ["CollectTier=", "CollectorObservedErrorCount=", "RunHealth="] if token not in overview_text]

    problems = []
    if noisy_follow_up_hits:
        problems.append("follow-up queue still surfaced known benign items: " + ", ".join(noisy_follow_up_hits))
    if process_review_missing_parent:
        problems.append("process review candidates are missing parent context")
    if noisy_task_hits:
        problems.append("high-signal summary still surfaced suppressed scheduled tasks: " + ", ".join(noisy_task_hits))
    if missing_overview_fields:
        problems.append("analyst overview missing fields: " + ", ".join(missing_overview_fields))

    if problems:
        update_step("review_surfaces", "FAIL", "; ".join(problems))
        raise RuntimeError("Review-surface tuning check failed.")

    update_step("review_surfaces", "PASS", "Review surfaces reflect tuned suppression, process parent context, and overview fields.")


def run_cleanup() -> None:
    ensure_runtime_available()
    update_step("cleanup", "RUNNING", "Running cleanup after evidence has already been saved.")
    okay = True
    for label, outroot in [("non-admin", RUNS_DIR / "nonadmin"), ("admin", RUNS_DIR / "admin")]:
        cmd = powershell_cmd("-File", str(collector_script_path()), "-Quick", "cleanup", "-OutRoot", str(outroot))
        result = run_command("cleanup", cmd, BASE_DIR, f"Running cleanup for the {label} run.", allow_error=True)
        combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
        markers = parse_markers(combined)
        if markers.get("CLEANUP_STATUS") != "COMPLETE":
            okay = False
    cleanup_transient_framework_artifacts()
    if okay:
        update_step("cleanup", "PASS", "Cleanup completed after the evidence was saved, and transient staged runtime files were removed.")
    else:
        update_step("cleanup", "PARTIAL", "Cleanup ran, but at least one cleanup pass did not report COMPLETE cleanly.")
