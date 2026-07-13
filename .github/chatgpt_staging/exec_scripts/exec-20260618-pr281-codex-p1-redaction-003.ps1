$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1"
if (-not (Test-Path $sourceScript)) {
    throw "Expected source script not found: $sourceScript"
}

$script = Get-Content -Path $sourceScript -Raw
$script = $script.Replace('$ErrorActionPreference = "Stop"', '$ErrorActionPreference = "Continue"')
$script = $script.Replace('git fetch origin $PrBranch', 'git fetch --quiet origin $PrBranch')

$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260618-pr281-codex-p1-redaction-003-expanded.ps1"
Set-Content -Path $tempScript -Value $script -Encoding UTF8
& $tempScript
