$ErrorActionPreference = 'Stop'

$branch = 'issue-484-lane-separation-scoring'
$expectedHead = 'a4c1c07f6fa1f25d350758c1117d4393ef480f1a'
$sourcePath = 'project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py'
$validatorPath = 'project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py'
$patcherPath = '.github/chatgpt_staging/exec_scripts/issue484-pr501-dcoir-findings-fix-v2.py'

function Invoke-Git([string[]]$GitArgs) {
    Write-Host "git $($GitArgs -join ' ')"
    $output = & git @GitArgs
    $code = $LASTEXITCODE
    if ($output) { $output | Out-Host }
    if ($code -ne 0) { throw "git failed with exit $code`: git $($GitArgs -join ' ')" }
}

Invoke-Git @('fetch', '--no-tags', 'origin', "refs/heads/$branch`:refs/remotes/origin/$branch")
$remoteHead = (& git rev-parse "refs/remotes/origin/$branch").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read remote branch head.' }
Write-Host "Remote PR head: $remoteHead"
if ($remoteHead -ne $expectedHead) { throw "PR head drifted: expected $expectedHead got $remoteHead" }

Invoke-Git @('checkout', '-B', $branch, "origin/$branch")
Invoke-Git @('config', 'user.name', 'github-actions[bot]')
Invoke-Git @('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')

$env:PYTHONDONTWRITEBYTECODE = '1'
foreach ($name in @('DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY')) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

python $patcherPath
if ($LASTEXITCODE -ne 0) { throw 'Patch script failed.' }

Invoke-Git @('diff', '--check')
$changed = @(& git diff --name-only)
$expectedFiles = @($sourcePath, $validatorPath)
$unexpected = @($changed | Where-Object { $_ -notin $expectedFiles })
if (($changed.Count -ne 2) -or ($unexpected.Count -ne 0)) {
    throw "Unexpected changed files: $($changed -join ', ')"
}

python -m py_compile $sourcePath $validatorPath
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed.' }

python $validatorPath
if ($LASTEXITCODE -ne 0) { throw 'Focused lane-separation regression failed.' }

$outDir = Join-Path $env:RUNNER_TEMP 'issue484-full-replay-validation-v2'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
python project_sources/gemini/tools/run_gemini_behavioral_replay_validation_suite.py `
    --fixtures-root project_sources/gemini/fixtures/behavioral_replay `
    --output-dir $outDir
if ($LASTEXITCODE -ne 0) { throw 'Full deterministic Gemini behavioral replay validation failed.' }

Invoke-Git @('add', '--', $sourcePath, $validatorPath)
Invoke-Git @('commit', '-m', 'Address DCOIR lane scoring findings')
$newHead = (& git rev-parse HEAD).Trim()
Write-Host "New PR head: $newHead"
Invoke-Git @('push', 'origin', "HEAD:refs/heads/$branch")

$remaining = @(& git status --porcelain)
if ($remaining.Count -ne 0) { throw "Worktree not clean after push: $($remaining -join '; ')" }
Write-Host "ISSUE484_FIX_HEAD=$newHead"
