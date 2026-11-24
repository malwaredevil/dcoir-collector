from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-review-config-validation-001.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-canonical-review-config-validation-002-inner.py"

source = source_path.read_text(encoding="utf-8")
replacements = {
    'EXPECTED_HEAD = "1210e9689200c7a97a8b48c0d6a1dc792675700d"':
        'EXPECTED_HEAD = "f10aa75bbdf54110329409371d7aa86404b6ba65"',
    'EXPECTED_TREE = "72b50e19e9da8eaaf566a79726a6615442c9c94c"':
        'EXPECTED_TREE = "91021d85eec18569fe52492c13959cd8b28a0331"',
    'REQUEST_ID = "issue550-pr553-canonical-review-config-validation-001"':
        'REQUEST_ID = "issue550-pr553-canonical-review-config-validation-002"',
    'TERMINAL = "ISSUE550_PR553_CANONICAL_REVIEW_CONFIG_VALIDATION_001_PASS"':
        'TERMINAL = "ISSUE550_PR553_CANONICAL_REVIEW_CONFIG_VALIDATION_002_PASS"',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit(f"exact-head replacement anchor count for {old!r}: {source.count(old)}")
    source = source.replace(old, new, 1)
inner.write_text(source, encoding="utf-8", newline="\n")
compile(inner.read_text(encoding="utf-8"), str(inner), "exec")
cp = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if cp.returncode:
    raise SystemExit(cp.returncode)
print("CANONICAL_REVIEW_CONFIG_VALIDATION_002_WRAPPER_PASS")
