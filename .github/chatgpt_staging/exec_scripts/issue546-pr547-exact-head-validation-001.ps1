$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$requestId = 'issue546-pr547-exact-head-validation-001'
$targetHead = 'c63189a64a17fb4b101dc79d61dc9938daf6fe30'
$targetBranch = 'fix/issue-546-adjudication-low-confidence'
$expectedCommandCount = 57
$repoRoot = (Get-Location).Path
$worktree = Join-Path $env:RUNNER_TEMP $requestId
$summaryDir = Join-Path $repoRoot ".github/chatgpt_staging/status_reports/chatgpt-exec/$requestId"
$summaryPath = Join-Path $summaryDir 'validation-summary.md'
$result = 'failure'
$failureMessage = ''
$remoteHead = ''
$actualHead = ''
$successfulCommandCount = 0

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
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_production.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest_prompt.py'
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
        '# PR #547 exact-head validation summary',
        '',
        "- request_id: $requestId",
        "- result: $result",
        "- target_branch: $targetBranch",
        "- requested_head_sha: $targetHead",
        "- remote_branch_head_sha: $remoteHead",
        "- actual_worktree_head_sha: $actualHead",
        "- changed_python_files_compiled: $($changedPythonFiles.Count)",
        "- governed_validation_commands_expected: $expectedCommandCount",
        "- governed_validation_commands_passed: $successfulCommandCount",
        "- worktree_mode: detached temporary git worktree",
        '- provider_and_github_secret_env_removed_before_validation: true',
        '- live_dcoir_review_invocation: false',
        '- pr_source_branch_mutation: false',
        '- ready_transition: false',
        '- merge_performed: false',
        "- failure: $safeFailure"
    ) | Out-File -LiteralPath $summaryPath -Encoding utf8
}

try {
    if (Test-Path -LiteralPath $worktree) {
        git worktree remove --force $worktree 2>$null
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

    Invoke-CheckedNative -Label 'Create detached exact-head worktree' -Action {
        git worktree add --detach $worktree $targetHead
    }

    Push-Location $worktree
    try {
        $actualHead = (git rev-parse HEAD).Trim()
        if ($actualHead -ne $targetHead) {
            throw "Worktree head mismatch: expected $targetHead but observed $actualHead"
        }

        $env:PYTHONDONTWRITEBYTECODE = '1'
        foreach ($name in $credentialNames) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        }
        foreach ($name in $credentialNames) {
            if (Test-Path -Path "Env:$name") {
                throw "Credential environment variable remained available in validation worktree: $name"
            }
        }
        Write-Host 'Provider and GitHub credential environment variables removed before validation.'

        $pythonExe = $null
        if (Get-Command python3 -ErrorAction SilentlyContinue) {
            $pythonExe = 'python3'
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $pythonExe = 'python'
        } else {
            throw 'Neither python3 nor python is available on the validation runner.'
        }
        Write-Host "Python executable selected: $pythonExe"

        Invoke-CheckedNative -Label 'git diff --check' -Action {
            git diff --check
        }

        foreach ($path in $changedPythonFiles) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "Changed Python file missing at exact head: $path"
            }
            Invoke-CheckedNative -Label "py_compile $path" -Action {
                & $pythonExe -m py_compile $path
            }
        }

        $configPath = '.github/dcoir_review/openrouter-pr-review-pareto.yml'
        if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
            throw "Governed validation config missing: $configPath"
        }
        $lines = Get-Content -LiteralPath $configPath
        $commands = New-Object System.Collections.Generic.List[string]
        $inside = $false
        foreach ($line in $lines) {
            if ($line -eq 'validation_commands:') {
                $inside = $true
                continue
            }
            if (-not $inside) {
                continue
            }
            if ($line -match '^[A-Za-z0-9_].*:$') {
                break
            }
            if ($line -match '^  - (.+)$') {
                [void]$commands.Add($Matches[1])
            }
        }

        if ($commands.Count -ne $expectedCommandCount) {
            throw "Expected exactly $expectedCommandCount governed validation commands; found $($commands.Count)"
        }
        Write-Host "Governed validation command count: $($commands.Count)"

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
            Write-Host 'Dirty worktree after validation:'
            $status | ForEach-Object { Write-Host $_ }
            throw 'Exact-head validation mutated the detached worktree.'
        }

        $result = 'pass'
        Write-Host 'VALIDATION_RECEIPT_BEGIN'
        Write-Host "requested_head_sha=$targetHead"
        Write-Host "remote_branch_head_sha=$remoteHead"
        Write-Host "actual_head_sha=$actualHead"
        Write-Host "changed_python_files_compiled=$($changedPythonFiles.Count)"
        Write-Host "governed_validation_commands=$($commands.Count)"
        Write-Host "governed_validation_commands_passed=$successfulCommandCount"
        Write-Host 'governed_validation_result=pass'
        Write-Host 'worktree_clean=true'
        Write-Host 'provider_and_github_secret_env_removed=true'
        Write-Host 'live_dcoir_review_invocation=false'
        Write-Host 'pr_source_mutation=false'
        Write-Host 'ready_transition=false'
        Write-Host 'merge_performed=false'
        Write-Host 'VALIDATION_RECEIPT_END'
    }
    finally {
        Pop-Location
    }
}
catch {
    $failureMessage = $_.Exception.Message
    Write-Host "VALIDATION_FAILURE: $failureMessage"
    throw
}
finally {
    Set-Location $repoRoot
    git worktree remove --force $worktree 2>$null
    Write-ValidationSummary
}
