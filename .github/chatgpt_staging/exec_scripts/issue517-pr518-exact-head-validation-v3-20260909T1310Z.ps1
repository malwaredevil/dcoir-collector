[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedSha = 'ffee31d2cf9bda3af02cdc9bb199d35111afc89a'
$requestedBranch = 'issue-517-bounded-repair-tail'
$expectedValidationCount = 52
$expectedChangedPythonCount = 5
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr518-v3-' + $requestedSha.Substring(0,12))

try {
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }

    $remoteLine = (& git -C $repo ls-remote origin "refs/heads/$requestedBranch" | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "could not resolve remote branch $requestedBranch" }
    $remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
    if ($remoteSha -ne $requestedSha) { throw "PR branch head moved before validation: requested=$requestedSha remote=$remoteSha" }

    & git -C $repo fetch --no-tags origin $requestedSha
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed with exit code $LASTEXITCODE" }
    & git -C $repo worktree add --detach $worktree $requestedSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed with exit code $LASTEXITCODE" }

    Set-Location -LiteralPath $worktree
    $actualSha = (& git rev-parse HEAD).Trim()
    if ($actualSha -ne $requestedSha) { throw "exact-head mismatch: requested=$requestedSha actual=$actualSha" }

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
    ) | ForEach-Object { [Environment]::SetEnvironmentVariable($_, $null, 'Process') }
    $env:PYTHONDONTWRITEBYTECODE = '1'

    $pythonFiles = @(
        '.github/dcoir_review/scripts/dcoir_review/entrypoint.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_selftest.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py'
    )
    if ($pythonFiles.Count -ne $expectedChangedPythonCount) { throw "expected $expectedChangedPythonCount changed Python files, found $($pythonFiles.Count)" }
    & python3 -m py_compile @pythonFiles
    if ($LASTEXITCODE -ne 0) { throw 'PR #518 changed Python source/selftest py_compile failed' }

    $commands = @()
    $capturing = $false
    foreach ($line in Get-Content -LiteralPath '.github/dcoir_review/openrouter-pr-review-pareto.yml' -Encoding UTF8) {
        if ($line -match '^validation_commands:\s*$') { $capturing = $true; continue }
        if (-not $capturing) { continue }
        if ($line -match '^\s{2}-\s+(.+?)\s*$') { $commands += $Matches[1]; continue }
        if ($line -match '^\S') { break }
    }
    if ($commands.Count -ne $expectedValidationCount) { throw "expected $expectedValidationCount governed validation commands, parsed $($commands.Count)" }

    $index = 0
    foreach ($command in $commands) {
        $index++
        Write-Host "[$index/$expectedValidationCount] $command"
        & cmd.exe /d /s /c $command
        if ($LASTEXITCODE -ne 0) { throw "validation command $index failed with exit code $LASTEXITCODE" }
    }

    $dirty = @(& git status --porcelain=v1 --untracked-files=all)
    if ($dirty.Count -gt 0) { throw "validation dirtied detached worktree: $($dirty -join ', ')" }

    @{
        schema = 'dcoir.issue517.pr518_exact_head_validation.v1'
        validation_attempt = 'v3'
        issue_number = 517
        pr_number = 518
        requested_branch = $requestedBranch
        requested_head_sha = $requestedSha
        remote_branch_head_sha = $remoteSha
        actual_head_sha = $actualSha
        source_pycompile = 'pass'
        changed_python_files_compiled = $pythonFiles.Count
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
    } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue517-pr518-exact-head-validation-v3-receipt.json') -Encoding utf8

    Write-Host 'Issue #517 / PR #518 exact-head deterministic validation v3 passed.'
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
