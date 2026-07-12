#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import textwrap
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "_test_output"
WORK_DIR = BASE_DIR / "_work"
RUNS_DIR = BASE_DIR / "_runs"
RUNTIME_DIR = OUTPUT_DIR / "live_runtime"
STATE_DEFAULT = OUTPUT_DIR / "_runner_state.json"
REPORT_PATH = OUTPUT_DIR / "DCOIR_Collector_Full_Signoff_Report.txt"
SESSION_INFO_PATH = OUTPUT_DIR / "_session_info.json"
BOOTSTRAP_DEFAULT = OUTPUT_DIR / "bootstrap_status.json"
MASTER_ZIP_PATH = OUTPUT_DIR / "DCOIR_Collector_master.zip"

REPO_URL = "https://github.com/DCOIR-Collector/dcoir-collector.git"

STEP_ORDER = [
    ("git_check", "Git prerequisite"),
    ("python_check", "Python prerequisite"),
    ("repo_fetch", "Fetch or update repo"),
    ("package_validate", "Validate package rules"),
    ("package_build", "Build delivery package"),
    ("runtime_restore", "Restore and stage live runtime"),
    ("help_top", "Top-level help"),
    ("help_quick", "Quick help"),
    ("help_contextual", "Contextual help"),
    ("bad_quick", "Bad command help fallback"),
    ("nonadmin_collect", "Non-admin collect"),
    ("nonadmin_validate", "Non-admin validator check"),
    ("review_surfaces", "Review-surface tuning"),
    ("nonadmin_targeted", "Non-admin targeted collect"),
    ("nonadmin_enrich", "Non-admin enrich lifecycle"),
    ("nonadmin_negative", "Non-admin bad input cases"),
    ("admin_launch", "Launch admin phase"),
    ("admin_collect", "Admin collect"),
    ("admin_validate", "Admin validator check"),
    ("admin_compare", "Admin vs non-admin compare"),
    ("t2_pathway_note", "T2 pathway mapping note"),
    ("full_regression", "FullRegression harness"),
    ("package_recheck", "Package build parity recheck"),
    ("cleanup", "Cleanup and evidence closeout"),
    ("final_signoff", "Final signoff summary"),
]

TERMINAL_STATUSES = {
    "PENDING": "Waiting",
    "RUNNING": "Running",
    "FOUND": "Ready",
    "INSTALLED": "Ready",
    "INSTALLING": "Installing",
    "PASS": "Pass",
    "PARTIAL": "Partial",
    "FAIL": "Fail",
    "ERROR": "Error",
    "ACTION": "Action",
    "LAUNCHING": "Launching",
    "SKIPPED": "Skipped",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-phase", action="store_true")
    ap.add_argument("--state-path", default=str(STATE_DEFAULT))
    ap.add_argument("--bootstrap-status-path", default=str(BOOTSTRAP_DEFAULT))
    return ap.parse_args()


ARGS = parse_args()
STATE_PATH = Path(ARGS.state_path)
BOOTSTRAP_STATUS_PATH = Path(ARGS.bootstrap_status_path)


def ensure_dirs() -> None:
    for path in [OUTPUT_DIR, WORK_DIR, RUNS_DIR, RUNTIME_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def terminal_width(default: int = 120) -> int:
    try:
        return shutil.get_terminal_size((default, 40)).columns
    except Exception:
        return default


def wrap_text(text: str, width: int) -> List[str]:
    raw_lines: List[str] = []
    for chunk in str(text).splitlines() or [""]:
        wrapped = textwrap.wrap(chunk, width=width, replace_whitespace=False, drop_whitespace=False)
        raw_lines.extend(wrapped or [""])
    return raw_lines


def now_text() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_bootstrap_statuses() -> Dict[str, Dict[str, str]]:
    if not BOOTSTRAP_STATUS_PATH.exists():
        return {}
    try:
        data = json.loads(BOOTSTRAP_STATUS_PATH.read_text(encoding="utf-8"))
        return data.get("steps", {})
    except Exception:
        return {}


def normalize_bootstrap_status(status: str) -> str:
    mapping = {
        "FOUND": "PASS",
        "INSTALLED": "PASS",
        "INSTALLING": "INSTALLING",
        "ACTION_REQUIRED": "ACTION",
        "FAIL": "FAIL",
        "ERROR": "ERROR",
        "PASS": "PASS",
    }
    return mapping.get((status or "").upper(), status or "PENDING")


def blank_steps() -> Dict[str, Dict[str, str]]:
    return {
        step_id: {"label": label, "status": "PENDING", "note": ""}
        for step_id, label in STEP_ORDER
    }


def sync_bootstrap_into_state(data: Dict) -> Dict:
    steps = data.setdefault("steps", blank_steps())
    for key, payload in load_bootstrap_statuses().items():
        if key in steps:
            steps[key]["status"] = normalize_bootstrap_status(payload.get("status", "PENDING"))
            steps[key]["note"] = payload.get("detail", "")
    return data


def load_state() -> Dict:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if "steps" in data:
                return sync_bootstrap_into_state(data)
        except Exception:
            pass
    data = {"steps": blank_steps(), "context": {}, "messages": []}
    return sync_bootstrap_into_state(data)


STATE = load_state()


def save_state() -> None:
    STATE_PATH.write_text(json.dumps(STATE, indent=2), encoding="utf-8")
    SESSION_INFO_PATH.write_text(
        json.dumps(
            {
                "started_at": STATE.get("context", {}).get("framework_started_at", now_text()),
                "mode": "ADMIN" if ARGS.admin_phase else "NON-ADMIN",
                "base_dir": str(BASE_DIR),
                "report_path": str(REPORT_PATH),
                "state_path": str(STATE_PATH),
                "repo_root": str(repo_root()),
                "runtime_dir": str(RUNTIME_DIR),
                "is_admin_process": is_admin(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def init_report() -> None:
    if REPORT_PATH.exists() and ARGS.admin_phase:
        return
    REPORT_PATH.write_text(
        "\n".join(
            [
                "DCOIR Collector Manual Test Framework Report",
                f"Started: {now_text()}",
                f"Framework mode: {'ADMIN' if ARGS.admin_phase else 'NON-ADMIN'}",
                f"Base directory: {BASE_DIR}",
                "",
                "This report captures every command, exit code, stdout, stderr, and framework note.",
                "=" * 90,
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def append_report(text: str) -> None:
    with REPORT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")


def report_command_block(step_id: str, cmd: List[str], cwd: Path, rc: Optional[int], stdout: str, stderr: str, exc: str = "") -> None:
    lines = [
        "=" * 90,
        f"Timestamp: {now_text()}",
        f"Step: {step_id}",
        f"Working directory: {cwd}",
        "Command:",
        "  " + " ".join(f'"{part}"' if " " in str(part) else str(part) for part in cmd),
        f"Exit code: {rc if rc is not None else 'NO_EXIT_CODE'}",
        "",
        "STDOUT:",
        stdout.rstrip() or "<empty>",
        "",
        "STDERR:",
        stderr.rstrip() or "<empty>",
    ]
    if exc:
        lines += ["", "EXCEPTION:", exc.rstrip() or "<empty>"]
    append_report("\n".join(lines) + "\n")


def set_message(text: str) -> None:
    STATE.setdefault("messages", []).append({"timestamp": now_text(), "text": text})
    if len(STATE["messages"]) > 20:
        STATE["messages"] = STATE["messages"][-20:]
    render_dashboard(text)
    save_state()


def latest_message() -> str:
    if not STATE.get("messages"):
        return "Framework loaded. Waiting for the next step."
    return STATE["messages"][-1]["text"]


def update_step(step_id: str, status: str, note: str = "") -> None:
    STATE["steps"][step_id]["status"] = status
    if note:
        STATE["steps"][step_id]["note"] = note
    save_state()
    render_dashboard(note or latest_message())


def draw_box(title: str, body: str, width: int) -> str:
    inner = max(30, width - 4)
    lines = wrap_text(body, inner - 2)
    top = "+" + "-" * inner + "+"
    title_line = f"| {title[: inner - 2].ljust(inner - 2)} |"
    content = [f"| {line.ljust(inner - 2)} |" for line in lines]
    return "\n".join([top, title_line, top] + content + [top])


def render_dashboard(message: str = "") -> None:
    clear_screen()
    width = max(100, min(terminal_width(), 160))
    status_w = 14
    name_w = width - status_w - 7
    top = "+" + "-" * (status_w + 2) + "+" + "-" * (name_w + 2) + "+"
    print("DCOIR Manual Test Framework")
    print(f"Mode: {'ADMIN' if ARGS.admin_phase else 'NON-ADMIN'}    Report: {REPORT_PATH}")
    print(f"Time: {now_text()}")
    print(top)
    print(f"| {'STATUS'.ljust(status_w)} | {'TEST'.ljust(name_w)} |")
    print(top)
    for step_id, _label in STEP_ORDER:
        raw_status = STATE["steps"][step_id]["status"]
        status = TERMINAL_STATUSES.get(raw_status, raw_status)[:status_w]
        label = STATE["steps"][step_id]["label"][:name_w]
        print(f"| {status.ljust(status_w)} | {label.ljust(name_w)} |")
    print(top)
    print(draw_box("STATUS / NEXT ACTION", message or latest_message(), width))


def run_command(step_id: str, cmd: List[str], cwd: Path, note: str, allow_error: bool = False, timeout: Optional[int] = None) -> Dict[str, object]:
    update_step(step_id, "RUNNING", note)
    result = {"ok": False, "exit_code": None, "stdout": "", "stderr": ""}
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, shell=False)
        result["exit_code"] = proc.returncode
        result["stdout"] = proc.stdout or ""
        result["stderr"] = proc.stderr or ""
        report_command_block(step_id, cmd, cwd, proc.returncode, proc.stdout or "", proc.stderr or "")
        result["ok"] = (proc.returncode == 0) or allow_error
        return result
    except Exception:
        report_command_block(step_id, cmd, cwd, None, "", "", exc=traceback.format_exc())
        raise


def powershell_cmd(*args: str) -> List[str]:
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", *args]


def repo_root() -> Path:
    return WORK_DIR / "dcoir-collector"


def stage_dir() -> Path:
    return OUTPUT_DIR / "staging"


def build_dir() -> Path:
    return WORK_DIR / "out_build"


def validate_script() -> Path:
    return repo_root() / "project_sources" / "collector" / "harness" / "validate_DCOIR_Run.ps1"


def harness_script() -> Path:
    return repo_root() / "project_sources" / "collector" / "harness" / "run_DCOIR_Tests.ps1"


def collector_script_path() -> Path:
    return RUNTIME_DIR / "DCOIR_Collector.ps1"


def live_zip_path() -> Path:
    return RUNTIME_DIR / "DCOIR_Collector.zip"


def required_repo_paths() -> List[Path]:
    root = repo_root()
    return [
        root / "project_sources" / "collector" / "source" / "DCOIR_Collector.ps1",
        root / "project_sources" / "collector" / "source" / "parts" / "DCOIR_Collector.05_Main_Entry.ps1",
        root / "project_sources" / "collector" / "tools" / "build_dcoir_collector_runtime_package.py",
        root / "project_sources" / "collector" / "tools" / "restore_dcoir_collector_runtime_zip.py",
        root / "supporting_assets" / "DCOIR_Collector.zip",
    ]


def file_exists_or_raise(path: Path, friendly: str) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required file: {friendly} -> {path}")


def newest_delivery_zip() -> Path:
    zips = sorted(build_dir().glob("DCOIR_Collector_Delivery_Package_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        raise RuntimeError("No delivery package zip was produced.")
    return zips[0]


def newest_run_root(parent: Path, run_id: str = "") -> Path:
    candidates = [p for p in parent.glob("DCOIR_*") if p.is_dir()]
    if run_id:
        matches = [p for p in candidates if run_id in p.name]
        if matches:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]
    if not candidates:
        raise RuntimeError(f"No DCOIR run folders found under {parent}")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def parse_markers(text: str) -> Dict[str, str]:
    markers: Dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            if key.isupper():
                markers[key] = value.strip()
    return markers


def test_output_has_all(text: str, tokens: List[str]) -> bool:
    hay = text or ""
    return all(token in hay for token in tokens)


def best_effort_cleanup_paths() -> None:
    for path in [stage_dir(), build_dir(), OUTPUT_DIR / "harness_output_temp"]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
