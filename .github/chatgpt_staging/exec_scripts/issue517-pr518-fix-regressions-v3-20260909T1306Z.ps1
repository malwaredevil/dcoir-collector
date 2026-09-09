[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$expectedSha = 'dd8b638c6b528c0a1eeb2a3da396b67ee6254b4a'
$branch = 'issue-517-bounded-repair-tail'
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr518-fix-v3-' + $expectedSha.Substring(0,12))
$v52Target = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py'
$v53Target = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py'

try {
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
    $remoteLine = (& git -C $repo ls-remote origin "refs/heads/$branch" | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "could not resolve remote branch $branch" }
    $remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
    if ($remoteSha -ne $expectedSha) { throw "PR branch moved before fix: expected=$expectedSha remote=$remoteSha" }

    & git -C $repo fetch --no-tags origin $expectedSha
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed with exit code $LASTEXITCODE" }
    & git -C $repo worktree add --detach $worktree $expectedSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed with exit code $LASTEXITCODE" }
    Set-Location -LiteralPath $worktree
    if ((& git rev-parse HEAD).Trim() -ne $expectedSha) { throw 'detached exact-head mismatch' }

    $v52Path = Join-Path $worktree $v52Target
    $v52Text = [System.IO.File]::ReadAllText($v52Path)
    $pattern = '(?m)(^\s*"dcoir_review_required_runtime_patch_v52",\r?\n)(\s*\)\r?$)'
    $matchCount = ([regex]::Matches($v52Text, $pattern)).Count
    if ($matchCount -ne 1) { throw "expected exactly one v52 terminal tuple seam, found $matchCount" }
    $replacement = '${1}        "dcoir_review_required_runtime_patch_v53",' + [Environment]::NewLine + '${2}'
    $v52Text = [regex]::Replace($v52Text, $pattern, $replacement, 1)
    [System.IO.File]::WriteAllText($v52Path, $v52Text, (New-Object System.Text.UTF8Encoding($false)))

    $v53Path = Join-Path $worktree $v53Target
    $v53Text = [System.IO.File]::ReadAllText($v53Path)
    $oldIndex = '        assert right_line_index[(PATH, 1)] == 1'
    $newIndex = '        assert right_line_index[(PATH, 1)] == 2'
    $indexMatches = ([regex]::Matches($v53Text, [regex]::Escape($oldIndex))).Count
    if ($indexMatches -ne 1) { throw "expected exactly one v53 diff-position assertion, found $indexMatches" }
    $v53Text = $v53Text.Replace($oldIndex, $newIndex)
    [System.IO.File]::WriteAllText($v53Path, $v53Text, (New-Object System.Text.UTF8Encoding($false)))

    & python3 -m py_compile $v52Target $v53Target
    if ($LASTEXITCODE -ne 0) { throw 'updated regression selftests py_compile failed' }
    & python3 $v52Target
    if ($LASTEXITCODE -ne 0) { throw 'v52 selftest failed after regression repair' }
    & python3 $v53Target
    if ($LASTEXITCODE -ne 0) { throw 'v53 selftest failed after regression repair' }

    $dirty = @(& git status --porcelain=v1 --untracked-files=all)
    if ($dirty.Count -ne 2) { throw "expected exactly two changed selftests, found: $($dirty -join ', ')" }
    foreach ($target in @($v52Target, $v53Target)) {
        if (-not ($dirty -match [regex]::Escape($target))) { throw "expected changed selftest missing from worktree: $target" }
    }

    & git add -- $v52Target $v53Target
    & git -c user.name='Malware Devil' -c user.email='34285973+malwaredevil@users.noreply.github.com' commit -m 'Align v52/v53 execution-policy regressions'
    if ($LASTEXITCODE -ne 0) { throw "git commit failed with exit code $LASTEXITCODE" }
    $newSha = (& git rev-parse HEAD).Trim()
    & git push "--force-with-lease=refs/heads/${branch}:$expectedSha" origin "HEAD:refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) { throw "guarded branch push failed with exit code $LASTEXITCODE" }
    $readbackLine = (& git -C $repo ls-remote origin "refs/heads/$branch" | Select-Object -First 1)
    $readbackSha = ([string]$readbackLine -split '\s+')[0].Trim()
    if ($readbackSha -ne $newSha) { throw "post-push head mismatch: committed=$newSha remote=$readbackSha" }

    @{
        schema = 'dcoir.issue517.pr518_regression_fix.v1'
        issue_number = 517
        pr_number = 518
        previous_head_sha = $expectedSha
        new_head_sha = $newSha
        changed_files = @($v52Target, $v53Target)
        v52_selftest = 'pass'
        v53_selftest = 'pass'
        v53_diff_position_expected = 2
        inference_used = $false
        workflow_yaml_changed = $false
    } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue517-pr518-regression-fix-v3-receipt.json') -Encoding utf8
    Write-Host "PR #518 regression fixtures repaired and pushed: $newSha"
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
