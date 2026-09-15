from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-readable-config-full-prepublication-validation-016.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-readable-config-full-prepublication-validation-017-inner.py"

source = source_path.read_text(encoding="utf-8")
old = '''    parser_command = (\n        "$ErrorActionPreference='Stop'; "\n        "Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop; "\n        "& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty"\n    )\n'''
new = '''    parser_command = r'''$ErrorActionPreference='Stop';\nfunction Get-FileHash {\n    [CmdletBinding()] param(\n        [Parameter(Mandatory=$true)][string]$LiteralPath,\n        [ValidateSet('SHA256')][string]$Algorithm='SHA256'\n    )\n    $stream = [System.IO.File]::OpenRead($LiteralPath)\n    $sha = [System.Security.Cryptography.SHA256]::Create()\n    try {\n        $hash = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '')\n        [pscustomobject]@{ Algorithm='SHA256'; Hash=$hash; Path=[System.IO.Path]::GetFullPath($LiteralPath) }\n    } finally {\n        $sha.Dispose()\n        $stream.Dispose()\n    }\n}\n& '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowEmpty\n'''\n'''
if source.count(old) != 1:
    raise SystemExit(f"parser command replacement anchor count={source.count(old)}")
source = source.replace(old, new, 1)
source = source.replace(
    'REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-016"',
    'REQUEST_ID = "issue550-pr553-readable-config-full-prepublication-validation-017"',
    1,
)
source = source.replace(
    'print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_016_PASS")',
    'print("ISSUE550_PR553_READABLE_CONFIG_FULL_PREPUBLICATION_VALIDATION_017_PASS")',
    1,
)
inner.write_text(source, encoding="utf-8", newline="\n")

completed = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if completed.returncode:
    raise SystemExit(completed.returncode)
print("FULL_PREPUBLICATION_VALIDATION_017_WRAPPER_PASS")
