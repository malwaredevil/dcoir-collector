$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptPath = '.github/chatgpt_staging/exec_scripts/dcoir-review-fix-guidance-normalization-20260627T123500Z.ps1'
$env:PYTHONPATH = (Resolve-Path -LiteralPath 'scripts').Path
& pwsh -NoProfile -ExecutionPolicy Bypass -File $scriptPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
