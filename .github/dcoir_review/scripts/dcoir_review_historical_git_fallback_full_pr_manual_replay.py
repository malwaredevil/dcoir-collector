#!/usr/bin/env python3
"""No-network full original PR617 Git-fallback P1 replay with mocked model CLEAN.

Runs real current production entrypoint with historically immutable source at
the 47-path vulnerable head, then the repaired-safe control. No API posts.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dcoir_review_end_to_end_replay_runtime as runtime
import dcoir_review_end_to_end_replay_support as support
from dcoir_review.exact_head_dependency_evidence import _direct_scripts
from dcoir_review.git_fallback_source_proof import PATHS, VERIFIER

BASE = "2c59f81e41d89bc804d6b4aabaa86a0500662e90"
BAD = "959e916a6671c9d89e25842f4a170b917ad08b93"
SAFE = "13ef93fe52851a5800bcdf6714733abecc1ce76a"


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE, timeout=30
    )


def prepare(sha: str) -> tuple[list[dict], int]:
    assert git("cat-file", "-t", sha).strip() == b"commit"
    rows = git("diff", "--name-status", "--no-renames", BASE, sha).decode().splitlines()
    entries = []
    for row in rows:
        status, path = row.split("\t", 1)
        if status not in ("A", "M", "D", "T"):
            raise ValueError(f"unsupported historical changed file: {status}: {path}")
        patch = git("diff", "--no-ext-diff", "--no-renames", "--unified=3",
                    BASE, sha, "--", path).decode("utf-8", "replace")
        data = b"" if status == "D" else git("show", f"{sha}:{path}")
        entry = {
            "path": path,
            "status": {"A": "added", "M": "modified", "D": "removed", "T": "modified"}[status],
            "lines": data.decode("utf-8", "replace").splitlines(),
            "full_diff": patch if patch.endswith("\n") else patch + "\n",
        }
        hunk = re.search(r"(?m)^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", patch)
        if status != "D" and hunk:
            entry["patch_override"] = patch[hunk.start():]
        if b"\x00" in data:
            entry["binary"] = True
        entries.append(entry)
    changed = len(entries)
    if sha == BAD:
        assert changed == 47, f"historical second-P1 diff scope drifted: {changed}"
    by_path = {entry["path"] for entry in entries}
    # The mocked GitHub contents API needs unchanged exact-head source, too.
    required = set(PATHS)
    for entry in entries:
        if entry["status"] == "removed" or not entry["path"].endswith((".yml", ".yaml")):
            continue
        required.update(_direct_scripts(entry["path"], "\n".join(entry["lines"])))
    for path in sorted(required - by_path):
        try:
            content = git("show", f"{sha}:{path}")
        except subprocess.CalledProcessError:
            # Do not fabricate unavailable source; production must fail closed
            # if any required executable is absent.
            continue
        entries.append({"path": path, "lines": content.decode("utf-8", "replace").splitlines(),
                        "changed": False})
    assert any(e["path"] == VERIFIER for e in entries)
    return entries, changed


def main(which: str) -> int:
    sha = BAD if which == "bad" else SAFE
    files, changed = prepare(sha)
    runtime.HEAD = sha
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runtime.run_one(str(ROOT), "historical-git-fallback-" + which,
                        {"files": files, "model": {"first-pass": [support.CLEAN]}})
    rows = [row[11:] for row in out.getvalue().splitlines() if row.startswith("E2E_RESULT ")]
    if len(rows) != 1:
        raise RuntimeError(f"mocked production replay missing terminal output: {out.getvalue()[-1500:]}")
    result = json.loads(rows[0])
    matches = [x for x in result.get("inline_entries", [])
               if x.get("path") == VERIFIER and x.get("line") == 20
               and "fallback" in str(x.get("body", "")).lower()]
    pass_condition = (
        result.get("outcome") == "ok" and result.get("review_posted")
        and not result.get("unknown_gh")
        and (len(matches) == 1 if which == "bad" else len(matches) == 0)
    )
    print(json.dumps({
        "status": "PASS" if pass_condition else "FAIL",
        "which": which, "sha": sha,
        "changed_files": changed,
        "unchanged_git_source_files": len(files) - changed,
        "model_first_pass_output": "CLEAN",
        "mocked_model_calls": len(result.get("kinds", [])),
        "real_model_calls": 0, "real_github_reviews": 0,
        "simulated_review_posts": result.get("review_attempts"),
        "verifier_git_fallback_high_published": bool(matches),
        "inline_count": len(result.get("inline_entries", [])),
        "other_mock_inline_count": len(result.get("inline_entries", [])) - len(matches),
        "control_scope": "Only the Git-fallback HIGH proof is scored; unrelated mocked findings are not precision evidence",
        "inline_entries": result.get("inline_entries", [])[:4],
        "outcome": result.get("outcome"),
        "unknown_gh": result.get("unknown_gh", []),
    }, indent=2))
    return 0 if pass_condition else 1


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--case", choices=("bad", "safe"), required=True)
    raise SystemExit(main(arg.parse_args().case))
