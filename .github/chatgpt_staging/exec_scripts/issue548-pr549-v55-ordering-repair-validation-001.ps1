$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$requestId = 'issue548-pr549-v55-ordering-repair-validation-001'
$targetBranch = 'fix/issue-548-provider-transport-retry'
$expectedHead = 'fd8dc731070c1543848e5c95263f33765b556ea6'
$reviewedBase = 'd7b44e227176cdbbd90ff06d6f684d1b9f95b0d4'
$expectedCommandCount = 58
$v55Path = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py'
$repoRoot = (Get-Location).Path
$worktree = Join-Path $env:RUNNER_TEMP $requestId
$summaryDir = Join-Path $repoRoot ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
$summaryPath = Join-Path $summaryDir 'validation-summary.md'
$result = 'failure'
$failureMessage = ''
$remoteHeadBefore = ''
$newHead = ''
$remoteHeadAfter = ''
$mergeBase = ''
$successfulCommandCount = 0
$compiledPythonCount = 0
$credentialsRemoved = $false
$prDiffCheckPassed = $false
$finalWorktreeClean = $false
$pushPerformed = $false

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
        '# PR #549 v55 ordering repair + exact-head validation summary','',
        "- request_id: $requestId",
        "- result: $result",
        "- target_branch: $targetBranch",
        "- expected_remote_head_before: $expectedHead",
        "- observed_remote_head_before: $remoteHeadBefore",
        "- reviewed_base_sha: $reviewedBase",
        "- reviewed_base_merge_base_with_new_head: $mergeBase",
        "- locally_committed_validated_head_sha: $newHead",
        "- remote_branch_head_after_push: $remoteHeadAfter",
        "- changed_python_files_expected: $($changedPythonFiles.Count)",
        "- changed_python_files_compiled: $compiledPythonCount",
        "- governed_validation_commands_expected: $expectedCommandCount",
        "- governed_validation_commands_passed: $successfulCommandCount",
        "- provider_and_github_secret_env_removed_before_validation: $($credentialsRemoved.ToString().ToLowerInvariant())",
        "- pr_range_git_diff_check_passed: $($prDiffCheckPassed.ToString().ToLowerInvariant())",
        "- final_worktree_clean: $($finalWorktreeClean.ToString().ToLowerInvariant())",
        "- source_branch_push_performed: $($pushPerformed.ToString().ToLowerInvariant())",
        '- source_change_scope: restore v55 selftest from reviewed base, replace only stale post-telemetry ordering assertions, then validate exact committed tree',
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
    $remoteHeadBefore = (git rev-parse "refs/remotes/origin/$targetBranch").Trim()
    if ($remoteHeadBefore -ne $expectedHead) { throw "Remote branch drifted: expected $expectedHead but observed $remoteHeadBefore" }

    Invoke-CheckedNative 'Create detached repair worktree' { git worktree add --detach $worktree $expectedHead }
    Push-Location $worktree
    try {
        Invoke-CheckedNative 'Restore complete v55 selftest from reviewed base' { git checkout $reviewedBase -- $v55Path }

        $text = [IO.File]::ReadAllText((Join-Path (Get-Location).Path $v55Path))
        $oldBlock = @'
    assert entrypoint.post_telemetry_patch_module_names[0] == "dcoir_review_required_runtime_patch_v55"
    assert entrypoint.post_telemetry_patch_module_names.index("dcoir_review_required_runtime_patch_v55") < entrypoint.post_telemetry_patch_module_names.index("dcoir_review_required_runtime_patch_v56")
'@
        $newBlock = @'
    post_telemetry = entrypoint.post_telemetry_patch_module_names
    assert post_telemetry[0] == "dcoir_review_required_runtime_patch_v58"
    assert post_telemetry[-3:] == (
        "dcoir_review_required_runtime_patch_v55",
        "dcoir_review_required_runtime_patch_v56",
        "dcoir_review_required_runtime_patch_v57",
    )
    assert post_telemetry.index("dcoir_review_required_runtime_patch_v55") < post_telemetry.index("dcoir_review_required_runtime_patch_v56")
'@
        if (-not $text.Contains($oldBlock)) { throw 'Expected v55 ordering assertion block was not found exactly once in reviewed-base source.' }
        if (($text.Split(@($oldBlock),[StringSplitOptions]::None).Count - 1) -ne 1) { throw 'Expected v55 ordering assertion block did not occur exactly once.' }
        $text = $text.Replace($oldBlock,$newBlock)
        [IO.File]::WriteAllText((Join-Path (Get-Location).Path $v55Path),$text,(New-Object Text.UTF8Encoding($false)))

        Invoke-CheckedNative 'git diff --check after repair' { git diff --check }
        $changed = @(git diff --name-only)
        if ($changed.Count -ne 1 -or $changed[0] -ne $v55Path) { throw "Repair touched unexpected paths: $($changed -join ', ')" }

        git config user.name 'chatgpt-exec'
        git config user.email 'chatgpt-exec@users.noreply.github.com'
        git add -- $v55Path
        Invoke-CheckedNative 'Commit validation-order repair' { git commit -m 'test(dcoir): align v55 ordering assertion with v58' }
        $newHead = (git rev-parse HEAD).Trim()

        $mergeBase = (git merge-base $reviewedBase $newHead).Trim()
        if ($LASTEXITCODE -ne 0 -or $mergeBase -ne $reviewedBase) { throw "Reviewed base is not merge-base ancestor of new head: $mergeBase" }

        $env:PYTHONDONTWRITEBYTECODE='1'
        foreach ($name in $credentialNames) { Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue }
        foreach ($name in $credentialNames) { if (Test-Path -Path "Env:$name") { throw "Credential env remained available: $name" } }
        $credentialsRemoved=$true

        $pythonExe = if (Get-Command python3 -ErrorAction SilentlyContinue) {'python3'} elseif (Get-Command python -ErrorAction SilentlyContinue) {'python'} else { throw 'Neither python3 nor python is available.' }

        Invoke-CheckedNative 'git diff --check reviewed PR range' { git diff --check "$reviewedBase...$newHead" }
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
        if ($status.Count -ne 0) { throw "Validated committed worktree became dirty: $($status -join '; ')" }
        $finalWorktreeClean=$true

        Invoke-CheckedNative 'Push validated repair to exact source branch' { git push origin "${newHead}:refs/heads/${targetBranch}" }
        $pushPerformed=$true
        Invoke-CheckedNative 'Refresh source branch after push' { git fetch --no-tags origin "refs/heads/${targetBranch}:refs/remotes/origin/${targetBranch}" }
        $remoteHeadAfter=(git rev-parse "refs/remotes/origin/$targetBranch").Trim()
        if ($remoteHeadAfter -ne $newHead) { throw "Post-push branch mismatch: expected $newHead observed $remoteHeadAfter" }

        $result='pass'
        Write-Host 'VALIDATION_RECEIPT_BEGIN'
        Write-Host "reviewed_base_sha=$reviewedBase"
        Write-Host "validated_head_sha=$newHead"
        Write-Host "remote_branch_head_after=$remoteHeadAfter"
        Write-Host "changed_python_files_compiled=$compiledPythonCount"
        Write-Host "governed_validation_commands_passed=$successfulCommandCount"
        Write-Host 'governed_validation_result=pass'
        Write-Host 'final_worktree_clean=true'
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
