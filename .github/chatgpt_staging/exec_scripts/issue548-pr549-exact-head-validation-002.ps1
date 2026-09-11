$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$requestId = 'issue548-pr549-exact-head-validation-002'
$targetHead = '253632c963d432b075f496b3d15e5e4fa25e9d14'
$targetBranch = 'fix/issue-548-provider-transport-retry'
$reviewedBase = 'd7b44e227176cdbbd90ff06d6f684d1b9f95b0d4'
$expectedCommandCount = 58
$repoRoot = (Get-Location).Path
$worktree = Join-Path $env:RUNNER_TEMP $requestId
$summaryDir = Join-Path $repoRoot ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
$summaryPath = Join-Path $summaryDir 'validation-summary.md'
$result = 'failure'
$failureMessage = ''
$remoteHead = ''
$actualHead = ''
$mergeBase = ''
$successfulCommandCount = 0
$compiledPythonCount = 0
$credentialsRemoved = $false
$initialWorktreeClean = $false
$finalWorktreeClean = $false
$prDiffCheckPassed = $false

$credentialNames = @(
    'DCOIR_GEMINI_API',
    'DCOIR_OPENAI_API_KEY',
    'DCOIR_OPENAI_PROJECT_ID',
    'OPENAI_API_KEY',
    'OPENROUTER_API_KEY',
    'DCOIR_OPENROUTER_API_KEY',
    'ANTHROPIC_API_KEY',
    'GOOGLE_API_KEY',
    'GEMINI_API_KEY',
    'DCOIR_GITHUB_FG_TOKEN',
    'DCOIR_GITHUB_CL_TOKEN'
)

$changedPythonFiles = @(
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py',
    '.github/dcoir_review/scripts/dcoir_review/hardened/part_04a_provider.py',
    '.github/dcoir_review/scripts/dcoir_review/selftests/provider_transport/fixtures.py',
    '.github/dcoir_review/scripts/dcoir_review/selftests/provider_transport/http_errors.py',
    '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v58.py'
)

function Invoke-CheckedNative {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host "==> $Label"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Write-ValidationSummary {
    New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
    $safeFailure = ($failureMessage -replace '[\r\n]+', ' ').Trim()
    @(
        '# PR #549 exact-head validation summary',
        '',
        "- request_id: $requestId",
        "- result: $result",
        "- target_branch: $targetBranch",
        "- reviewed_base_sha: $reviewedBase",
        "- reviewed_base_merge_base_with_target: $mergeBase",
        "- requested_head_sha: $targetHead",
        "- remote_branch_head_sha: $remoteHead",
        "- actual_worktree_head_sha: $actualHead",
        "- changed_python_files_expected: $($changedPythonFiles.Count)",
        "- changed_python_files_compiled: $compiledPythonCount",
        "- governed_validation_commands_expected: $expectedCommandCount",
        "- governed_validation_commands_passed: $successfulCommandCount",
        "- provider_and_github_secret_env_removed_before_validation: $($credentialsRemoved.ToString().ToLowerInvariant())",
        "- initial_detached_worktree_clean: $($initialWorktreeClean.ToString().ToLowerInvariant())",
        "- pr_range_git_diff_check_passed: $($prDiffCheckPassed.ToString().ToLowerInvariant())",
        "- final_detached_worktree_clean: $($finalWorktreeClean.ToString().ToLowerInvariant())",
        '- worktree_mode: detached temporary git worktree',
        '- current_main_tip_equality_required: false',
        '- live_dcoir_review_invocation: false',
        '- live_model_provider_calls: false',
        '- pr_source_branch_mutation_by_harness: false',
        '- ready_transition: false',
        '- merge_performed: false',
        "- failure: $safeFailure"
    ) | Out-File -LiteralPath $summaryPath -Encoding utf8
}

try {
    if (Test-Path -LiteralPath $worktree) {
        $oldErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = 'SilentlyContinue'
        & git worktree remove --force $worktree 2>$null | Out-Null
        $ErrorActionPreference = $oldErrorPreference
        if (Test-Path -LiteralPath $worktree) {
            Remove-Item -LiteralPath $worktree -Recurse -Force
        }
    }

    Invoke-CheckedNative -Label 'Fetch exact PR branch' -Action {
        git fetch --no-tags origin "refs/heads/${targetBranch}:refs/remotes/origin/${targetBranch}"
    }
    $remoteHead = (git rev-parse "refs/remotes/origin/$targetBranch").Trim()
    if ($remoteHead -ne $targetHead) {
        throw "Remote branch drifted: expected $targetHead but observed $remoteHead"
    }

    Invoke-CheckedNative -Label 'Verify reviewed base commit exists' -Action {
        git cat-file -e "$reviewedBase^{commit}"
    }
    $mergeBase = (git merge-base $reviewedBase $targetHead).Trim()
    if ($LASTEXITCODE -ne 0 -or $mergeBase -ne $reviewedBase) {
        throw "Reviewed base is not the merge-base ancestor of the exact target head: reviewed=$reviewedBase merge_base=$mergeBase"
    }

    Invoke-CheckedNative -Label 'Create detached exact-head worktree' -Action {
        git worktree add --detach $worktree $targetHead
    }

    Push-Location $worktree
    try {
        $actualHead = (git rev-parse HEAD).Trim()
        if ($actualHead -ne $targetHead) {
            throw "Worktree head mismatch: expected $targetHead but observed $actualHead"
        }

        $initialStatus = @(git status --porcelain)
        if ($initialStatus.Count -ne 0) {
            throw "Detached exact-head worktree was not clean before validation: $($initialStatus -join '; ')"
        }
        $initialWorktreeClean = $true

        $env:PYTHONDONTWRITEBYTECODE = '1'
        foreach ($name in $credentialNames) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        }
        foreach ($name in $credentialNames) {
            if (Test-Path -Path "Env:$name") {
                throw "Credential environment variable remained available in validation worktree: $name"
            }
        }
        $credentialsRemoved = $true

        $pythonExe = $null
        if (Get-Command python3 -ErrorAction SilentlyContinue) {
            $pythonExe = 'python3'
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $pythonExe = 'python'
        } else {
            throw 'Neither python3 nor python is available on the validation runner.'
        }

        Invoke-CheckedNative -Label 'git diff --check (working tree)' -Action { git diff --check }
        Invoke-CheckedNative -Label 'git diff --check (reviewed PR range)' -Action { git diff --check "$reviewedBase...$targetHead" }
        $prDiffCheckPassed = $true

        foreach ($path in $changedPythonFiles) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "Changed Python file missing at exact head: $path"
            }
            Invoke-CheckedNative -Label "py_compile $path" -Action { & $pythonExe -m py_compile $path }
            $compiledPythonCount++
        }

        $configPath = '.github/dcoir_review/openrouter-pr-review-pareto.yml'
        if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
            throw "Governed validation config missing: $configPath"
        }
        $lines = Get-Content -LiteralPath $configPath
        $commands = New-Object System.Collections.Generic.List[string]
        $inside = $false
        foreach ($line in $lines) {
            if ($line -eq 'validation_commands:') { $inside = $true; continue }
            if (-not $inside) { continue }
            if ($line -match '^[A-Za-z0-9_].*:$') { break }
            if ($line -match '^  - (.+)$') { [void]$commands.Add($Matches[1]) }
        }

        if ($commands.Count -ne $expectedCommandCount) {
            throw "Expected exactly $expectedCommandCount governed validation commands; found $($commands.Count)"
        }

        $index = 0
        foreach ($command in $commands) {
            $index++
            $execCommand = $command
            if ($pythonExe -eq 'python' -and $execCommand -match '^python3\s+') {
                $execCommand = $execCommand -replace '^python3\s+', 'python '
            }
            Write-Host ("[{0:D2}/{1}] {2}" -f $index, $expectedCommandCount, $execCommand)
            cmd.exe /d /s /c $execCommand
            if ($LASTEXITCODE -ne 0) {
                throw "Governed validation command $index failed with exit code ${LASTEXITCODE}: $execCommand"
            }
            $successfulCommandCount++
        }

        $status = @(git status --porcelain)
        if ($status.Count -ne 0) {
            throw "Exact-head validation mutated the detached worktree: $($status -join '; ')"
        }
        $finalWorktreeClean = $true
        $result = 'pass'

        Write-Host 'VALIDATION_RECEIPT_BEGIN'
        Write-Host "reviewed_base_sha=$reviewedBase"
        Write-Host "reviewed_base_merge_base_with_target=$mergeBase"
        Write-Host "requested_head_sha=$targetHead"
        Write-Host "remote_branch_head_sha=$remoteHead"
        Write-Host "actual_head_sha=$actualHead"
        Write-Host "changed_python_files_compiled=$compiledPythonCount"
        Write-Host "governed_validation_commands=$($commands.Count)"
        Write-Host "governed_validation_commands_passed=$successfulCommandCount"
        Write-Host 'governed_validation_result=pass'
        Write-Host 'initial_worktree_clean=true'
        Write-Host 'pr_range_git_diff_check_passed=true'
        Write-Host 'final_worktree_clean=true'
        Write-Host 'provider_and_github_secret_env_removed=true'
        Write-Host 'live_dcoir_review_invocation=false'
        Write-Host 'live_model_provider_calls=false'
        Write-Host 'pr_source_mutation_by_harness=false'
        Write-Host 'ready_transition=false'
        Write-Host 'merge_performed=false'
        Write-Host 'VALIDATION_RECEIPT_END'
    }
    finally { Pop-Location }
}
catch {
    $failureMessage = $_.Exception.Message
    Write-Host "VALIDATION_FAILURE: $failureMessage"
    throw
}
finally {
    Set-Location $repoRoot
    if (Test-Path -LiteralPath $worktree) {
        $oldErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = 'SilentlyContinue'
        & git worktree remove --force $worktree 2>$null | Out-Null
        $ErrorActionPreference = $oldErrorPreference
        if (Test-Path -LiteralPath $worktree) {
            Remove-Item -LiteralPath $worktree -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Write-ValidationSummary
}