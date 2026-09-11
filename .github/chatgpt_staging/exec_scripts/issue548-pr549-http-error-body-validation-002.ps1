$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$requestId = 'issue548-pr549-http-error-body-validation-002'
$targetBranch = 'fix/issue-548-provider-transport-retry'
$expectedHead = '535a9ed0dcc439342afdd313e6c792d3f4dbf382'
$reviewedBase = 'd7b44e227176cdbbd90ff06d6f684d1b9f95b0d4'
$expectedCommandCount = 58
$repoRoot = (Get-Location).Path
$worktree = Join-Path $env:RUNNER_TEMP $requestId
$summaryDir = Join-Path $repoRoot ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
$summaryPath = Join-Path $summaryDir 'validation-summary.md'
$result = 'failure'
$failureMessage = ''
$remoteHead = ''
$mergeBase = ''
$successfulCommandCount = 0
$compiledPythonCount = 0
$credentialsRemoved = $false
$prDiffCheckPassed = $false
$finalWorktreeClean = $false

$credentialNames = @(
    'DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY',
    'OPENROUTER_API_KEY','DCOIR_OPENROUTER_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','GEMINI_API_KEY',
    'DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN'
)

$changedPythonFiles = @(
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py',
    '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v58.py'
)

function Invoke-CheckedNative {
    param([Parameter(Mandatory=$true)][string]$Label,[Parameter(Mandatory=$true)][scriptblock]$Action)
    Write-Host "==> $Label"
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

function Write-ValidationSummary {
    New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
    $safeFailure = ($failureMessage -replace '[\r\n]+',' ').Trim()
    @(
        '# PR #549 HTTPError-body status-policy exact-head validation','',
        "- request_id: $requestId",
        "- result: $result",
        "- target_branch: $targetBranch",
        "- expected_head_sha: $expectedHead",
        "- observed_remote_head_sha: $remoteHead",
        "- reviewed_base_sha: $reviewedBase",
        "- reviewed_base_merge_base_with_head: $mergeBase",
        "- changed_python_files_expected: $($changedPythonFiles.Count)",
        "- changed_python_files_compiled: $compiledPythonCount",
        "- governed_validation_commands_expected: $expectedCommandCount",
        "- governed_validation_commands_passed: $successfulCommandCount",
        "- provider_and_github_secret_env_removed_before_validation: $($credentialsRemoved.ToString().ToLowerInvariant())",
        "- pr_range_git_diff_check_passed: $($prDiffCheckPassed.ToString().ToLowerInvariant())",
        "- final_worktree_clean: $($finalWorktreeClean.ToString().ToLowerInvariant())",
        '- source_branch_mutation: false',
        '- source_change_scope: validate current-head v58 HTTPError-body repair using historical HTTP-status retry policy; no mutation',
        '- live_dcoir_review_invocation: false',
        '- live_model_provider_calls: false',
        '- ready_transition: false',
        '- merge_performed: false',
        "- failure: $safeFailure"
    ) | Out-File -LiteralPath $summaryPath -Encoding utf8
}

try {
    if (Test-Path -LiteralPath $worktree) {
        $old = $ErrorActionPreference; $ErrorActionPreference='SilentlyContinue'
        & git worktree remove --force $worktree 2>$null | Out-Null
        $ErrorActionPreference=$old
        if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force }
    }

    Invoke-CheckedNative 'Fetch source branch' { git fetch --no-tags origin "refs/heads/${targetBranch}:refs/remotes/origin/${targetBranch}" }
    $remoteHead = (git rev-parse "refs/remotes/origin/$targetBranch").Trim()
    if ($remoteHead -ne $expectedHead) { throw "Remote branch drifted: expected $expectedHead but observed $remoteHead" }

    $mergeBase = (git merge-base $reviewedBase $expectedHead).Trim()
    if ($LASTEXITCODE -ne 0 -or $mergeBase -ne $reviewedBase) { throw "Reviewed base is not merge-base ancestor of head: $mergeBase" }

    Invoke-CheckedNative 'Create detached validation worktree' { git worktree add --detach $worktree $expectedHead }
    Push-Location $worktree
    try {
        $env:PYTHONDONTWRITEBYTECODE='1'
        foreach ($name in $credentialNames) { Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue }
        foreach ($name in $credentialNames) { if (Test-Path -Path "Env:$name") { throw "Credential env remained available: $name" } }
        $credentialsRemoved=$true

        $pythonExe = if (Get-Command python3 -ErrorAction SilentlyContinue) {'python3'} elseif (Get-Command python -ErrorAction SilentlyContinue) {'python'} else { throw 'Neither python3 nor python is available.' }

        Invoke-CheckedNative 'git diff --check reviewed PR range' { git diff --check "$reviewedBase...$expectedHead" }
        $prDiffCheckPassed=$true

        foreach ($path in $changedPythonFiles) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Changed Python file missing: $path" }
            Invoke-CheckedNative "py_compile $path" { & $pythonExe -m py_compile $path }
            $compiledPythonCount++
        }

        $lines = Get-Content -LiteralPath '.github/dcoir_review/openrouter-pr-review-pareto.yml'
        $commands = New-Object System.Collections.Generic.List[string]
        $inside=$false
        foreach ($line in $lines) {
            if ($line -eq 'validation_commands:') { $inside=$true; continue }
            if (-not $inside) { continue }
            if ($line -match '^[A-Za-z0-9_].*:$') { break }
            if ($line -match '^  - (.+)$') { [void]$commands.Add($Matches[1]) }
        }
        if ($commands.Count -ne $expectedCommandCount) { throw "Expected $expectedCommandCount validation commands; found $($commands.Count)" }

        $index=0
        foreach ($command in $commands) {
            $index++
            $execCommand=$command
            if ($pythonExe -eq 'python' -and $execCommand -match '^python3\s+') { $execCommand=$execCommand -replace '^python3\s+','python ' }
            Write-Host ("[{0:D2}/{1}] {2}" -f $index,$expectedCommandCount,$execCommand)
            cmd.exe /d /s /c $execCommand
            if ($LASTEXITCODE -ne 0) { throw "Governed validation command $index failed with exit code ${LASTEXITCODE}: $execCommand" }
            $successfulCommandCount++
        }

        $status=@(git status --porcelain)
        if ($status.Count -ne 0) { throw "Validated detached worktree became dirty: $($status -join '; ')" }
        $finalWorktreeClean=$true
        $result='pass'

        Write-Host 'VALIDATION_RECEIPT_BEGIN'
        Write-Host "reviewed_base_sha=$reviewedBase"
        Write-Host "validated_head_sha=$expectedHead"
        Write-Host "remote_branch_head=$remoteHead"
        Write-Host "changed_python_files_compiled=$compiledPythonCount"
        Write-Host "governed_validation_commands_passed=$successfulCommandCount"
        Write-Host 'governed_validation_result=pass'
        Write-Host 'final_worktree_clean=true'
        Write-Host 'source_branch_mutation=false'
        Write-Host 'live_dcoir_review_invocation=false'
        Write-Host 'live_model_provider_calls=false'
        Write-Host 'VALIDATION_RECEIPT_END'
    }
    finally { Pop-Location }
}
catch {
    $failureMessage=$_.Exception.Message
    Write-Host "VALIDATION_FAILURE: $failureMessage"
    throw
}
finally {
    Set-Location $repoRoot
    if (Test-Path -LiteralPath $worktree) {
        $old=$ErrorActionPreference; $ErrorActionPreference='SilentlyContinue'
        & git worktree remove --force $worktree 2>$null | Out-Null
        $ErrorActionPreference=$old
        if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Write-ValidationSummary
}
