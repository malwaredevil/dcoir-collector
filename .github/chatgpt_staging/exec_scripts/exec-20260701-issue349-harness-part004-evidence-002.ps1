$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$RequestId = 'exec-20260701-issue349-harness-part004-evidence-002'
$InnerScriptRel = '.github/chatgpt_staging/exec_scripts/exec-20260701-issue349-harness-part004-evidence-001.ps1'
$TargetBranch = 'codex/349-workflow-file-modularization'
$ExpectedHead = '51baee007cf4c66bbd95fe849f349ddabf817a89'
$RepoRoot = (Get-Location).Path
$WorktreePath = Join-Path $env:RUNNER_TEMP $RequestId

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$Description,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    Write-Host "==> $Description"
    $output = & $Command 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($output) {
        $output | Write-Output
    }
    if ($exitCode -ne 0) {
        throw "$Description failed with exit code $exitCode"
    }
}

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git config core.autocrlf false
git config core.eol lf
git config core.longpaths true

$innerScript = Join-Path $RepoRoot ($InnerScriptRel -replace '/', [IO.Path]::DirectorySeparatorChar)
if (-not (Test-Path -LiteralPath $innerScript -PathType Leaf)) {
    throw "Inner script not found: $InnerScriptRel"
}

Invoke-Checked 'Fetch target PR branch' { git fetch --no-tags origin "refs/heads/$TargetBranch`:refs/remotes/origin/$TargetBranch" }
$actualHead = (git rev-parse "origin/$TargetBranch").Trim()
if ($actualHead -ne $ExpectedHead) {
    throw "Target branch head mismatch before isolated retry. Expected $ExpectedHead but found $actualHead."
}

Invoke-Checked 'Create isolated target branch worktree' {
    git worktree add -B issue349-harness-part004-evidence-refresh-002 $WorktreePath "origin/$TargetBranch"
}

Push-Location $WorktreePath
try {
    Invoke-Checked 'Run evidence refresh inside isolated worktree' { & $innerScript }
}
finally {
    Pop-Location
}

Invoke-Checked 'Fetch refreshed target PR branch' { git fetch --no-tags origin "refs/heads/$TargetBranch`:refs/remotes/origin/$TargetBranch" }
$newHead = (git rev-parse "origin/$TargetBranch").Trim()
if ($newHead -eq $ExpectedHead) {
    throw "Evidence refresh did not advance $TargetBranch beyond $ExpectedHead."
}

$summaryDir = Join-Path '.github/chatgpt_staging/status_reports/chatgpt-exec' $RequestId
New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
$summaryPath = Join-Path $summaryDir 'isolated_worktree_retry_summary.json'
[ordered]@{
    schema = 'dcoir.chatgpt_staging.exec_summary.v1'
    request_id = $RequestId
    target_branch = $TargetBranch
    expected_input_head = $ExpectedHead
    pushed_head = $newHead
    isolation = 'target branch was mutated from a temporary git worktree; primary workflow checkout remained on main'
    reused_script = $InnerScriptRel
    validation_note = 'inner script runs the evidence generation, hard assertions, no-write checks, assembly parity unit test, commit, and push'
    created_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
} | ConvertTo-Json -Depth 8 | Out-File -FilePath $summaryPath -Encoding utf8
Write-Host "Wrote tracked summary $summaryPath"
