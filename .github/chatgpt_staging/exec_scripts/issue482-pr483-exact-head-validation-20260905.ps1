[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedSha = '5bed144002cd4d36278f94174e1e444ab00aadae'
$expectedValidationCount = 44
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr483-' + $requestedSha.Substring(0,12))

try {
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }

    & git -C $repo fetch --no-tags origin $requestedSha
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed with exit code $LASTEXITCODE" }

    & git -C $repo worktree add --detach $worktree $requestedSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed with exit code $LASTEXITCODE" }

    Set-Location -LiteralPath $worktree
    $actualSha = (& git rev-parse HEAD).Trim()
    if ($actualSha -ne $requestedSha) {
        throw "exact-head mismatch: requested=$requestedSha actual=$actualSha"
    }

    @(
        'OPENROUTER_API_KEY',
        'DCOIR_OPENROUTER_API_KEY',
        'OPENROUTER_MANAGEMENT_KEY',
        'OPENAI_API_KEY',
        'DCOIR_OPENAI_API_KEY',
        'DCOIR_GEMINI_API'
    ) | ForEach-Object {
        [Environment]::SetEnvironmentVariable($_, $null, 'Process')
    }
    $env:PYTHONDONTWRITEBYTECODE = '1'

    python3 -m py_compile .github/dcoir_review/scripts/dcoir_review/hardened/part_04a_provider.py .github/dcoir_review/scripts/dcoir_review/selftests/pareto_context_selftest/part_05.py
    if ($LASTEXITCODE -ne 0) { throw 'provider/selftest py_compile failed' }

    python3 .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py
    if ($LASTEXITCODE -ne 0) { throw 'focused Pareto/provider selftest failed' }

    $commands = @()
    $capturing = $false
    foreach ($line in Get-Content -LiteralPath '.github/dcoir_review/openrouter-pr-review-pareto.yml' -Encoding UTF8) {
        if ($line -match '^validation_commands:\s*$') { $capturing = $true; continue }
        if (-not $capturing) { continue }
        if ($line -match '^\s{2}-\s+(.+?)\s*$') { $commands += $Matches[1]; continue }
        if ($line -match '^\S') { break }
    }

    if ($commands.Count -ne $expectedValidationCount) {
        throw "expected $expectedValidationCount governed validation commands, parsed $($commands.Count)"
    }

    $index = 0
    foreach ($command in $commands) {
        $index++
        Write-Host "[$index/$expectedValidationCount] $command"
        & cmd.exe /d /s /c $command
        if ($LASTEXITCODE -ne 0) {
            throw "validation command $index failed with exit code $LASTEXITCODE"
        }
    }

    $dirty = @(& git status --porcelain=v1 --untracked-files=all)
    if ($dirty.Count -gt 0) {
        throw "validation dirtied detached worktree: $($dirty -join ', ')"
    }

    @{
        schema = 'dcoir.issue482.pr483_exact_head_validation.v1'
        issue_number = 482
        pr_number = 483
        requested_head_sha = $requestedSha
        actual_head_sha = $actualSha
        provider_pycompile = 'pass'
        focused_provider_selftest = 'pass'
        governed_validation_commands = $commands.Count
        governed_validation_result = 'pass'
        worktree_clean = $true
        live_model_inference = $false
        live_dcoir_review_invocation = $false
    } | ConvertTo-Json -Depth 4 |
        Out-File -LiteralPath (Join-Path $downloads 'issue482-pr483-exact-head-validation-receipt.json') -Encoding utf8

    Write-Host 'Issue #482 / PR #483 exact-head deterministic validation passed.'
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }
}
