from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-review-orchestration-prepublication-validation-002.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-review-orchestration-prepublication-validation-003-wrapper-inner.py"

source = source_path.read_text(encoding="utf-8")
replacements = {
    'issue550-pr553-review-orchestration-prepublication-validation-002':
        'issue550-pr553-review-orchestration-prepublication-validation-003',
}
for old, new in replacements.items():
    if old not in source:
        raise SystemExit(f"missing wrapper replacement anchor: {old}")
    source = source.replace(old, new)

# The 002 wrapper generates an inner validator from 001. Extend that generated
# source transformation so git-status porcelain parsing consumes raw stdout;
# the generic out() helper strips leading whitespace from the first status row.
needle = "source = source.replace(old_parser, 'line[3:].strip()')\n"
insert = """source = source.replace(old_parser, 'line[3:].strip()')
status_out = 'out(\\\"git\\\", \\\"status\\\", \\\"--porcelain\\\", cwd=worktree).splitlines()'
status_raw = 'run(\\\"git\\\", \\\"status\\\", \\\"--porcelain\\\", cwd=worktree).stdout.splitlines()'
if source.count(status_out) != 2:
    raise SystemExit(f\"porcelain stdout anchor count={source.count(status_out)}\")
source = source.replace(status_out, status_raw)
"""
if source.count(needle) != 1:
    raise SystemExit(f"wrapper insertion anchor count={source.count(needle)}")
source = source.replace(needle, insert, 1)

inner.write_text(source, encoding="utf-8", newline="\n")
compile(inner.read_text(encoding="utf-8"), str(inner), "exec")
cp = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if cp.returncode:
    raise SystemExit(cp.returncode)
print("REVIEW_ORCHESTRATION_PREPUBLICATION_VALIDATION_003_WRAPPER_PASS")
