"""Issue618 isolated replay: real PR617 source snapshots through existing mocked E2E runner.

Local test adapter only. Does not mutate the tracked repository, send provider
requests or publish GitHub comments. All GitHub/OpenRouter HTTP is mocked by
the maintained dcoir_review_end_to_end_replay_runtime.run_one routine.
"""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".github" / "dcoir_review" / "scripts"))
import dcoir_review_end_to_end_replay_runtime as runtime
import dcoir_review_end_to_end_replay_support as support
import dcoir_review_historical_recall_cases as historical


def main(case_name: str) -> int:
    case = historical.cases()[0 if case_name.startswith("bad") else 1]
    large = case_name.endswith("-large")
    module = "-module" in case_name
    path = case["focus_path"]
    full = case["changed_diff"]
    expected_header = f"diff --git a/{path} b/{path}"
    assert full.startswith(expected_header), (case_name, full[:100])
    focus_diff = full.split("\ndiff --git a/", 1)[0] + "\n"
    assert "@@ " in focus_diff
    if case_name.startswith("bad"):
        assert "run_powershell_analyzer.py" in focus_diff
    source = case["focus_source"]
    if module:
        # Deliberate synthetic change atop genuine historic bad/safe source:
        # not an assertion about what was committed at the immutable SHA.
        direct = "python project_sources/collector/tools/run_powershell_analyzer.py"
        dotted = "project_sources.collector.tools.run_powershell_analyzer"
        invocation = (
            "python -m" + dotted if case_name.endswith("-attached")
            else 'python "-m" ' + dotted if case_name.endswith("-quoted")
            else "python -m " + dotted
        )
        assert direct in source
        source = source.replace(direct, invocation, 1)
        # The safe PR changed its preflight, not the analyzer command.
        focus_diff = focus_diff.replace(direct, invocation, 1)
    hunk = focus_diff[focus_diff.index("@@ "):]
    entries = [{
        "path": path,
        "status": "modified",
        "lines": source.splitlines(),
        "patch_override": hunk,
        "full_diff": focus_diff,
    }]
    if large:
        # No network or original historic commit needed in CI. Put a dozen
        # synthetic changed test modules before the actual source-backed action
        # to exercise bounded priority and post-model candidate preservation.
        distractions = []
        for i in range(12):
            p = f"project_sources/collector/tools/test_powershell_analyzer_mock_{i}.py"
            hunk = "@@ -0,0 +1,1 @@\n+from powershell_analyzer_cli import load_inventory\n"
            distractions.append({
                "path": p, "status": "modified",
                "lines": ["from powershell_analyzer_cli import load_inventory"],
                "patch_override": hunk,
                "full_diff": f"diff --git a/{p} b/{p}\n" + hunk,
            })
        entries = distractions + entries
    for p, source in {**case["dependency_sources"], **case["caller_sources"]}.items():
        if p != path:
            entries.append({"path": p, "lines": source.splitlines(), "changed": False})
    runtime.HEAD = case["reviewed_head"]
    spec = {
        "files": entries,
        "model": {"first-pass": [support.CLEAN]},
        "keep_debug": False,
        "suffix": "debug",
    }
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        runtime.run_one(str(ROOT), "pr617-source-backed-" + case_name, spec)
    lines = [line for line in stdout.getvalue().splitlines() if line.startswith("E2E_RESULT ")]
    assert len(lines) == 1, (stdout.getvalue()[-1800:], stderr.getvalue()[-1000:])
    result = json.loads(lines[0].split("E2E_RESULT ", 1)[1])
    review_body = result.pop("body_full", "")
    result["source_population"] = (
        "synthetic module-mode mutation of real PR617 bad/safe action and dependencies; "
        "source differs from the recorded immutable historic SHA"
        if module else "PR617 real action source + real dependency/caller sources"
    )
    result["diff_population"] = (
        "real action hunk + 12 synthetic test-file distractions (not full original PR)"
        if large else "real changed action hunk, narrowed one-file list (not full original PR)"
    )
    result["reviewed_head"] = case["reviewed_head"]
    result["review_summary"] = review_body[:800]
    result["model_clean_first_pass"] = True
    result["inventory_progress"] = [line[:360] for line in stdout.getvalue().splitlines() if "[dcoir-review] source-inventory" in line][:12]
    print(json.dumps(result, ensure_ascii=True, indent=2))
    success = result["outcome"] == "ok" and result["review_posted"] and not result["unknown_gh"]
    if case_name.startswith("bad"):
        hit = any(
            c["path"] == path and c["line"] == 36
            and ("inventory" in c["body"].lower() or "powershell" in c["body"].lower())
            for c in result["inline_entries"]
        )
        success = success and hit
    else:
        success = success and len(result["inline_entries"]) == 0
    print("HISTORICAL_E2E_" + case_name.upper() + "_RESULT=" + ("PASS" if success else "FAIL"))
    return 0 if success else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=["bad", "safe", "bad-large", "safe-large",
                                       "bad-module", "safe-module",
                                       "bad-module-attached", "safe-module-attached",
                                       "bad-module-quoted", "safe-module-quoted"], default=None)
    args = ap.parse_args()
    if args.case:
        raise SystemExit(main(args.case))
    # Keep each real-snapshot replay isolated: run_one patches urllib, os
    # and imported reviewer modules, so the sibling control uses a new interpreter.
    import subprocess
    for label in ("bad", "safe", "bad-large", "safe-large",
                  "bad-module", "safe-module",
                  "bad-module-attached", "safe-module-attached",
                  "bad-module-quoted", "safe-module-quoted"):
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--case", label],
            check=True, timeout=120
        )
    print("PASS: historical PR617 source-backed end-to-end mock bad/safe pair")
