$ErrorActionPreference = 'Stop'

$branch = 'issue-484-lane-separation-scoring'
$expectedHead = 'b7935a3c7fa1d50329c1094343e6f7495938de49'
$worktree = Join-Path $env:RUNNER_TEMP 'issue484-pr501-postdcoir-exact-head'

function Invoke-Git([string[]]$GitArgs) {
    Write-Host "git $($GitArgs -join ' ')"
    $output = & git @GitArgs
    $code = $LASTEXITCODE
    if ($output) { $output | Out-Host }
    if ($code -ne 0) { throw "git failed with exit $code`: git $($GitArgs -join ' ')" }
}

Invoke-Git @('fetch', '--no-tags', 'origin', "refs/heads/$branch`:refs/remotes/origin/$branch")
$remoteHead = (& git rev-parse "refs/remotes/origin/$branch").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve remote PR branch.' }
Write-Host "Remote PR head: $remoteHead"
if ($remoteHead -ne $expectedHead) { throw "PR head drifted: expected $expectedHead got $remoteHead" }

if (Test-Path -LiteralPath $worktree) {
    Invoke-Git @('worktree', 'remove', '--force', $worktree)
}
Invoke-Git @('worktree', 'add', '--detach', $worktree, $expectedHead)

try {
    Push-Location $worktree
    $actualHead = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve detached worktree head.' }
    if ($actualHead -ne $expectedHead) { throw "Detached worktree mismatch: expected $expectedHead got $actualHead" }

    $env:PYTHONDONTWRITEBYTECODE = '1'
    foreach ($name in @('DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY')) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }

    $sourcePath = 'project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py'
    $validatorPath = 'project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py'
    python -m py_compile $sourcePath $validatorPath
    if ($LASTEXITCODE -ne 0) { throw 'py_compile failed.' }

    python $validatorPath
    if ($LASTEXITCODE -ne 0) { throw 'Focused lane-separation regression failed.' }

    $outDir = Join-Path $env:RUNNER_TEMP 'issue484-pr501-postdcoir-replay-suite'
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    python project_sources/gemini/tools/run_gemini_behavioral_replay_validation_suite.py `
        --fixtures-root project_sources/gemini/fixtures/behavioral_replay `
        --output-dir $outDir
    if ($LASTEXITCODE -ne 0) { throw 'Full deterministic Gemini behavioral replay validation failed.' }

    $dirty = @(& git status --porcelain)
    if ($dirty.Count -ne 0) { throw "Detached worktree is dirty after validation: $($dirty -join '; ')" }
    Write-Host "ISSUE484_POSTDCOIR_VALIDATION_HEAD=$actualHead"
    Write-Host 'ISSUE484_POSTDCOIR_VALIDATION=PASS'
}
finally {
    Pop-Location
    Invoke-Git @('worktree', 'remove', '--force', $worktree)
}
