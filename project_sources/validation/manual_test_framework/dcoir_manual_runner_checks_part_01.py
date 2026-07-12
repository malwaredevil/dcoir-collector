#!/usr/bin/env python3
"""Manual collector test steps for the DCOIR manual test runner."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

from dcoir_manual_runner_context import *
from dcoir_manual_runner_package import ensure_runtime_available, validate_package


def run_help_tests() -> None:
    ensure_runtime_available()
    cmd = powershell_cmd("-File", str(collector_script_path()), "-Help")
    result = run_command("help_top", cmd, BASE_DIR, "Running top-level help.")
    combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
    if test_output_has_all(combined, ["DCOIR Collector Help", "Quick usage:"]):
        update_step("help_top", "PASS", "Top-level help printed successfully.")
    else:
        update_step("help_top", "FAIL", "Top-level help did not print the expected help text.")
        raise RuntimeError("Top-level help test failed.")

    cmd = powershell_cmd("-File", str(collector_script_path()), "-Quick", "help")
    result = run_command("help_quick", cmd, BASE_DIR, "Running quick help.", allow_error=True)
    combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
    if result["exit_code"] == 0 and test_output_has_all(combined, ["Quick command examples:", "collect-t1"]):
        update_step("help_quick", "PASS", "Quick help printed the expected examples and returned cleanly.")
    else:
        update_step("help_quick", "FAIL", "Quick help did not print the expected examples cleanly.")
        raise RuntimeError("Quick help test failed.")

    cmd = powershell_cmd("-File", str(collector_script_path()), "-Quick", "help-collect")
    result = run_command("help_contextual", cmd, BASE_DIR, "Running contextual collect help.", allow_error=True)
    combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
    if result["exit_code"] == 0 and test_output_has_all(combined, ["DCOIR Collector Contextual Help - Collect", "collect-t1"]):
        update_step("help_contextual", "PASS", "Contextual help printed collect-specific guidance and returned cleanly.")
    else:
        update_step("help_contextual", "FAIL", "Contextual help did not print the expected collect-specific guidance.")
        raise RuntimeError("Contextual help test failed.")

    cmd = powershell_cmd("-File", str(collector_script_path()), "-Quick", "bad-value")
    result = run_command("bad_quick", cmd, BASE_DIR, "Running a bad quick command to test the help fallback.", allow_error=True)
    combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
    if result["exit_code"] != 0 and test_output_has_all(combined, ["Unknown -Quick value", "DCOIR Collector Help"]):
        update_step("bad_quick", "PASS", "Bad quick command failed clearly and showed help text.")
    else:
        update_step("bad_quick", "FAIL", "Bad quick command did not fail in a clear helpful way.")
        raise RuntimeError("Bad quick fallback test failed.")


def classify_collect_note(markers: Dict[str, str], targeted: bool = False) -> str:
    expected_nonadmin = markers.get("AUDIT_POLICY_ACCESS_STATUS") == "PRIVILEGE_REQUIRED_NON_ELEVATED"
    if markers.get("STATUS") == "PARTIAL_SUCCESS" and expected_nonadmin:
        return (
            "Targeted collect produced the expected targeted output files and expected non-elevated limitations were recorded honestly."
            if targeted
            else "Collect completed and produced the expected live-style output markers; expected non-elevated limitations were recorded honestly."
        )
    return (
        "Targeted collect produced the expected targeted output files."
        if targeted
        else "Collect completed and produced the expected live-style output markers."
    )


def run_validator(step_id: str, run_root: Path) -> Tuple[str, int]:
    cmd = powershell_cmd("-File", str(validate_script()), "-RunRoot", str(run_root))
    result = run_command(step_id, cmd, repo_root(), "Running the standalone validator against the collected run.", allow_error=True)
    combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
    if result["exit_code"] == 0:
        update_step(step_id, "PASS", "Validator passed.")
    else:
        update_step(step_id, "FAIL", "Validator failed. Open the report file to see the exact failing checks.")
    return combined, int(result["exit_code"] or 0)


def run_enrich_lifecycle(step_id: str, outroot: Path) -> Dict[str, Dict[str, str]]:
    ensure_runtime_available()
    results: Dict[str, Dict[str, str]] = {}
    commands = [
        ("start", powershell_cmd("-File", str(collector_script_path()), "-Quick", "enrich-start-tcp", "-OutRoot", str(outroot))),
        ("add", powershell_cmd("-File", str(collector_script_path()), "-Quick", "enrich-add-logtext", "-Target", "Security", "-OutRoot", str(outroot))),
        ("finalize", powershell_cmd("-File", str(collector_script_path()), "-Quick", "enrich-finalize", "-OutRoot", str(outroot))),
    ]
    update_step(step_id, "RUNNING", "Running the enrich lifecycle with live-style commands.")
    session_id = None
    okay = True
    for subname, cmd in commands:
        result = run_command(step_id, cmd, BASE_DIR, f"Running enrich lifecycle step: {subname}.", allow_error=True)
        combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
        markers = parse_markers(combined)
        results[subname] = markers
        if subname in ("start", "add"):
            if "ENRICH_SESSION_ID" not in markers:
                okay = False
            elif session_id is None:
                session_id = markers["ENRICH_SESSION_ID"]
            elif markers["ENRICH_SESSION_ID"] != session_id:
                okay = False
        if subname == "finalize" and "ENRICH_BUNDLE_PATH" not in markers:
            okay = False

    if okay:
        update_step(step_id, "PASS", "Enrich start, add, and finalize behaved correctly.")
    else:
        update_step(step_id, "FAIL", "Enrich lifecycle did not behave as expected.")
        raise RuntimeError("Enrich lifecycle test failed.")
    return results


def find_first_glob(root: Path, pattern: str) -> Optional[Path]:
    matches = sorted(root.glob(pattern))
    return matches[0] if matches else None


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def record_t2_pathway_note() -> None:
    note = (
        "Framework recorded the bounded follow-on only. Use Airtable test case COL-T2-PATH-001 to compare T2-first, T2-after-T1, and any other bounded live pathway scenarios outside this automated framework."
    )
    append_report("\n" + "=" * 90 + "\n")
    append_report("T2 PATHWAY FOLLOW-ON NOTE")
    append_report(note)
    update_step("t2_pathway_note", "ACTION", note)


def run_negative_cases(step_id: str, outroot: Path) -> None:
    ensure_runtime_available()
    cases = [
        ("invalid_quick", powershell_cmd("-File", str(collector_script_path()), "-Quick", "unknown-value", "-OutRoot", str(outroot)), ["Unknown -Quick value", "DCOIR Collector Help"], True),
        ("missing_target", powershell_cmd("-File", str(collector_script_path()), "-Quick", "enrich-start-sigcheck", "-OutRoot", str(outroot)), ["requires -Target <path>"], True),
        ("bad_pid", powershell_cmd("-File", str(collector_script_path()), "-Quick", "enrich-start-listdlls", "-Target", "abc", "-OutRoot", str(outroot)), ["requires a numeric -Target <pid>"], True),
        ("bad_window", powershell_cmd("-File", str(collector_script_path()), "-Quick", "collect-targeted-popup", "-Target", "User reported popup", "-WindowStart", "not-a-date", "-WindowEnd", "2026-04-08T09:15:00Z", "-OutRoot", str(outroot)), ["Invalid WindowStart value"], False),
    ]
    update_step(step_id, "RUNNING", "Running bad-input tests.")
    pass_count = 0
    partial_count = 0
    for name, cmd, tokens, must_fail in cases:
        result = run_command(step_id, cmd, BASE_DIR, f"Running negative test: {name}.", allow_error=True)
        combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
        has_tokens = test_output_has_all(combined, tokens)
        if must_fail:
            if result["exit_code"] != 0 and has_tokens:
                pass_count += 1
        else:
            markers = parse_markers(combined)
            if has_tokens and markers.get("STATUS") in {"PARTIAL_SUCCESS", "SUCCESS"}:
                partial_count += 1
    if pass_count == 3 and partial_count == 1:
        update_step(step_id, "PASS", "Bad-input tests produced the expected clear failures and degraded behavior.")
    elif pass_count >= 2:
        update_step(step_id, "PARTIAL", "Some bad-input cases behaved correctly, but not all of them.")
    else:
        update_step(step_id, "FAIL", "Bad-input tests did not behave clearly enough.")
        raise RuntimeError("Negative test coverage failed.")


def compare_admin_nonadmin() -> None:
    nonadmin = STATE.get("context", {}).get("nonadmin_collect_markers", {})
    admin = STATE.get("context", {}).get("admin_collect_markers", {})
    if not nonadmin or not admin:
        update_step("admin_compare", "FAIL", "Could not compare admin and non-admin results because one side is missing.")
        raise RuntimeError("Missing comparison data.")

    if nonadmin.get("IS_ELEVATED") == "False" and admin.get("IS_ELEVATED") == "True":
        diff_keys = []
        for key in ["AUDIT_POLICY_ACCESS_STATUS", "NETSTAT_OWNER_AWARE_STATUS", "SECURITY_AUDIT_POLICY_PATH", "SECURITY_FILTERED_PATH"]:
            if nonadmin.get(key) != admin.get(key):
                diff_keys.append(key)
        if diff_keys:
            update_step("admin_compare", "PASS", "Admin and non-admin results were both captured, and the security/elevation differences are visible.")
        else:
            update_step("admin_compare", "PARTIAL", "Admin and non-admin runs were captured, but the practical differences were weaker than expected.")
    else:
        update_step("admin_compare", "FAIL", "The admin/non-admin comparison did not show the expected elevation markers.")
        raise RuntimeError("Admin/non-admin comparison failed.")


def run_full_regression() -> None:
    ensure_runtime_available()
    outroot = OUTPUT_DIR / "harness_output"
    if outroot.exists():
        shutil.rmtree(outroot)
    outroot.mkdir(parents=True, exist_ok=True)
    cmd = powershell_cmd(
        "-File", str(harness_script()),
        "-CollectorPath", str(collector_script_path()),
        "-Suite", "FullRegression",
        "-MasterZipPath", str(MASTER_ZIP_PATH),
        "-OutputRoot", str(outroot),
    )
    result = run_command("full_regression", cmd, repo_root() / "project_sources", "Running the full harness regression.")
    if result["exit_code"] == 0:
        update_step("full_regression", "PASS", "FullRegression completed successfully.")
    else:
        update_step("full_regression", "FAIL", "FullRegression failed. Open the report file and the harness output to see which suite broke.")
        raise RuntimeError("FullRegression failed.")


def recheck_package() -> None:
    validate_package(step_id="package_recheck")
