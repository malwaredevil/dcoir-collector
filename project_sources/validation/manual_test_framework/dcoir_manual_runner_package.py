#!/usr/bin/env python3
"""Repository, package, and runtime staging helpers for the manual test runner."""
from __future__ import annotations

import shutil
import sys

from dcoir_manual_runner_context import *

def ensure_repo() -> None:
    root = repo_root()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if (root / ".git").exists():
        cmd = ["git", "-C", str(root), "pull", "--ff-only"]
        result = run_command("repo_fetch", cmd, BASE_DIR, "Updating the local repo copy.")
        if result["exit_code"] != 0:
            update_step("repo_fetch", "FAIL", "Git pull failed. Authenticate Git to GitHub if needed, then rerun the framework.")
            raise RuntimeError("Git pull failed. If the repository is private, make sure this machine is authenticated to GitHub.")
    else:
        cmd = ["git", "clone", REPO_URL, str(root)]
        result = run_command("repo_fetch", cmd, BASE_DIR, "Cloning the repo into the local work folder.")
        if result["exit_code"] != 0:
            update_step("repo_fetch", "FAIL", "Git clone failed. If this repo is private, sign in to Git on this machine and rerun the framework.")
            raise RuntimeError("Git clone failed. If the repository is private, authenticate this machine to GitHub and rerun the framework.")

    for path in required_repo_paths():
        file_exists_or_raise(path, path.name)
    update_step("repo_fetch", "PASS", "Repo fetched and required files are present.")


def validate_package(step_id: str = "package_validate") -> None:
    out = build_dir()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    script = repo_root() / "project_sources" / "collector" / "tools" / "validate_dcoir_collector_runtime_package.py"
    cmd = [sys.executable, str(script), "--source-dir", str(repo_root()), "--output-dir", str(out)]
    result = run_command(step_id, cmd, repo_root(), "Validating the current package rules.")
    if result["exit_code"] == 0:
        update_step(step_id, "PASS", "Package validation passed.")
    else:
        update_step(step_id, "FAIL", "Package validation failed. Open the report file and fix the reported package-rule problems.")
        raise RuntimeError("Package validation failed.")


def build_package(step_id: str = "package_build") -> None:
    out = build_dir()
    out.mkdir(parents=True, exist_ok=True)
    script = repo_root() / "project_sources" / "collector" / "tools" / "build_dcoir_collector_runtime_package.py"
    cmd = [sys.executable, str(script), "--source-dir", str(repo_root()), "--output-dir", str(out)]
    result = run_command(step_id, cmd, repo_root(), "Building the delivery package.")
    if result["exit_code"] == 0 and newest_delivery_zip().exists():
        update_step(step_id, "PASS", "Delivery package build passed.")
    else:
        update_step(step_id, "FAIL", "Delivery package build failed. Open the report file and fix the build issue before rerunning.")
        raise RuntimeError("Delivery package build failed.")


def ensure_runtime_available() -> None:
    if collector_script_path().exists() and live_zip_path().exists():
        return
    file_exists_or_raise(MASTER_ZIP_PATH, "Master runtime zip")
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MASTER_ZIP_PATH, live_zip_path())
    extract_dir = stage_dir() / "master_runtime_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(MASTER_ZIP_PATH), str(extract_dir), "zip")
    combined = extract_dir / "DCOIR_Collector.ps1"
    file_exists_or_raise(combined, "Combined DCOIR_Collector.ps1")
    shutil.copy2(combined, collector_script_path())


def restore_and_stage_runtime() -> None:
    sdir = stage_dir()
    if sdir.exists():
        shutil.rmtree(sdir)
    sdir.mkdir(parents=True, exist_ok=True)

    restore_script = repo_root() / "project_sources" / "collector" / "tools" / "restore_dcoir_collector_runtime_zip.py"
    delivery_zip = newest_delivery_zip()
    base_runtime_zip = repo_root() / "supporting_assets" / "DCOIR_Collector.zip"
    restored_zip = sdir / "DCOIR_Collector_runtime_for_harness.zip"

    cmd = [
        sys.executable,
        str(restore_script),
        "--delivery-package-zip", str(delivery_zip),
        "--base-runtime-zip", str(base_runtime_zip),
        "--output-dir", str(sdir),
        "--output-name", restored_zip.name,
    ]
    result = run_command("runtime_restore", cmd, repo_root(), "Restoring the live-style runtime zip and extracting the combined collector.")
    if result["exit_code"] != 0:
        update_step("runtime_restore", "FAIL", "Runtime restore failed. Open the report file and fix the restore error.")
        raise RuntimeError("Runtime restore failed.")

    if not restored_zip.exists():
        update_step("runtime_restore", "FAIL", "Restore script finished but did not produce the runtime zip.")
        raise RuntimeError("Restore script did not produce the runtime zip.")

    if MASTER_ZIP_PATH.exists():
        MASTER_ZIP_PATH.unlink()
    shutil.copy2(restored_zip, MASTER_ZIP_PATH)

    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    extract_dir = sdir / "runtime_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(restored_zip), str(extract_dir), "zip")

    combined = extract_dir / "DCOIR_Collector.ps1"
    file_exists_or_raise(combined, "Combined DCOIR_Collector.ps1")
    shutil.copy2(combined, collector_script_path())
    shutil.copy2(restored_zip, live_zip_path())

    update_step("runtime_restore", "PASS", f"Staged DCOIR_Collector.ps1 and DCOIR_Collector.zip in {RUNTIME_DIR}.")
