[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null

$targets = @(
    [pscustomobject]@{ Name = 'validation-pr493-20260907'; Sha = '9dc79501bd40ee365eda898bf4b5839f52788ee0' },
    [pscustomobject]@{ Name = 'validation-pr493-rerun1-20260907'; Sha = 'a0f0d96dd39f36bd897255b88da4fc873407f97b' },
    [pscustomobject]@{ Name = 'test-only-439-copilot-skill'; Sha = '89d7d3d399147bd375fb6111c95d5949c2faccc1' },
    [pscustomobject]@{ Name = 'test-only-439-blind-baseline'; Sha = '11f3754047e6e89fa7422478c75a39eaaedd5ae9' },
    [pscustomobject]@{ Name = 'test-only-439-blind-treatment'; Sha = 'f489ac55108deead69f7e7a3f99ff11143a5189d' },
    [pscustomobject]@{ Name = 'issue-424-openai-gpt-human-setup-package'; Sha = '49fb663af838f06bf0ed29e1461649f8c733d170' },
    [pscustomobject]@{ Name = 'stage-8-ircore-agent-runtime-alignment'; Sha = 'b1a4771e693639d5670b2c5378ccac758aeb09cd' }
)

$reserved = @(
    'main',
    'issue-457-credit-aware-concurrency',
    'benchmark-478-architecture-b-replay-base',
    'benchmark-478-architecture-b-replay-head',
    'test-only-dcoir-review-suggestion-probe',
    'test-only-dcoir-review-verifier-probe'
)

foreach ($target in $targets) {
    if ($reserved -contains $target.Name) {
        throw "cleanup target unexpectedly intersects reserved branch: $($target.Name)"
    }
}

$preflight = @()
foreach ($target in $targets) {
    $ref = "refs/heads/$($target.Name)"
    $lines = @(& git -C $repo ls-remote --heads origin $ref)
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-remote failed for $($target.Name) with exit code $LASTEXITCODE"
    }
    if ($lines.Count -ne 1) {
        throw "preflight requires exactly one existing ref for $($target.Name); observed $($lines.Count)"
    }
    $actualSha = (($lines[0] -split '\s+')[0]).Trim()
    if ($actualSha -ne $target.Sha) {
        throw "preflight SHA mismatch for $($target.Name): expected=$($target.Sha) actual=$actualSha"
    }
    $preflight += [pscustomobject]@{
        name = $target.Name
        expected_sha = $target.Sha
        observed_sha = $actualSha
        exact_match = $true
    }
}

$leaseArgs = @()
$deleteRefspecs = @()
foreach ($target in $targets) {
    $ref = "refs/heads/$($target.Name)"
    $leaseArgs += "--force-with-lease=${ref}:$($target.Sha)"
    $deleteRefspecs += ":$ref"
}

$gitArgs = @('-C', $repo, 'push', 'origin', '--atomic') + $leaseArgs + $deleteRefspecs
Write-Host "Deleting exactly $($targets.Count) guarded obsolete branches in one atomic push."
& git @gitArgs
if ($LASTEXITCODE -ne 0) {
    throw "atomic guarded branch deletion push failed with exit code $LASTEXITCODE"
}

$verifiedAbsent = @()
foreach ($target in $targets) {
    $ref = "refs/heads/$($target.Name)"
    $lines = @(& git -C $repo ls-remote --heads origin $ref)
    if ($LASTEXITCODE -ne 0) {
        throw "post-delete git ls-remote failed for $($target.Name) with exit code $LASTEXITCODE"
    }
    if ($lines.Count -ne 0) {
        throw "post-delete verification failed; branch still exists: $($target.Name)"
    }
    $verifiedAbsent += $target.Name
}

@{
    schema = 'dcoir.issue457.obsolete_branch_cleanup.v1'
    issue_number = 457
    deleted_branch_count = $targets.Count
    preflight_exact_sha = 'pass'
    atomic_guarded_push = 'pass'
    absence_verification = 'pass'
    deleted_branches = @($preflight)
    verified_absent = @($verifiedAbsent)
    reserved_branches_targeted = $false
    workflow_yaml_mutation = $false
    pr_source_mutation = $false
    issue_mutation = $false
    review_mutation = $false
    ready_transition = $false
    merge_performed = $false
} | ConvertTo-Json -Depth 6 |
    Out-File -LiteralPath (Join-Path $downloads 'issue457-obsolete-branch-cleanup-20260907-receipt.json') -Encoding utf8

Write-Host 'Issue #457 guarded obsolete branch cleanup passed.'
