#!/usr/bin/env python3
"""Top-level orchestration for the DCOIR manual test runner."""
from __future__ import annotations

import ctypes
import sys
import traceback

from dcoir_manual_runner_checks import (
    compare_admin_nonadmin,
    final_signoff,
    record_t2_pathway_note,
    recheck_package,
    run_cleanup,
    run_collect,
    run_enrich_lifecycle,
    run_full_regression,
    run_help_tests,
    run_negative_cases,
    run_review_surfaces,
    run_validator,
)
from dcoir_manual_runner_context import *
from dcoir_manual_runner_package import build_package, ensure_repo, ensure_runtime_available, restore_and_stage_runtime, validate_package

def launch_admin_phase() -> None:
    update_step("admin_launch", "LAUNCHING", "Opening the admin phase in a new elevated PowerShell window.")
    save_state()
    launcher = BASE_DIR / "run_dcoir_manual_tests.ps1"
    file_exists_or_raise(launcher, "run_dcoir_manual_tests.ps1")
    args = (
        f'-NoProfile -ExecutionPolicy Bypass -File "{launcher}" '
        f'-AdminPhase -StatePath "{STATE_PATH}" -BootstrapStatusPath "{BOOTSTRAP_STATUS_PATH}"'
    )
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, str(BASE_DIR), 1)
    if int(rc) <= 32:
        update_step("admin_launch", "FAIL", "UAC elevation did not start. Accept the admin prompt or rerun the launcher as Administrator.")
        raise RuntimeError("Could not start the admin phase. Accept the UAC prompt or rerun the launcher as Administrator.")
    update_step("admin_launch", "PASS", "Admin phase is now running.")
    append_report(f"Admin phase launched at {now_text()}\n")
    set_message("Admin phase launched. The elevated window should continue this same session with the same dashboard style.")
    sys.exit(0)


def top_level_failure(exc: Exception) -> None:
    append_report("\n" + "=" * 90 + "\n")
    append_report("FRAMEWORK FATAL ERROR")
    append_report(f"Timestamp: {now_text()}")
    append_report(str(exc))
    append_report(traceback.format_exc())
    access_denied = "denied" in str(exc).lower() or "access is denied" in str(exc).lower()
    if access_denied:
        set_message(
            "Execution failed because a file or folder was locked or denied. Close any leftover PowerShell or Python windows, let antivirus finish, then rerun the launcher."
        )
    else:
        set_message(
            "Execution failed. Read the report file for the full command output and traceback. If this happened during repo access, authenticate Git and rerun. If it happened right after an install, close this window, open a new PowerShell window, and rerun the launcher."
        )
    cleanup_transient_framework_artifacts()


def main() -> int:
    ensure_dirs()
    STATE.setdefault("context", {})["framework_started_at"] = STATE.get("context", {}).get("framework_started_at", now_text())
    init_report()
    render_dashboard("Framework loaded. Preparing to run.")
    save_state()

    try:
        sync_bootstrap_into_state(STATE)
        save_state()
        if ARGS.admin_phase:
            update_step("admin_launch", "PASS", "Admin phase is now running.")

        ensure_repo()
        validate_package()
        build_package()
        restore_and_stage_runtime()
        run_help_tests()

        if not ARGS.admin_phase:
            nonadmin_out = RUNS_DIR / "nonadmin"
            nonadmin_collect_output, nonadmin_collect_markers, nonadmin_run_root = run_collect("nonadmin_collect", nonadmin_out, targeted=False)
            STATE["context"]["nonadmin_collect_output"] = nonadmin_collect_output
            STATE["context"]["nonadmin_collect_markers"] = nonadmin_collect_markers
            STATE["context"]["nonadmin_run_root"] = str(nonadmin_run_root)
            save_state()

            nonadmin_validator_output, nonadmin_validator_rc = run_validator("nonadmin_validate", nonadmin_run_root)
            STATE["context"]["nonadmin_validator_output"] = nonadmin_validator_output
            STATE["context"]["nonadmin_validator_rc"] = nonadmin_validator_rc
            save_state()

            run_review_surfaces(nonadmin_run_root)

            targeted_out = RUNS_DIR / "nonadmin_targeted"
            targeted_output, targeted_markers, targeted_run_root = run_collect("nonadmin_targeted", targeted_out, targeted=True)
            STATE["context"]["nonadmin_targeted_output"] = targeted_output
            STATE["context"]["nonadmin_targeted_markers"] = targeted_markers
            STATE["context"]["nonadmin_targeted_run_root"] = str(targeted_run_root)
            save_state()

            enrich_results = run_enrich_lifecycle("nonadmin_enrich", nonadmin_out)
            STATE["context"]["nonadmin_enrich_results"] = enrich_results
            save_state()

            run_negative_cases("nonadmin_negative", RUNS_DIR / "nonadmin_negative")
            launch_admin_phase()
            return 0

        admin_out = RUNS_DIR / "admin"
        ensure_runtime_available()
        admin_collect_output, admin_collect_markers, admin_run_root = run_collect("admin_collect", admin_out, targeted=False)
        STATE["context"]["admin_collect_output"] = admin_collect_output
        STATE["context"]["admin_collect_markers"] = admin_collect_markers
        STATE["context"]["admin_run_root"] = str(admin_run_root)
        save_state()

        admin_validator_output, admin_validator_rc = run_validator("admin_validate", admin_run_root)
        STATE["context"]["admin_validator_output"] = admin_validator_output
        STATE["context"]["admin_validator_rc"] = admin_validator_rc
        save_state()

        compare_admin_nonadmin()
        record_t2_pathway_note()
        run_full_regression()
        recheck_package()
        run_cleanup()
        final_signoff()
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        for step_id, _label in STEP_ORDER:
            if STATE["steps"][step_id]["status"] == "RUNNING":
                update_step(step_id, "ERROR", str(exc))
                break
        top_level_failure(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
