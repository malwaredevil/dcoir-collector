$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260625-pr312-dcoir-review-fixes-002.ps1"
if (-not (Test-Path -LiteralPath $sourceScript -PathType Leaf)) {
    throw "Expected source script not found: $sourceScript"
}

$script = Get-Content -LiteralPath $sourceScript -Raw
$script = $script.Replace('$ErrorActionPreference = "Stop"', '$ErrorActionPreference = "Continue"')
$script = $script.Replace('git switch -C main origin/main', 'git switch --quiet -C main origin/main')

$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260625-pr312-dcoir-review-fixes-003-expanded.ps1"
Set-Content -LiteralPath $tempScript -Value $script -Encoding UTF8
& $tempScript
