from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-full-prepublication-validation-012.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-readable-config-full-prepublication-validation-019-inner.py"

source = source_path.read_text(encoding="utf-8")
replacements = {
    'EXPECTED_PATCH_SHA = "2eec4439b09fd3a20fef8e78f8a502f4bfae03930b0c4c118c8b27a18d178806"':
        'EXPECTED_PATCH_SHA = "923ffd839b1bacb4cf2a2801a0916bae783d7470e2c320cf1804740b48302cb1"',
    'REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-012"':
        'REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-019"',
    'preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-readable-preview-010.py"':
        'preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-strong-loader-guard-preview-013.py"',
    'patch = downloads / "issue550-pr553-canonical-config-readable-preview-010.patch"':
        'patch = downloads / "issue550-pr553-readable-config-strong-loader-guard-preview-013.patch"',
    'print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_012_PASS")':
        'print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_019_PASS")',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit(f"full-validation replacement anchor count for {old!r}: {source.count(old)}")
    source = source.replace(old, new, 1)

path_anchor = '    run("git", "apply", str(patch), cwd=worktree)\n\n    status_lines = check_output("git", "status", "--porcelain", cwd=worktree).splitlines()\n'
path_injected = (
    '    run("git", "apply", str(patch), cwd=worktree)\n'
    '    scripts_path = worktree / ".github" / "dcoir_review" / "scripts"\n'
    '    prior_pythonpath = os.environ.get("PYTHONPATH", "")\n'
    '    os.environ["PYTHONPATH"] = str(scripts_path) + (os.pathsep + prior_pythonpath if prior_pythonpath else "")\n\n'
    '    status_lines = check_output("git", "status", "--porcelain", cwd=worktree).splitlines()\n'
)
if source.count(path_anchor) != 1:
    raise SystemExit(f"PYTHONPATH injection anchor count={source.count(path_anchor)}")
source = source.replace(path_anchor, path_injected, 1)

parser_old = '''    parser = run(\n        str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",\n        ".github/dcoir_review/scripts/validate-windows-powershell-51.ps1", "-AllowEmpty",\n        cwd=worktree,\n    )\n'''
powershell_command = (
    "$ErrorActionPreference='Stop'; "
    "function Get-FileHash { "
    "[CmdletBinding()] param([Parameter(Mandatory=$true)][string]$LiteralPath,[ValidateSet('SHA256')][string]$Algorithm='SHA256'); "
    "$stream=[System.IO.File]::OpenRead($LiteralPath); $sha=[System.Security.Cryptography.SHA256]::Create(); "
    "try { $hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-',''); "
    "[pscustomobject]@{Algorithm='SHA256';Hash=$hash;Path=[System.IO.Path]::GetFullPath($LiteralPath)} } "
    "finally { $sha.Dispose(); $stream.Dispose() } }; "
    "& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty"
)
parser_new = (
    "    parser_command = " + repr(powershell_command) + "\n"
    "    parser = run(\n"
    "        str(powershell), \"-NoProfile\", \"-ExecutionPolicy\", \"Bypass\", \"-Command\", parser_command,\n"
    "        cwd=worktree,\n"
    "    )\n"
)
if source.count(parser_old) != 1:
    raise SystemExit(f"native parser replacement anchor count={source.count(parser_old)}")
source = source.replace(parser_old, parser_new, 1)
inner.write_text(source, encoding="utf-8", newline="\n")
compile(inner.read_text(encoding="utf-8"), str(inner), "exec")

completed = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if completed.returncode:
    raise SystemExit(completed.returncode)
print("FULL_PREPUBLICATION_VALIDATION_019_WRAPPER_PASS")
