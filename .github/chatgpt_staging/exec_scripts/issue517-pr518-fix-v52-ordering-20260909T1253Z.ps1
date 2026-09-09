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
$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr518-fix-' + $expectedSha.Substring(0,12))
$target = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py'

try {
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }

    $remoteLine = (& git -C $repo ls-remote origin "refs/heads/$branch" | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "could not resolve remote branch $branch" }
    $remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
    if ($remoteSha -ne $expectedSha) {
        throw "PR branch moved before fix: expected=$expectedSha remote=$remoteSha"
    }

    & git -C $repo fetch --no-tags origin $expectedSha
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed with exit code $LASTEXITCODE" }
    & git -C $repo worktree add --detach $worktree $expectedSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed with exit code $LASTEXITCODE" }

    Set-Location -LiteralPath $worktree
    $actualSha = (& git rev-parse HEAD).Trim()
    if ($actualSha -ne $expectedSha) { throw "exact-head mismatch: expected=$expectedSha actual=$actualSha" }

    $path = Join-Path $worktree $target
    $text = [System.IO.File]::ReadAllText($path)
    $old = "        `"dcoir_review_required_runtime_patch_v52`",`n    )"
    $new = "        `"dcoir_review_required_runtime_patch_v52`",`n        `"dcoir_review_required_runtime_patch_v53`",`n    )"
    $matches = ([regex]::Matches($text, [regex]::Escape($old))).Count
    if ($matches -ne 1) { throw "expected exactly one v52 terminal tuple seam, found $matches" }
    $text = $text.Replace($old, $new)
    [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))

    & python3 -m py_compile $target
    if ($LASTEXITCODE -ne 0) { throw 'v52 selftest py_compile failed' }
    & python3 $target
    if ($LASTEXITCODE -ne 0) { throw 'v52 selftest failed after ordering fix' }
    & python3 '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v53 selftest failed after ordering fix' }

    $dirty = @(& git status --porcelain=v1 --untracked-files=all)
    if ($dirty.Count -ne 1 -or -not ($dirty[0] -match [regex]::Escape($target))) {
        throw "unexpected worktree delta: $($dirty -join ', ')"
    }

    & git add -- $target
    & git -c user.name='Malware Devil' -c user.email='34285973+malwaredevil@users.noreply.github.com' commit -m 'Keep v52 ordering regression current with v53'
    if ($LASTEXITCODE -ne 0) { throw "git commit failed with exit code $LASTEXITCODE" }
    $newSha = (& git rev-parse HEAD).Trim()

    & git push "--force-with-lease=refs/heads/${branch}:$expectedSha" origin "HEAD:refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) { throw "guarded branch push failed with exit code $LASTEXITCODE" }

    $readbackLine = (& git -C $repo ls-remote origin "refs/heads/$branch" | Select-Object -First 1)
    $readbackSha = ([string]$readbackLine -split '\s+')[0].Trim()
    if ($readbackSha -ne $newSha) { throw "post-push head mismatch: committed=$newSha remote=$readbackSha" }

    @{
        schema = 'dcoir.issue517.pr518_v52_ordering_fix.v1'
        issue_number = 517
        pr_number = 518
        branch = $branch
        previous_head_sha = $expectedSha
        new_head_sha = $newSha
        target = $target
        v52_selftest = 'pass'
        v53_selftest = 'pass'
        inference_used = $false
        workflow_yaml_changed = $false
    } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue517-pr518-v52-ordering-fix-receipt.json') -Encoding utf8

    Write-Host "PR #518 v52 ordering regression updated and pushed: $newSha"
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) {
        & git -C $repo worktree remove --force $worktree 2>$null
    }
}
