[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedSha = '168b66a43620d5b68b124d889ef280e49b36df5e'
$expectedValidationCount = 44
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr486-' + $requestedSha.Substring(0,12))

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

    python3 -m py_compile `
        .github/dcoir_review/scripts/dcoir_review_first_pass_candidate_eval.py `
        .github/dcoir_review/scripts/dcoir_review_first_pass_candidate_eval_selftest.py
    if ($LASTEXITCODE -ne 0) { throw 'candidate harness py_compile failed' }

    python3 .github/dcoir_review/scripts/dcoir_review_first_pass_candidate_eval_selftest.py
    if ($LASTEXITCODE -ne 0) { throw 'candidate harness deterministic selftest failed' }

    $planPath = Join-Path $downloads 'issue485-pr486-candidate-eval-plan.json'
    python3 .github/dcoir_review/scripts/dcoir_review_first_pass_candidate_eval.py --candidate all --output $planPath
    if ($LASTEXITCODE -ne 0) { throw 'candidate harness plan mode failed' }
    $plan = Get-Content -LiteralPath $planPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$plan.mode -ne 'plan-no-network') { throw "unexpected plan mode: $($plan.mode)" }
    if ([int]$plan.network_calls -ne 0) { throw "plan mode reported network calls: $($plan.network_calls)" }
    if ([int]$plan.case_counts.planned_total_requests -ne 42) {
        throw "expected 42 planned candidate requests, got $($plan.case_counts.planned_total_requests)"
    }

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
        schema = 'dcoir.issue485.pr486_exact_head_validation.v1'
        issue_number = 485
        pr_number = 486
        requested_head_sha = $requestedSha
        actual_head_sha = $actualSha
        candidate_harness_pycompile = 'pass'
        candidate_harness_selftest = 'pass'
        candidate_plan_mode = 'pass'
        candidate_plan_network_calls = 0
        candidate_plan_request_count = 42
        governed_validation_commands = $commands.Count
        governed_validation_result = 'pass'
        worktree_clean = $true
        inference_credentials_removed = $true
        live_model_inference = $false
        live_dcoir_review_invocation = $false
        github_review_publication = $false
    } | ConvertTo-Json -Depth 4 |
        Out-File -LiteralPath (Join-Path $downloads 'issue485-pr486-exact-head-validation-receipt.json') -Encoding utf8

    Write-Host 'Issue #485 / PR #486 exact-head deterministic validation passed.'
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }
}
