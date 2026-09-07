[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedSha = '2dc0633e6bae9fc9f11b89e29498c83df8fad2d0'
$expectedValidationCount = 47
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr493-rerun2-' + $requestedSha.Substring(0,12))

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
        'DCOIR_OPENAI_PROJECT_ID',
        'DCOIR_GEMINI_API',
        'DCOIR_GEMINI_API_KEY',
        'GEMINI_API_KEY',
        'GOOGLE_API_KEY'
    ) | ForEach-Object {
        [Environment]::SetEnvironmentVariable($_, $null, 'Process')
    }
    $env:PYTHONDONTWRITEBYTECODE = '1'

    python3 -m py_compile `
        .github/dcoir_review/scripts/dcoir_review/pareto_context/credit_aware_concurrency.py `
        .github/dcoir_review/scripts/dcoir_review/pareto_context/part_05a_hybrid_review.py `
        .github/dcoir_review/scripts/dcoir_review_credit_aware_concurrency_v49_selftest.py `
        .github/dcoir_review/scripts/dcoir_review_per_file_coverage_recovery_v40_selftest.py
    if ($LASTEXITCODE -ne 0) { throw 'PR #493 credit-aware source/selftest py_compile failed' }

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
        schema = 'dcoir.issue457.pr493_exact_head_validation.v1'
        issue_number = 457
        pr_number = 493
        validation_attempt = 'rerun2'
        requested_head_sha = $requestedSha
        actual_head_sha = $actualSha
        source_pycompile = 'pass'
        governed_validation_commands = $commands.Count
        governed_validation_result = 'pass'
        worktree_clean = $true
        inference_credentials_removed = $true
        live_model_inference = $false
        live_dcoir_review_invocation = $false
        github_review_publication = $false
        pr_source_mutation = $false
        ready_transition = $false
        merge_performed = $false
    } | ConvertTo-Json -Depth 4 |
        Out-File -LiteralPath (Join-Path $downloads 'issue457-pr493-exact-head-validation-rerun2-receipt.json') -Encoding utf8

    Write-Host 'Issue #457 / PR #493 exact-head deterministic validation rerun2 passed.'
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }
}
