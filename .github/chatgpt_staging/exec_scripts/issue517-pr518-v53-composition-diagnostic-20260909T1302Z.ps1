[CmdletBinding()]
param()
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$requestedSha = 'dd8b638c6b528c0a1eeb2a3da396b67ee6254b4a'
$branch = 'issue-517-bounded-repair-tail'
$repo = [string]$env:DCOIR_REPO_ROOT
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr518-v53diag-' + $requestedSha.Substring(0,12))
try {
  if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
  $remoteLine = (& git -C $repo ls-remote origin "refs/heads/$branch" | Select-Object -First 1)
  $remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
  if ($remoteSha -ne $requestedSha) { throw "branch moved: requested=$requestedSha remote=$remoteSha" }
  & git -C $repo fetch --no-tags origin $requestedSha
  if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
  & git -C $repo worktree add --detach $worktree $requestedSha
  if ($LASTEXITCODE -ne 0) { throw 'worktree add failed' }
  Set-Location -LiteralPath $worktree
  $target = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py'
  $text = [System.IO.File]::ReadAllText((Join-Path $worktree $target))
  $needle = '        assert second["outcome"] == v36.REPAIR_SET_OUTCOME'
  $replacement = '        print("V53_DIAG_SECOND=" + repr(second)); print("V53_DIAG_CALLS=" + repr(calls))' + [Environment]::NewLine + $needle
  if (-not $text.Contains($needle)) { throw 'diagnostic insertion seam missing' }
  $text = $text.Replace($needle, $replacement)
  [System.IO.File]::WriteAllText((Join-Path $worktree $target), $text, (New-Object System.Text.UTF8Encoding($false)))
  & python3 $target
  $exit = $LASTEXITCODE
  Write-Host "V53_DIAG_EXIT=$exit"
  if ($exit -ne 0) { exit $exit }
}
finally {
  Set-Location -LiteralPath $repo
  if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
