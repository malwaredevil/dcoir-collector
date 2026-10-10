"""Fixtures and driver for the offline end-to-end DCOIR Review replay selftest.

The replay runs the real entrypoint (every runtime patch, the composed review
pipeline, verifier, repair, and publication) and fakes only the network
(``urllib.request.urlopen``) for GitHub and OpenRouter. Each scenario runs in a
fresh interpreter so module-level runtime state never leaks between cases.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

REPO = "malwaredevil/dcoir-collector"
PR = 614
HEAD = "1" * 40
NEW_HEAD = "4" * 40
BASE_SHA = "2" * 40

PY_LINES = [
    "import json",
    "",
    "def load(path):",
    "    with open(path) as handle:",
    "        data = json.load(handle)",
    "    if data.get('known_good'):",
    "        return data['pack']",
    "    return None",
    "",
    "def score(pack, expected):",
    "    failures = [k for k in expected if pack.get(k) != expected[k]]",
    "    return not failures",
]
SENTINEL_LINES = list(PY_LINES)
SENTINEL_LINES[0] = "import json, pickle"
SENTINEL_LINES[4] = "        data = pickle.loads(handle.read())"
PS_LINES = [
    "function Get-Pack {",
    "    param([string]$Path)",
    "    $data = Get-Content -Raw -Path $Path | ConvertFrom-Json",
    "    if ($data.known_good) { return $data.pack }",
    "    return $null",
    "}",
]
MD_LINES = ["# Notes", "", "Known-good packs are trusted as labeled.", "Ünïcödé — résumé ✓"]


def F(conf, path="tools/replay_0.py", line=6, title="Known-bad pack accepted", **extra):
    item = {
        "title": title, "severity": "medium", "confidence": conf, "path": path, "line": line,
        "body": f"Line {line} trusts the known_good label, so a known-bad pack passes the gate.",
        "suggested_replacement": "",
        "validation": "Run the replay suite with a known-bad pack labeled known_good; it must be rejected.",
    }
    item.update(extra)
    return item


def R(*findings, summary="Findings below."):
    return {"summary": summary, "findings": list(findings)}


CLEAN = {"summary": "No actionable issues found in the changed lines.", "findings": []}
VERIFIED = {"supported": True, "confidence": 0.9, "evidence": "Line 6 returns the pack whenever known_good is truthy.", "reason": "Counterexample: a known-bad pack labeled known_good passes."}
REJECTED = {"supported": False, "confidence": 0.9, "evidence": "The caller validates the pack first.", "reason": "Not reproducible from the supplied file."}


class HTTP(Exception):
    def __init__(self, code, body="error"):
        super().__init__(code)
        self.code, self.body = code, body


class TimeoutErr(Exception):
    pass


class Raw(Exception):
    """Return this raw content string instead of JSON."""

    def __init__(self, content, finish="stop"):
        super().__init__(content)
        self.content, self.finish = content, finish


def files_default(n=6, lines=PY_LINES):
    return [{"path": f"tools/replay_{i}.py", "lines": lines} for i in range(n)]


def judge(spec, res):
    expect = spec.get("expect", "ok")
    ok = res["outcome"] == "ok"
    problems = []
    if expect == "ok" and not ok:
        problems.append("expected success")
    if expect == "fail" and ok:
        problems.append("expected failure")
    if expect == "superseded" and (not ok or res["review_posted"] or "superseded" not in res["status_tail"]):
        problems.append("expected a clean supersession with no review posted")
    if not ok and spec.get("fail_contains") and spec["fail_contains"] not in res["outcome"]:
        problems.append(f"failure does not mention {spec['fail_contains']!r}")
    if ok and expect == "ok" and not res["review_posted"]:
        problems.append("no review posted")
    if ok and "comments" in spec and res["comments"] != spec["comments"]:
        problems.append(f"comments {res['comments']} != {spec['comments']}")
    if ok and "min_comments" in spec and (res["comments"] or 0) < spec["min_comments"]:
        problems.append(f"comments {res['comments']} < {spec['min_comments']}")
    if ok and spec.get("body_contains") and spec["body_contains"] not in res.get("body_full", ""):
        problems.append("review body missing expected text")
    spent = sorted(set(spec.get("forbid_kinds", ())) & set(res["kinds"]))
    if spent:
        problems.append(f"unexpected model calls {spent}")
    if res["unknown_gh"]:
        problems.append(f"unhandled GitHub calls {res['unknown_gh']}")
    return problems


def run_subprocess(script: str, name: str, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **(extra_env or {}))
    proc = subprocess.run(
        [sys.executable, script, "--scenario", name],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=600,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("E2E_RESULT "):
            return json.loads(line[len("E2E_RESULT "):])
    return {
        "name": name, "outcome": f"harness crash rc={proc.returncode}: {proc.stderr[-800:]}",
        "kinds": [], "review_posted": False, "comments": None, "unknown_gh": [], "event": None,
        "body_full": "", "status_tail": "",
    }


def run_named(script: str, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    if not spec.get("incremental"):
        return run_subprocess(script, name)
    # Phase one posts a real review; phase two re-reviews a new head with it.
    handle = tempfile.NamedTemporaryFile("w", delete=False, suffix=".md")
    handle.close()
    try:
        env = {"E2E_PRIOR_REVIEW": handle.name}
        first = run_subprocess(script, name, {**env, "E2E_PHASE": "first"})
        if not first["review_posted"]:
            first["outcome"] = "first phase did not post a review: " + first["outcome"]
            return first
        return run_subprocess(script, name, {**env, "E2E_PHASE": "second"})
    finally:
        os.unlink(handle.name)


def run_matrix(script: str, scenarios: dict[str, dict[str, Any]], only: str = "", jobs: int = 6) -> int:
    names = [name for name in scenarios if only in name]
    with ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(lambda name: run_named(script, name, scenarios[name]), names))
    failures = 0
    for res in results:
        problems = judge(scenarios[res["name"]], res)
        failures += bool(problems)
        print(f"{'PASS' if not problems else 'FAIL'} {res['name']}: outcome={res['outcome'][:200]}")
        if problems:
            print(f"     problems={problems}; calls={res['kinds']}")
    print(f"{len(results) - failures}/{len(results)} end-to-end replay scenarios passed")
    return failures


__all__ = [name for name in dir() if not name.startswith("_")]
