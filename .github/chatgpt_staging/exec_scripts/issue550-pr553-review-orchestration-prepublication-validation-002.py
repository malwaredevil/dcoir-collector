from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-review-orchestration-prepublication-validation-001.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-review-orchestration-prepublication-validation-002-inner.py"

source = source_path.read_text(encoding="utf-8")
replacements = {
    'REQUEST_ID = "issue550-pr553-review-orchestration-prepublication-validation-001"':
        'REQUEST_ID = "issue550-pr553-review-orchestration-prepublication-validation-002"',
    'TERMINAL = "ISSUE550_PR553_REVIEW_ORCHESTRATION_PREPUBLICATION_VALIDATION_001_PASS"':
        'TERMINAL = "ISSUE550_PR553_REVIEW_ORCHESTRATION_PREPUBLICATION_VALIDATION_002_PASS"',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit(f"replacement anchor count for {old!r}: {source.count(old)}")
    source = source.replace(old, new, 1)

old_parser = 'line.strip()[3:]'
if source.count(old_parser) != 2:
    raise SystemExit(f"porcelain parser anchor count={source.count(old_parser)}")
source = source.replace(old_parser, 'line[3:].strip()')

inner.write_text(source, encoding="utf-8", newline="\n")
compile(inner.read_text(encoding="utf-8"), str(inner), "exec")
cp = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if cp.returncode:
    raise SystemExit(cp.returncode)
print("REVIEW_ORCHESTRATION_PREPUBLICATION_VALIDATION_002_WRAPPER_PASS")
