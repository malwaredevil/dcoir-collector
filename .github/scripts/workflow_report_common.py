"""Shared helpers for ChatGPT workflow report scripts."""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

REPORT_ROOT = Path("chatgpt_staging/status_reports")
REQUEST_ROOT = Path("chatgpt_staging/requests")
OUT_ROOT = Path("chatgpt_staging/out")
SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_segment(value: object, default: str = "unknown") -> str:
    text = str(value or default).strip() or default
    text = SAFE_SEGMENT_RE.sub("-", text)
    text = text.strip(".-_") or default
    return text[:120]


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_text_if_present(path: Path | None, limit_chars: int = 60000) -> str:
    if path is None or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit_chars:
        return text[-limit_chars:]
    return text


def bounded_lines(text: str, max_lines: int, max_chars: int) -> list[str]:
    if not text:
        return []
    lines = text.splitlines()
    selected = lines[-max_lines:] if len(lines) > max_lines else lines
    joined = "\n".join(selected)
    if len(joined) > max_chars:
        joined = joined[-max_chars:]
        selected = ["[truncated to final bounded excerpt]"] + joined.splitlines()
    if len(lines) > max_lines:
        selected = [f"[truncated: showing final {len(selected)} of {len(lines)} log lines]"] + selected
    return selected


def git_commit_epoch(path: Path) -> int | None:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    if not out:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def parse_report_result(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except Exception:
        return "unknown"
    if "- result: failure" in text or "- conclusion: failure" in text:
        return "failure"
    if "- result: cancelled" in text or "- conclusion: cancelled" in text:
        return "failure"
    if "- result: timed_out" in text or "- conclusion: timed_out" in text:
        return "failure"
    if "- result: action_required" in text or "- conclusion: action_required" in text:
        return "failure"
    if "- result: startup_failure" in text or "- conclusion: startup_failure" in text:
        return "failure"
    if "- result: success" in text or "- conclusion: success" in text:
        return "success"
    if "chatgpt-report-retention-cleanup" in text or "retention-cleanup" in str(path):
        return "cleanup"
    return "unknown"


def path_age_days(path: Path, now: dt.datetime) -> float:
    epoch = git_commit_epoch(path)
    if epoch is None:
        return 0.0
    committed = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
    return max(0.0, (now - committed).total_seconds() / 86400.0)


def newest_report_per_workflow(paths: Iterable[Path]) -> set[Path]:
    newest: dict[str, tuple[int, Path]] = {}
    for path in paths:
        parts = path.parts
        try:
            idx = parts.index("repo-workflows")
            workflow = parts[idx + 1]
        except Exception:
            workflow = str(path.parent)
        epoch = git_commit_epoch(path) or 0
        if workflow not in newest or epoch > newest[workflow][0]:
            newest[workflow] = (epoch, path)
    return {item[1] for item in newest.values()}
