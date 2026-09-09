[CmdletBinding()]
param()
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$requestedSha = 'fd7a2d8b5b2b29c4b51ad8240dc01875f15ce68e'
$requestedBranch = 'issue-519-openrouter-run-telemetry'
$expectedValidationCount = 53
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr520-v5-' + $requestedSha.Substring(0,12))
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
    @('OPENROUTER_API_KEY','DCOIR_OPENROUTER_API_KEY','OPENROUTER_MANAGEMENT_KEY','OPENAI_API_KEY','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','DCOIR_GEMINI_API','DCOIR_GEMINI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY') | ForEach-Object { [Environment]::SetEnvironmentVariable($_, $null, 'Process') }
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $pythonFiles = @('.github/dcoir_review/scripts/dcoir_review/entrypoint.py','.github/dcoir_review/scripts/dcoir_review/hardened/part_04a_provider.py','.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py','.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py')
    foreach ($path in $pythonFiles) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "changed Python path missing: $path" } }
    & python -m py_compile @pythonFiles
    if ($LASTEXITCODE -ne 0) { throw 'PR #520 changed Python source/selftest py_compile failed' }
    $commands = @(); $capturing = $false
    foreach ($line in Get-Content -LiteralPath '.github/dcoir_review/openrouter-pr-review-pareto.yml' -Encoding UTF8) {
        if ($line -match '^validation_commands:\s*$') { $capturing = $true; continue }
        if (-not $capturing) { continue }
        if ($line -match '^\s{2}-\s+(.+?)\s*$') { $commands += $Matches[1]; continue }
        if ($line -match '^\S') { break }
    }
    if ($commands.Count -ne $expectedValidationCount) { throw "expected $expectedValidationCount governed validation commands, parsed $($commands.Count)" }
    $index=0
    foreach ($command in $commands) { $index++; Write-Host "[$index/$expectedValidationCount] $command"; & cmd.exe /d /s /c $command; if ($LASTEXITCODE -ne 0) { throw "validation command $index failed with exit code $LASTEXITCODE" } }
    $dirty=@(& git status --porcelain=v1 --untracked-files=all); if ($dirty.Count -gt 0) { throw "validation dirtied detached worktree: $($dirty -join ', ')" }
    @{schema='dcoir.issue519.pr520_exact_head_validation.v5';issue_number=519;pr_number=520;requested_branch=$requestedBranch;requested_head_sha=$requestedSha;remote_branch_head_sha=$remoteSha;actual_head_sha=$actualSha;source_pycompile='pass';changed_python_files_compiled=$pythonFiles.Count;governed_validation_commands=$commands.Count;governed_validation_result='pass';worktree_clean=$true;inference_credentials_removed=$true;live_model_inference=$false;live_dcoir_review_invocation=$false;github_review_publication=$false;pr_source_mutation=$false;ready_transition=$false;merge_performed=$false} | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue519-pr520-exact-head-validation-v5-receipt.json') -Encoding utf8
    Write-Host 'Issue #519 / PR #520 exact-head deterministic validation v5 passed.'
} finally { Set-Location -LiteralPath $repo; if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null } }
