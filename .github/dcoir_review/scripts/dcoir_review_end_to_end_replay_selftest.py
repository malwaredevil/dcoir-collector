#!/usr/bin/env python3
"""Offline end-to-end DCOIR Review replay across every review path.

Each scenario drives the real entrypoint through first-pass-deep, deep, diff,
and incremental re-review paths with scripted provider and GitHub behavior,
including the run 37983201801 adjudication sequence. Run from the repository
root; ``--only <substr>`` narrows the matrix and ``--scenario <name>`` runs one
case in-process (used by the parallel driver).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dcoir_review_end_to_end_replay_support import (
    CLEAN, F, HTTP, MD_LINES, PS_LINES, PY_LINES, R, REJECTED, Raw, SENTINEL_LINES,
    TimeoutErr, VERIFIED, files_default, run_matrix,
)

REPO_ROOT = str(Path(__file__).resolve().parents[3])
SCENARIOS: dict[str, dict] = {}


def scenario(name, **spec):
    SCENARIOS[name] = spec


LIVE = {  # run 37983201801 shape
    "first-pass": lambda st, p: R(F(0.60, path=st["file_in_prompt"])),
    "quality-retry": [R(F(0.72), F(0.70, path="tools/replay_1.py", line=11))],
    "challenger": [R(F(0.66, line=11, title="Scoring gate too broad"))],
    "v44-adjudicator": [R(F(0.62, line=11, title="Scoring gate"), F(0.55), F(0.58, path="tools/replay_1.py", line=11), summary="Hypotheses remain uncertain.")],
    "v35-adjudicator": [R(F(0.62, line=11, title="Scoring gate"), F(0.55), F(0.58, path="tools/replay_1.py", line=11), summary="Hypotheses remain uncertain.")],
    "verifier": [VERIFIED],
}


def live(**overrides):
    model = dict(LIVE)
    model.update(overrides)
    return model


# --- first-pass-deep (default /dcoir-review) ---
scenario("fpd-clean", model={"first-pass": [CLEAN]}, expect="ok", comments=0)
scenario("fpd-high-confidence", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [VERIFIED]}, expect="ok", min_comments=1)
scenario("fpd-high-verifier-rejects", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [REJECTED]}, expect="ok", comments=0)
scenario("fpd-live-retry-repairs", model=live(**{"v44-adjudication-retry": [R(F(0.86, line=11))], "v35-adjudication-retry": [R(F(0.86, line=11))]}), expect="ok", min_comments=1)
scenario("fpd-live-retry-clean", model=live(**{"v44-adjudication-retry": [CLEAN]}), expect="ok", comments=0)
scenario("fpd-live-retry-low", model=live(**{"v44-adjudication-retry": [R(F(0.64, line=11), summary="Still uncertain.")]}), expect="ok", comments=0)
scenario("fpd-live-retry-provider-error", model=live(**{"v44-adjudication-retry": [HTTP(500)]}), expect="ok", comments=0)
scenario("fpd-live-broad", files=files_default(6), model=live(**{
    "quality-retry": [R(*[F(0.71, path=f"tools/replay_{i}.py") for i in range(5)])],
    "v44-adjudication-retry": [R(F(0.64, line=11), summary="Still uncertain.")]}), expect="ok", comments=0)
scenario("fpd-live-broad-repair", files=files_default(6), model=live(**{
    "quality-retry": [R(*[F(0.71, path=f"tools/replay_{i}.py") for i in range(5)])],
    "v44-adjudication-retry": [R(F(0.86, line=11))]}), expect="ok", min_comments=1)
scenario("fpd-passthrough-high", model=live(**{
    "quality-retry": [R(F(0.72), F(0.70, path="tools/replay_1.py", line=11), F(0.95, path="tools/replay_2.py", line=11, title="Definite defect"))],
    "v44-adjudication-retry": [R(F(0.64, line=11), summary="Still uncertain.")]}), expect="ok", min_comments=1)
scenario("fpd-retry-out-of-scope", model=live(**{
    "v44-adjudication-retry": [R(F(0.9, path="tools/replay_4.py", line=11))]}), expect="ok", comments=0)
scenario("fpd-retry-missing-confidence", model=live(**{
    "v44-adjudication-retry": [R({k: v for k, v in F(0.0, line=11).items() if k != "confidence"})]}), expect="ok")
scenario("fpd-adjudicator-shape-recovery", model=live(**{"v44-adjudicator": [{"verdict": "unclear", "notes": "n/a"}]}), expect="ok")
scenario("fpd-adjudicator-flat-finding", model=live(**{"v44-adjudicator": [F(0.88, line=11)]}), expect="ok", min_comments=1)
scenario("fpd-summary-only-problem", model={"first-pass": [{"summary": "A correctness issue remains in the scoring gate.", "findings": []}],
    "quality-retry": [R(F(0.9, line=11))], "verifier": [VERIFIED]}, expect="ok")
scenario("fpd-sentinel-low", files=files_default(2, SENTINEL_LINES), model=live(**{
    "v44-adjudication-retry": [R(F(0.64, line=11), summary="Still uncertain.")]}), expect="ok", min_comments=2)
scenario("fpd-sentinel-clean", files=files_default(2, SENTINEL_LINES), model={"first-pass": [CLEAN], "verifier": [VERIFIED]}, expect="ok", min_comments=2)
scenario("fpd-many-findings", model={"first-pass": lambda st, p: R(*[F(0.9, path=st["file_in_prompt"], line=l, title=f"Defect {l}") for l in (3, 5, 6, 7, 10, 11, 12)]), "verifier": [VERIFIED]}, expect="ok", min_comments=1)
scenario("fpd-per-file-provider-error", model={"first-pass": lambda st, p: (_ for _ in ()).throw(HTTP(500)) if st["file_in_prompt"].endswith("_3.py") else CLEAN}, expect="fail", fail_contains="Per-file first-pass coverage incomplete")
scenario("fpd-transient-429-then-ok", model={"first-pass": lambda st, p: (_ for _ in ()).throw(HTTP(429)) if st["count"] == 1 else CLEAN}, expect="ok", comments=0)
scenario("fpd-provider-down", model={"first-pass": [HTTP(503)]}, expect="fail", fail_contains="Per-file first-pass coverage incomplete")
scenario("fpd-fenced-json", model={"first-pass": [Raw("```json\n" + json.dumps(CLEAN) + "\n```")]}, expect="ok", comments=0)
scenario("fpd-non-json", model={"first-pass": [Raw("I could not review this.")]}, expect="fail", fail_contains="Per-file first-pass coverage incomplete")
scenario("fpd-length-cutoff", model={"first-pass": [Raw(json.dumps(CLEAN), finish="length")]}, expect="ok", comments=0)
scenario("fpd-repair-real", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [VERIFIED]}, expect="ok", min_comments=1, repair=True)

scenario("fpd-very-low", model={"first-pass": lambda st, p: R(F(0.40, path=st["file_in_prompt"])), "quality-retry": [R(F(0.45), summary="Still uncertain.")],
    "v44-adjudicator": [R(F(0.50), summary="Still uncertain.")], "v44-adjudication-retry": [R(F(0.52), summary="Still uncertain.")]}, expect="ok", comments=0)
scenario("fpd-very-low-no-escalation-findings", model={"first-pass": lambda st, p: R(F(0.40, path=st["file_in_prompt"])), "quality-retry": [R(F(0.45), summary="Still uncertain.")]}, expect="ok", comments=0)

scenario("fpd-retry-low-with-replacement", model=live(**{"v44-adjudication-retry": [R(F(0.64, line=11, suggested_replacement="    return bool(pack) and not failures"), summary="Still uncertain.")]}), expect="ok", comments=0)
scenario("deep-retry-low-with-replacement", suffix="deep", model=live(**{"v35-adjudication-retry": [R(F(0.64, line=11, suggested_replacement="    return bool(pack) and not failures"), summary="Still uncertain.")]}), expect="ok", comments=0)
scenario("fpd-retry-low-offdiff-line", model=live(**{"v44-adjudication-retry": [R(F(0.64, line=40), summary="Still uncertain.")]}), expect="ok", comments=0)
scenario("fpd-retry-low-empty-validation", model=live(**{"v44-adjudication-retry": [R(F(0.64, line=11, validation=""), summary="Still uncertain.")]}), expect="ok", comments=0)

# --- file shapes ---
scenario("files-mixed-shapes", files=[
    {"path": "tools/replay_0.py", "lines": PY_LINES},
    {"path": "scripts/Get-Pack.ps1", "lines": PS_LINES},
    {"path": "docs/notes.md", "lines": MD_LINES},
    {"path": "assets/logo.png", "binary": True},
    {"path": "tools/old.py", "status": "removed"},
    {"path": "tools/renamed.py", "status": "renamed", "previous_filename": "tools/was.py", "lines": PY_LINES},
], model={"first-pass": lambda st, p: R(F(0.9, path="tools/replay_0.py")) if "replay_0" in st["file_in_prompt"] else CLEAN, "verifier": [VERIFIED]}, expect="ok", min_comments=1)
scenario("files-pagination-120", files=files_default(120), model={"first-pass": [CLEAN]}, expect="ok", comments=0)

# --- explicit modes ---
scenario("deep-live-retry-low", suffix="deep", model=live(**{"v35-adjudication-retry": [R(F(0.64, line=11), summary="Still uncertain.")]}), expect="ok", comments=0)
scenario("deep-live-retry-repairs", suffix="deep", model=live(**{"v35-adjudication-retry": [R(F(0.86, line=11))]}), expect="ok", min_comments=1)
scenario("deep-clean", suffix="deep", model={"first-pass": [CLEAN]}, expect="ok", comments=0)
scenario("diff-clean", suffix="diff", model={"first-pass": [CLEAN]}, expect="ok", comments=0)
scenario("diff-high", suffix="diff", model={"first-pass": [R(F(0.9))], "verifier": [VERIFIED]}, expect="ok", min_comments=1)
scenario("diff-near-threshold", suffix="diff", model={"first-pass": [R(F(0.62))], "v44-adjudicator": [R(F(0.86))], "verifier": [VERIFIED]}, expect="ok", min_comments=1)
scenario("diff-near-threshold-low-twice", suffix="diff", model={"first-pass": [R(F(0.62))], "v44-adjudicator": [R(F(0.63), summary="Still uncertain.")], "v44-adjudication-retry": [R(F(0.64), summary="Still uncertain.")]}, expect="ok", comments=0)
scenario("diff-very-low", suffix="diff", model={"first-pass": [R(F(0.40))], "quality-retry": [R(F(0.45), summary="Still uncertain.")]}, expect="ok", comments=0)
scenario("diff-very-low-retry-clean", suffix="diff", model={"first-pass": [R(F(0.40))], "quality-retry": [CLEAN]}, expect="ok", comments=0)
scenario("diff-sentinel-low", suffix="diff", files=files_default(2, SENTINEL_LINES), model={"first-pass": [R(F(0.62, line=11))], "quality-retry": [R(F(0.63, line=11), summary="Still uncertain.")]}, expect="ok", min_comments=2)

scenario("diff-very-low-adjudicated-low", suffix="diff", model={"first-pass": [R(F(0.40))], "quality-retry": [R(F(0.45), summary="Still uncertain.")],
    "v44-adjudicator": [R(F(0.50), summary="Still uncertain.")], "v44-adjudication-retry": [R(F(0.52), summary="Still uncertain.")]}, expect="ok", comments=0)
scenario("diff-very-low-many-paths", suffix="diff", files=files_default(6), model={"first-pass": [R(*[F(0.40, path=f"tools/replay_{i}.py") for i in range(6)])],
    "quality-retry": [R(*[F(0.45, path=f"tools/replay_{i}.py") for i in range(6)], summary="Still uncertain.")],
    "v44-adjudicator": [R(F(0.50), summary="Still uncertain.")]}, expect="ok", comments=0)
scenario("diff-very-low-adjudicator-confirms", suffix="diff", model={"first-pass": [R(F(0.40))], "quality-retry": [R(F(0.45))], "v44-adjudicator": [R(F(0.88))], "verifier": [VERIFIED]}, expect="ok", min_comments=1)
scenario("deep-sentinel-low", suffix="deep", files=files_default(2, SENTINEL_LINES), model=live(**{"v35-adjudication-retry": [R(F(0.64, line=11), summary="Still uncertain.")]}), expect="ok", min_comments=2)

# --- provider failure shapes ---
scenario("verifier-provider-error", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [HTTP(500)]}, expect="fail", fail_contains="HTTP 500")
scenario("verifier-malformed", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [{"supported": "yes"}]}, expect="fail", fail_contains="verifier returned a non-boolean")
scenario("credit-402-saturation-recovers", model={"first-pass": lambda st, p: (_ for _ in ()).throw(HTTP(402, '{"error":{"message":"Insufficient credits for current in-flight requests. Retry after in-flight requests settle."}}')) if st["count"] <= 3 else CLEAN}, expect="ok", comments=0)
scenario("network-timeout-then-ok", model={"first-pass": lambda st, p: (_ for _ in ()).throw(TimeoutErr()) if st["count"] == 2 else CLEAN}, expect="ok", comments=0)
scenario("repair-provider-error", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [VERIFIED], "repair-author": [HTTP(500)]}, expect="ok", min_comments=1)
scenario("repair-malformed", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [VERIFIED], "repair-author": [{"action": "repair_set", "edits": "nonsense"}]}, expect="ok", min_comments=1)
scenario("challenger-error", model=live(**{"challenger": [HTTP(500)], "v44-adjudication-retry": [R(F(0.86, line=11))]}), expect="fail", fail_contains="HTTP 500")
scenario("adjudicator-error", model=live(**{"v44-adjudicator": [HTTP(500)]}), expect="fail", fail_contains="HTTP 500")

# --- PR shapes ---
scenario("pr-binary-and-deleted-only", files=[{"path": "assets/logo.png", "binary": True}, {"path": "tools/old.py", "status": "removed"}], model={"first-pass": [CLEAN]}, expect="ok", comments=0)
scenario("pr-huge-file-no-patch", files=[{"path": "tools/replay_0.py", "lines": PY_LINES}, {"path": "data/huge.json", "nopatch": True, "lines": ["{}"] * 5}], model={"first-pass": [CLEAN]}, expect="ok", comments=0)
scenario("pr-single-file-high", files=files_default(1), model={"first-pass": [R(F(0.9))], "verifier": [VERIFIED]}, expect="ok", min_comments=1)

# --- GitHub behaviors ---
scenario("gh-review-422-once", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [VERIFIED]}, gh={"review_422_once": True}, expect="ok", comments=0, body_contains="Findings GitHub could not anchor inline")
scenario("gh-reaction-fails", model={"first-pass": [CLEAN]}, gh={"reaction_fail": True}, expect="ok", comments=0)
scenario("gh-head-moves", model={"first-pass": [CLEAN]}, gh={"head_moves_after": 3}, expect="superseded")
scenario("gh-review-422-twice", model={"first-pass": lambda st, p: R(F(0.92, path=st["file_in_prompt"])), "verifier": [VERIFIED]}, gh={"review_422_always": True}, expect="fail", fail_contains="422")
scenario("gh-pr-closed", model={"first-pass": [CLEAN]}, gh={"state": "closed"}, expect="superseded")

# --- incremental re-review (prior DCOIR review exists, new head) ---
scenario("incremental-clean", incremental=True, model={"first-pass": [CLEAN]}, expect="ok", comments=0)
scenario("incremental-near-threshold", incremental=True, model={"first-pass": [R(F(0.62))], "v44-adjudicator": [R(F(0.63), summary="Still uncertain.")], "v44-adjudication-retry": [R(F(0.64), summary="Still uncertain.")]}, expect="ok", comments=0)
scenario("incremental-high", incremental=True, model={"first-pass": [R(F(0.9))], "verifier": [VERIFIED]}, expect="ok", min_comments=1)


def main() -> int:
    if "--scenario" in sys.argv:
        from dcoir_review_end_to_end_replay_runtime import run_one

        name = sys.argv[sys.argv.index("--scenario") + 1]
        run_one(REPO_ROOT, name, SCENARIOS[name])
        return 0
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    failures = run_matrix(os.path.abspath(__file__), SCENARIOS, only=only, jobs=6)
    if failures:
        return 1
    print("dcoir_review_end_to_end_replay_selftest passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
