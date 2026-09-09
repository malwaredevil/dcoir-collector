[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedSha = '0368db89878e2380410490ea17a475ca9720bfa4'
$requestedBranch = 'issue-519-openrouter-run-telemetry'
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-issue519-targeted-' + $requestedSha.Substring(0,12))

try {
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }

    $remoteLine = (& git -C $repo ls-remote origin "refs/heads/$requestedBranch" | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "could not resolve remote branch $requestedBranch" }
    $remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
    if ($remoteSha -ne $requestedSha) { throw "issue #519 branch moved before validation: requested=$requestedSha remote=$remoteSha" }

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
        '.github/dcoir_review/scripts/dcoir_review/hardened/part_04a_provider.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    )
    & python3 -m py_compile @pythonFiles
    if ($LASTEXITCODE -ne 0) { throw 'issue #519 changed Python py_compile failed' }

    $commands = @(
        'python3 .github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v47_selftest.py',
        'python3 .github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_selftest.py',
        'python3 .github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py',
        'python3 .github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py',
        'python3 .github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py',
        'python3 .github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py',
        'python3 .github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py'
    )
    $index = 0
    foreach ($command in $commands) {
        $index++
        Write-Host "[$index/$($commands.Count)] $command"
        & cmd.exe /d /s /c $command
        if ($LASTEXITCODE -ne 0) { throw "targeted validation command $index failed with exit code $LASTEXITCODE" }
    }

    $dirty = @(& git status --porcelain=v1 --untracked-files=all)
    if ($dirty.Count -gt 0) { throw "targeted validation dirtied detached worktree: $($dirty -join ', ')" }

    @{
        schema = 'dcoir.issue519.targeted_validation.v1'
        issue_number = 519
        requested_branch = $requestedBranch
        requested_head_sha = $requestedSha
        remote_branch_head_sha = $remoteSha
        actual_head_sha = $actualSha
        changed_python_files_compiled = $pythonFiles.Count
        targeted_validation_commands = $commands.Count
        targeted_validation_result = 'pass'
        worktree_clean = $true
        inference_credentials_removed = $true
        live_model_inference = $false
        live_dcoir_review_invocation = $false
        github_review_publication = $false
        pr_source_mutation = $false
        ready_transition = $false
        merge_performed = $false
    } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue519-targeted-validation-v1-receipt.json') -Encoding utf8

    Write-Host 'Issue #519 targeted deterministic validation v1 passed.'
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
