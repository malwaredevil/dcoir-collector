from __future__ import annotations

import ast
import base64
import gzip
import hashlib
import os
import runpy
import subprocess
from pathlib import Path

EXACT_HEAD = "e4bdc91adb5e31e78a9356ed15384dd83aa08c7b"
EXACT_PARENT = "e12e776ef4fc1b06bb01158b9f22d56db4a3f513"
EXPECTED_PATCH_SHA = "7c4ad7373ceb9beb080f65db794f89b02ecd13b46e6130217ac4aa6da9b4f5cf"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
TERMINAL = "ISSUE550_PR553_PROVIDER_REVIEW_GHAS_FOLLOWUP_EXACT_HEAD_001_PASS"
repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
prepub_candidates = (
    repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-provider-review-ghas-followup-prepublication-001.py",
    repo / ".git/provider-review-ghas-followup-prepublication.py",
)
prepub = next((path for path in prepub_candidates if path.is_file()), None)
if prepub is None:
    raise RuntimeError("prepublication validator source not found")
tree = ast.parse(prepub.read_text(encoding="utf-8"))
patch_b64 = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PATCH_GZIP_B64" for t in node.targets):
        patch_b64 = ast.literal_eval(node.value)
        break
if not isinstance(patch_b64, str):
    raise RuntimeError("embedded prepublication patch not found")
patch = gzip.decompress(base64.b64decode("".join(patch_b64.split())))
if hashlib.sha256(patch).hexdigest() != EXPECTED_PATCH_SHA:
    raise RuntimeError("embedded patch hash drift")
subprocess.run(["git", "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}"], cwd=repo, check=True)
remote_head = subprocess.check_output(["git", "rev-parse", f"refs/remotes/origin/{BRANCH}"], cwd=repo, text=True).strip()
if remote_head != EXACT_HEAD:
    raise RuntimeError(f"remote PR head drift: {remote_head}")
parent = subprocess.check_output(["git", "rev-parse", f"{EXACT_HEAD}^"], cwd=repo, text=True).strip()
if parent != EXACT_PARENT:
    raise RuntimeError(f"exact parent drift: {parent}")
commit_patch = subprocess.check_output(["git", "diff", "--binary", EXACT_PARENT, EXACT_HEAD, "--"], cwd=repo)
if commit_patch != patch:
    raise RuntimeError(f"commit/frozen patch mismatch: {hashlib.sha256(commit_patch).hexdigest()}")
exact_tree = subprocess.check_output(["git", "rev-parse", f"{EXACT_HEAD}^{{tree}}"], cwd=repo, text=True).strip()
print(f"EXACT_HEAD={EXACT_HEAD}")
print(f"EXACT_HEAD_TREE={exact_tree}")
print(f"EXACT_PARENT={EXACT_PARENT}")
print(f"COMMIT_PATCH_SHA256={hashlib.sha256(commit_patch).hexdigest()}")
runpy.run_path(str(prepub), run_name="__main__")
print(TERMINAL)
