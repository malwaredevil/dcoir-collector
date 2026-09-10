$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$targetHead = '58c9188b105bbff8071d4f3aadc1b2ad08ae5f18'
$targetBranch = 'issue-526-repair-critic-batching'
$repoRoot = (Get-Location).Path
$worktree = Join-Path $env:RUNNER_TEMP 'issue526-pr527-round2-exact-head-validation'

$secretNames = @(
    'DCOIR_GEMINI_API',
    'DCOIR_OPENAI_API_KEY',
    'DCOIR_OPENAI_PROJECT_ID',
    'OPENAI_API_KEY',
    'DCOIR_GITHUB_FG_TOKEN',
    'DCOIR_GITHUB_CL_TOKEN'
)

$changedPythonFiles = @(
    '.github/dcoir_review/scripts/dcoir_review/entrypoint.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_batch.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_followup_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_repair.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_selftest.py'
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

if (Test-Path -LiteralPath $worktree) {
    git worktree remove --force $worktree 2>$null
    if (Test-Path -LiteralPath $worktree) {
        Remove-Item -LiteralPath $worktree -Recurse -Force
    }
}

Invoke-CheckedNative -Label 'Fetch exact PR branch' -Action {
    git fetch --no-tags origin $targetBranch
}
$remoteHead = (git rev-parse "origin/$targetBranch").Trim()
if ($remoteHead -ne $targetHead) {
    throw "Remote branch drifted: expected $targetHead but observed $remoteHead"
}

Invoke-CheckedNative -Label 'Create detached exact-head worktree' -Action {
    git worktree add --detach $worktree $targetHead
}

try {
    Push-Location $worktree
    try {
        $actualHead = (git rev-parse HEAD).Trim()
        if ($actualHead -ne $targetHead) {
            throw "Worktree head mismatch: expected $targetHead but observed $actualHead"
        }

        foreach ($name in $secretNames) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        }
        foreach ($name in $secretNames) {
            if (Test-Path -Path "Env:$name") {
                throw "Inference or GitHub credential remained available in validation worktree: $name"
            }
        }
        Write-Host 'Inference and GitHub credential environment variables removed before validation.'

        foreach ($path in $changedPythonFiles) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "Changed Python file missing at exact head: $path"
            }
            Invoke-CheckedNative -Label "py_compile $path" -Action {
                python3 -m py_compile $path
            }
        }

        $configPath = '.github/dcoir_review/openrouter-pr-review-pareto.yml'
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

        if ($commands.Count -ne 56) {
            throw "Expected exactly 56 governed validation commands; found $($commands.Count)"
        }
        Write-Host "Governed validation command count: $($commands.Count)"

        $index = 0
        foreach ($command in $commands) {
            $index++
            Write-Host ("[{0:D2}/56] {1}" -f $index, $command)
            cmd.exe /d /s /c $command
            if ($LASTEXITCODE -ne 0) {
                throw "Governed validation command $index failed with exit code $LASTEXITCODE: $command"
            }
        }

        $status = @(git status --porcelain)
        if ($status.Count -ne 0) {
            Write-Host 'Dirty worktree after validation:'
            $status | ForEach-Object { Write-Host $_ }
            throw 'Exact-head validation mutated the detached worktree.'
        }

        Write-Host 'VALIDATION_RECEIPT_BEGIN'
        Write-Host "requested_head_sha=$targetHead"
        Write-Host "remote_branch_head_sha=$remoteHead"
        Write-Host "actual_head_sha=$actualHead"
        Write-Host "changed_python_files_compiled=$($changedPythonFiles.Count)"
        Write-Host "governed_validation_commands=$($commands.Count)"
        Write-Host 'governed_validation_result=pass'
        Write-Host 'worktree_clean=true'
        Write-Host 'inference_credentials_removed=true'
        Write-Host 'live_model_inference=false'
        Write-Host 'live_dcoir_review_invocation=false'
        Write-Host 'github_review_publication=false'
        Write-Host 'pr_source_mutation=false'
        Write-Host 'ready_transition=false'
        Write-Host 'merge_performed=false'
        Write-Host 'VALIDATION_RECEIPT_END'
    }
    finally {
        Pop-Location
    }
}
finally {
    Set-Location $repoRoot
    git worktree remove --force $worktree 2>$null
}
