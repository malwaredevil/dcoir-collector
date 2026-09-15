from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-full-prepublication-validation-012.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-readable-config-full-prepublication-validation-014-inner.py"

source = source_path.read_text(encoding="utf-8")
replacements = {
    'EXPECTED_PATCH_SHA = "2eec4439b09fd3a20fef8e78f8a502f4bfae03930b0c4c118c8b27a18d178806"':
        'EXPECTED_PATCH_SHA = "923ffd839b1bacb4cf2a2801a0916bae783d7470e2c320cf1804740b48302cb1"',
    'REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-012"':
        'REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-014"',
    'preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-readable-preview-010.py"':
        'preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-strong-loader-guard-preview-013.py"',
    'patch = downloads / "issue550-pr553-canonical-config-readable-preview-010.patch"':
        'patch = downloads / "issue550-pr553-readable-config-strong-loader-guard-preview-013.patch"',
    'print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_012_PASS")':
        'print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_014_PASS")',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit(f"full-validation replacement anchor count for {old!r}: {source.count(old)}")
    source = source.replace(old, new, 1)

anchor = '    run("git", "apply", str(patch), cwd=worktree)\n\n    status_lines = check_output("git", "status", "--porcelain", cwd=worktree).splitlines()\n'
injected = (
    '    run("git", "apply", str(patch), cwd=worktree)\n'
    '    scripts_path = worktree / ".github" / "dcoir_review" / "scripts"\n'
    '    prior_pythonpath = os.environ.get("PYTHONPATH", "")\n'
    '    os.environ["PYTHONPATH"] = str(scripts_path) + (os.pathsep + prior_pythonpath if prior_pythonpath else "")\n\n'
    '    status_lines = check_output("git", "status", "--porcelain", cwd=worktree).splitlines()\n'
)
if source.count(anchor) != 1:
    raise SystemExit(f"PYTHONPATH injection anchor count={source.count(anchor)}")
source = source.replace(anchor, injected, 1)
inner.write_text(source, encoding="utf-8", newline="\n")

completed = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if completed.returncode:
    raise SystemExit(completed.returncode)
print("FULL_PREPUBLICATION_VALIDATION_014_WRAPPER_PASS")
