from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_PATCH_SHA = "2eec4439b09fd3a20fef8e78f8a502f4bfae03930b0c4c118c8b27a18d178806"
EXPECTED_METRICS = {
    "multi_stage_callable_chains": "31",
    "superseded_callable_installations": "162",
    "stored_original_callable_attributes": "133",
    "duplicate_function_names": "122",
    "final_numbered_owned_callables": "89",
}

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-readable-preview-010.py"
audit_source = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-function-ownership-audit-001.ps1"
patch = downloads / "issue550-pr553-canonical-config-readable-preview-010.patch"
request_id = "issue550-pr553-readable-config-transformed-ownership-audit-011"
inner = downloads / f"{request_id}.ps1"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

result = subprocess.run([sys.executable, str(preview)], cwd=repo, text=True)
if result.returncode:
    raise SystemExit(result.returncode)
if not patch.is_file():
    raise SystemExit("readable canonical-config patch missing after preview")
patch_sha = hashlib.sha256(patch.read_bytes()).hexdigest()
if patch_sha != EXPECTED_PATCH_SHA:
    raise SystemExit(f"readable patch drift: expected {EXPECTED_PATCH_SHA}, observed {patch_sha}")

text = audit_source.read_text(encoding="utf-8")
old_request = "$requestId = 'issue550-pr553-function-ownership-audit-001'"
new_request = f"$requestId = '{request_id}'"
if old_request not in text:
    raise SystemExit("ownership audit request id anchor missing")
text = text.replace(old_request, new_request, 1)

anchor = "& git -C $repo worktree add --detach $worktree $expectedHead\nif ($LASTEXITCODE -ne 0) { throw 'Unable to create isolated worktree' }\n"
insert = anchor + "\n$patchPath = Join-Path $downloads 'issue550-pr553-canonical-config-readable-preview-010.patch'\n& git -C $worktree apply --check $patchPath\nif ($LASTEXITCODE -ne 0) { throw 'Readable canonical config patch failed git apply --check' }\n& git -C $worktree apply $patchPath\nif ($LASTEXITCODE -ne 0) { throw 'Readable canonical config patch failed to apply' }\nif (-not (Test-Path -LiteralPath (Join-Path $worktree '.github/dcoir_review/scripts/dcoir_review/review_config.py') -PathType Leaf)) { throw 'Canonical review_config.py missing after readable transformed patch apply' }\n"
if anchor not in text:
    raise SystemExit("ownership audit worktree anchor missing")
text = text.replace(anchor, insert, 1)

old_dirty = "    $dirty = @(& git status --porcelain)\n    if ($dirty.Count -ne 0) { throw \"Isolated worktree dirty after audit: $($dirty -join ', ')\" }"
new_dirty = "    $dirty = @(& git status --porcelain)\n    if ($dirty.Count -eq 0) { throw 'Readable transformed audit worktree unexpectedly clean' }\n    $reviewConfigStatus = @($dirty | Where-Object { $_ -match 'dcoir_review/review_config\\.py$' })\n    if ($reviewConfigStatus.Count -ne 1) { throw \"Readable transformed audit status did not include exactly one canonical review_config.py entry: $($dirty -join ', ')\" }"
if old_dirty not in text:
    raise SystemExit("ownership audit dirty-worktree anchor missing")
text = text.replace(old_dirty, new_dirty, 1)
text = text.replace(
    "ISSUE550_PR553_FUNCTION_OWNERSHIP_AUDIT_001_PASS",
    "ISSUE550_PR553_READABLE_CONFIG_TRANSFORMED_OWNERSHIP_AUDIT_011_PASS",
    1,
)
inner.write_text(text, encoding="utf-8", newline="\n")

ps = os.environ.get("WINDIR", r"C:\Windows") + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
run = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(inner)], cwd=repo, text=True)
if run.returncode:
    raise SystemExit(run.returncode)

summary = downloads / f"{request_id}-summary.txt"
if not summary.is_file():
    raise SystemExit("readable transformed ownership summary missing")
lines = summary.read_text(encoding="utf-8").splitlines()
observed = {}
for line in lines:
    if "=" in line:
        key, value = line.split("=", 1)
        observed[key] = value
for key, expected in EXPECTED_METRICS.items():
    if observed.get(key) != expected:
        raise SystemExit(f"ownership metric drift for {key}: expected {expected}, observed {observed.get(key)!r}")
with summary.open("a", encoding="utf-8") as handle:
    handle.write("readable_transformed_preview=true\n")
    handle.write(f"source_patch_sha256={patch_sha}\n")
    handle.write("structural_metrics_preserved=true\n")
print(summary.read_text(encoding="utf-8"), end="")
print("READABLE_CONFIG_TRANSFORMED_OWNERSHIP_AUDIT_WRAPPER_PASS")
