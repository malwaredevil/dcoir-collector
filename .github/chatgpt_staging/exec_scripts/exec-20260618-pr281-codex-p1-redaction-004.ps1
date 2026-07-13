$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ExpectedHead = "94759784627f546c3ae30b3a5521fc59a1925a50"
$PrBranch = "implement-pr-review-command-workflow"
$sourceScript = ".github/chatgpt_staging/exec_scripts/exec-20260618-pr281-codex-p1-redaction-002.ps1"
if (-not (Test-Path $sourceScript)) {
    throw "Expected source script not found: $sourceScript"
}

function Invoke-NativeChecked {
    param(
        [string]$Description,
        [scriptblock]$Command
    )
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Command 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        if ($output) {
            $output | Write-Output
        }
        throw "$Description failed with exit code $exitCode"
    }
    if ($output) {
        $output | Write-Output
    }
}

Invoke-NativeChecked "git fetch PR branch" { git fetch --quiet origin $PrBranch }
$currentHead = (git rev-parse FETCH_HEAD).Trim()
if ($currentHead -ne $ExpectedHead) {
    throw "Unexpected PR branch head. Expected $ExpectedHead but found $currentHead"
}

$workDir = Join-Path $env:RUNNER_TEMP "pr281-redaction-worktree"
if (Test-Path $workDir) {
    Remove-Item -LiteralPath $workDir -Recurse -Force
}
Invoke-NativeChecked "git worktree add PR head" { git worktree add --detach $workDir $ExpectedHead }

$script = Get-Content -Path $sourceScript -Raw
$script = $script.Replace('$ErrorActionPreference = "Stop"', '$ErrorActionPreference = "Continue"')
$script = $script.Replace('git fetch origin $PrBranch', 'git fetch --quiet origin $PrBranch')
$commitAnchor = 'Invoke-Checked "git add" { git add .github/dcoir_review/scripts/openrouter_pr_review.py scripts/openrouter_pr_review_codex_regression_selftest.py }'
$gitIdentity = @'
Invoke-Checked "git configure user email" { git config user.email "chatgpt-exec@users.noreply.github.com" }
Invoke-Checked "git configure user name" { git config user.name "ChatGPT Exec" }
'@
if (-not $script.Contains($commitAnchor)) {
    throw "Commit anchor not found in source script"
}
$script = $script.Replace($commitAnchor, ($gitIdentity + $commitAnchor))

$tempScript = Join-Path $env:RUNNER_TEMP "exec-20260618-pr281-codex-p1-redaction-004-expanded.ps1"
Set-Content -Path $tempScript -Value $script -Encoding UTF8

Push-Location $workDir
try {
    & $tempScript
} finally {
    Pop-Location
}
