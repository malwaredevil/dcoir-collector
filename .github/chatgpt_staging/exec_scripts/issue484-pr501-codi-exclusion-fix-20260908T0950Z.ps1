$ErrorActionPreference = 'Stop'
$repo = $env:DCOIR_REPO_ROOT
if (-not $repo) { throw 'DCOIR_REPO_ROOT is not set' }
$branch = 'issue-484-lane-separation-scoring'
$expected = 'ccd0ebeac43b68e76c4c40684916167d43a3f858'
$sourcePath = 'project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py'
$validatorPath = 'project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py'
$remoteLine = git -C $repo ls-remote origin ('refs/heads/' + $branch)
if ($LASTEXITCODE -ne 0) { throw 'git ls-remote failed' }
$remote = (($remoteLine -split '\s+')[0])
if ($remote -ne $expected) { throw ('PR head drift: expected ' + $expected + ', got ' + $remote) }
git -C $repo fetch --no-tags origin $branch
if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
$worktree = Join-Path $env:RUNNER_TEMP 'dcoir-issue484-pr501-codi-exclusion-fix'
if (Test-Path $worktree) {
  git -C $repo worktree remove --force $worktree 2>$null
  Remove-Item -LiteralPath $worktree -Recurse -Force -ErrorAction SilentlyContinue
}
git -C $repo worktree add --detach $worktree $expected
if ($LASTEXITCODE -ne 0) { throw 'git worktree add failed' }
try {
  Set-Location $worktree
  git config user.name 'github-actions[bot]'
  git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  'OPENROUTER_API_KEY','OPENAI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID' | ForEach-Object { Remove-Item ('Env:' + $_) -ErrorAction SilentlyContinue }
  $env:PYTHONDONTWRITEBYTECODE = '1'

  $patch = @'
from pathlib import Path

source_path = Path('project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py')
validator_path = Path('project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py')
source = source_path.read_text(encoding='utf-8')
validator = validator_path.read_text(encoding='utf-8')

old = '''        "unlike",
        "versus",
        "vs",
        "against",
    }
)
'''
new = '''        "unlike",
        "versus",
        "vs",
        "against",
        "besides",
        "beside",
        "save",
        "saving",
        "aside",
        "outside",
        "beyond",
    }
)
'''
if source.count(old) != 1:
    raise SystemExit('expected one lane-target blocker tail')
source = source.replace(old, new)

anchor = '''    _expect(
        "Do not run endpoint response-action commands in the same shell as anything other "
        "than local PowerShell commands.",
        False,
        "other-than exclusion cannot be skipped before local lane head",
    )
'''
insert = anchor + '''    _expect(
        "Do not run endpoint response-action commands in the same shell as anything besides "
        "local PowerShell commands.",
        False,
        "besides exclusion cannot be skipped before local lane head",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything aside "
        "from local PowerShell commands.",
        False,
        "aside-from exclusion cannot be skipped before local lane head",
    )
'''
if validator.count(anchor) != 1:
    raise SystemExit('expected one other-than exclusion validator block')
validator = validator.replace(anchor, insert)

source_path.write_text(source, encoding='utf-8')
validator_path.write_text(validator, encoding='utf-8')
'@
  $tempPy = Join-Path $env:RUNNER_TEMP 'issue484_codi_exclusion_fix.py'
  Set-Content -LiteralPath $tempPy -Value $patch -Encoding UTF8
  python $tempPy
  if ($LASTEXITCODE -ne 0) { throw 'patch script failed' }
  git diff --check
  if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
  $changed = @(git diff --name-only)
  if (($changed.Count -ne 2) -or (@($changed | Where-Object { $_ -notin @($sourcePath,$validatorPath) }).Count -ne 0)) { throw ('unexpected changed files: ' + ($changed -join ', ')) }
  python -m py_compile $sourcePath $validatorPath
  if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
  python $validatorPath
  if ($LASTEXITCODE -ne 0) { throw 'focused lane-separation regression failed' }
  $out = Join-Path $env:RUNNER_TEMP 'issue484-gemini-replay-codi-exclusion-output'
  if (Test-Path $out) { Remove-Item -LiteralPath $out -Recurse -Force }
  python project_sources/gemini/tools/run_gemini_behavioral_replay_validation_suite.py --fixtures-root project_sources/gemini/fixtures/behavioral_replay --output-dir $out
  if ($LASTEXITCODE -ne 0) { throw 'Gemini behavioral replay validation suite failed' }
  git add -- $sourcePath $validatorPath
  git commit -m 'Block exclusion operators before lane head'
  if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
  $newHead = (git rev-parse HEAD).Trim()
  git push origin ('HEAD:refs/heads/' + $branch)
  if ($LASTEXITCODE -ne 0) { throw 'git push failed' }
  $dirty = git status --porcelain
  if ($dirty) { throw ('worktree not clean after push: ' + ($dirty -join '; ')) }
  Write-Host ('ISSUE484_CODI_EXCLUSION_FIX_HEAD=' + $newHead)
}
finally {
  Set-Location $repo
  git worktree remove --force $worktree 2>$null
}
