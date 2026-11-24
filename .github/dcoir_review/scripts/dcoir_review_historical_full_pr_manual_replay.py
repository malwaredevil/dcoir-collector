#!/usr/bin/env python3
"""Manual no-network replay of the full ORIGINAL 45-file PR617 defect.

Requires the two immutable historical Git commits in the local repository.
Uses the maintained fake GitHub/OpenRouter end-to-end runtime. Nothing is
posted and no model API calls are made. This is not a live efficacy metric.
Unlike the CI-safe 13-file positive/safe test, this requires Git history.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = "2c59f81e41d89bc804d6b4aabaa86a0500662e90"
BAD = "50c69b9eb72779b43dd70b2c2e4b316db4f7d83f"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dcoir_review_end_to_end_replay_runtime as replay
import dcoir_review_end_to_end_replay_support as support
import dcoir_review_historical_recall_cases as history
from dcoir_review.exact_head_dependency_evidence import _direct_scripts


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE, timeout=30
    )


def source_at_head(path: str) -> str:
    return git("show", f"{BAD}:{path}").decode("utf-8", "replace")


def prepare() -> list[dict]:
    for sha in (BASE, BAD):
        if git("cat-file", "-t", sha).strip() != b"commit":
            raise ValueError(f"historical commit unavailable: {sha}")
    rows = git("diff", "--name-status", "--no-renames", BASE, BAD).decode().splitlines()
    entries: list[dict] = []
    for row in rows:
        status, path = row.split("\t", 1)
        if status not in ("A", "M", "D", "T"):
            raise ValueError(f"unsupported historical status: {status}")
        patch = git(
            "diff", "--no-ext-diff", "--no-renames", "--unified=3",
            BASE, BAD, "--", path
        ).decode("utf-8", "replace")
        data = b"" if status == "D" else git("show", f"{BAD}:{path}")
        entry = {
            "path": path,
            "status": {"A": "added", "M": "modified",
                       "D": "removed", "T": "modified"}[status],
            "lines": data.decode("utf-8", "replace").splitlines(),
            "full_diff": patch if patch.endswith("\n") else patch + "\n",
        }
        match = re.search(r"(?m)^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", patch)
        if status != "D" and match:
            entry["patch_override"] = patch[match.start():]
        if b"\x00" in data:
            entry["binary"] = True
        entries.append(entry)
    if len(entries) != 45:
        raise ValueError(f"original historical changed-file count drift: {len(entries)}")

    fixture = history.cases()[0]
    assert fixture["reviewed_head"] == BAD
    index = {item["path"] for item in entries}
    focus = next(e for e in entries if e["path"] == fixture["focus_path"])
    assert "\n".join(focus["lines"]).strip() == fixture["focus_source"].strip()
    for p, contents in {
        **fixture["dependency_sources"], **fixture["caller_sources"]
    }.items():
        if p not in index:
            entries.append({"path": p, "lines": contents.splitlines(),
                            "changed": False})
            index.add(p)
    # The mock contents route only sees supplied files. Include unchanged
    # directly invoked scripts from the same immutable commit, not fabricated
    # substitutes. Original files remain precisely the Git-reviewed versions.
    for item in list(entries):
        if item.get("status") == "removed" or not item["path"].endswith((".yml", ".yaml")):
            continue
        for dep in _direct_scripts(item["path"], "\n".join(item["lines"])):
            if dep not in index:
                entries.append({
                    "path": dep, "lines": source_at_head(dep).splitlines(),
                    "changed": False,
                })
                index.add(dep)
    return entries


def main() -> int:
    files = prepare()
    replay.HEAD = BAD
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        replay.run_one(
            str(ROOT), "historical-original-pr617-full-45",
            {"files": files, "model": {"first-pass": [support.CLEAN]}},
        )
    events = [
        line[len("E2E_RESULT "):]
        for line in output.getvalue().splitlines()
        if line.startswith("E2E_RESULT ")
    ]
    if len(events) != 1:
        raise RuntimeError("fake reviewer did not emit one terminal result")
    result = json.loads(events[0])
    focus = ".github/actions/run-psscriptanalyzer/action.yml"
    inline = result.get("inline_entries", [])
    found = [
        item for item in inline
        if item.get("path") == focus and item.get("line") == 36
        and ("powershell" in str(item.get("body", "")).lower()
             or "inventory" in str(item.get("body", "")).lower())
    ]
    passed = bool(
        result.get("outcome") == "ok"
        and result.get("review_posted")
        and not result.get("unknown_gh")
        and found
    )
    print(json.dumps({
        "status": "PASS" if passed else "FAIL",
        "source_population": "actual original PR617 Git history at immutable head",
        "reviewed_head": BAD,
        "changed_files": 45,
        "unchanged_head_source_files": sum(not x.get("changed", True) for x in files),
        "mock_model_calls": len(result.get("kinds", [])),
        "real_provider_requests": 0,
        "real_github_review_posts": 0,
        "simulated_review_posts": result.get("review_attempts"),
        "known_P1_published": bool(found),
        "review_outcome": result.get("outcome"),
        "inline_comments": len(inline),
        "note": "Synthetic model outputs and simplified GitHub metadata are not precision or cost evidence",
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Missing history or git error: {exc}. Fetch historical commits before retry.") from exc
