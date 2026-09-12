$ErrorActionPreference = 'Stop'

function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = [IO.Path]::GetTempPath() }

$expectedHead = '1be96623305fdaca08ddb7f686f480ca8525c97b'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestRel = '.github/chatgpt_staging/exec_requests/issue550-pr553-v28-retirement-validation-002.json'
$requestPath = Join-Path $repo $requestRel

$sharedHeadBefore = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read shared harness HEAD' }
$sharedRefLines = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefBefore = if ($LASTEXITCODE -eq 0) { ($sharedRefLines -join "`n").Trim() } else { '' }
if (-not (Test-Path -LiteralPath $requestPath)) { throw "Missing exec request: $requestRel" }
$requestHashBefore = (Get-Sha256Hex -Path $requestPath)

function Invoke-NativeCheck {
    param([string]$Label, [string]$CommandLine)
    Write-Host "=== $Label ==="
    $output = @(& cmd.exe /d /c "$CommandLine 2>&1")
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) { Write-Host $line }
    if ($exitCode -ne 0) { throw "$Label failed with exit code $exitCode" }
}

& git -C $repo fetch --no-tags origin "+refs/heads/$branch`:refs/remotes/origin/$branch" '+refs/heads/main:refs/remotes/origin/main'
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
$actualHead = (& git -C $repo rev-parse "refs/remotes/origin/$branch").Trim()
if ($actualHead -ne $expectedHead) { throw "PR head drift: expected $expectedHead observed $actualHead" }
& git -C $repo merge-base --is-ancestor $base $expectedHead
if ($LASTEXITCODE -ne 0) { throw 'PR base is not an ancestor of target head' }
$liveMain = (& git -C $repo rev-parse 'refs/remotes/origin/main').Trim()
& git -C $repo merge-base --is-ancestor $base $liveMain
if ($LASTEXITCODE -ne 0) { throw 'PR product base is not an ancestor of live main' }
$mainDelta = @(& git -C $repo diff --name-only "$base...$liveMain")
$nonStaging = @($mainDelta | Where-Object { $_ -and $_ -notlike '.github/chatgpt_staging/*' })
if ($nonStaging.Count -ne 0) { throw "Live main product drift detected: $($nonStaging -join ', ')" }

@('OPENROUTER_API_KEY','GITHUB_TOKEN','GH_TOKEN','DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN','DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY') | ForEach-Object {
    [Environment]::SetEnvironmentVariable($_, $null, 'Process')
    Remove-Item ("Env:" + $_) -ErrorAction SilentlyContinue
}
$env:PYTHONDONTWRITEBYTECODE = '1'

$runnerTemp = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$worktree = Join-Path $runnerTemp ('issue550-pr553-repair-validation-' + [Guid]::NewGuid().ToString('N'))
$created = $false
try {
    & git -C $repo worktree add --detach $worktree $expectedHead
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated worktree' }
    $created = $true
    Push-Location $worktree
    try {
        if ((& git rev-parse HEAD).Trim() -ne $expectedHead) { throw 'Wrong isolated worktree head' }

        $changedPython = @(& git diff --name-only "$base...$expectedHead" | Where-Object { $_ -like '*.py' -and (Test-Path -LiteralPath $_) })
        if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate changed Python files' }
        if ($changedPython.Count -eq 0) { throw 'Expected changed Python files' }
        $compileArgs = ($changedPython | ForEach-Object { '"' + $_ + '"' }) -join ' '
        Invoke-NativeCheck 'Compile changed Python' ("python -m py_compile " + $compileArgs)

        $tests = @(
            '.github/dcoir_review/scripts/dcoir_review_repair_pipeline_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_routing_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v26_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_reliability_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v33_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_status_comment_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py'
        )
        foreach ($test in $tests) { Invoke-NativeCheck "Selftest $test" "python $test" }

        Invoke-NativeCheck 'Windows PowerShell validation' 'pwsh -NoProfile -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1 -AllowPowerShell7 -AllowEmpty'
        Invoke-NativeCheck 'CodeQL workflow config validation' 'python .github/dcoir_review/scripts/validate-codeql-security-workflow.py'

        $inventoryText = (& python .github/dcoir_review/scripts/dcoir_review_architecture_inventory.py) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Architecture inventory failed' }
        $inventory = $inventoryText | ConvertFrom-Json
        if (@($inventory.missing_modules).Count -ne 0) { throw "Missing inventory modules: $($inventory.missing_modules -join ', ')" }
        if ([int]$inventory.production_patch_count -ne 56) { throw "Expected 56 production components, observed $($inventory.production_patch_count)" }
        if ([int]$inventory.max_numbered_version -ne 58) { throw "Expected max numbered version 58, observed $($inventory.max_numbered_version)" }
        $sequence = @($inventory.production_patch_sequence)
        foreach ($retired in @('dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29')) {
            if ($sequence -contains $retired) { throw "Retired module still in production sequence: $retired" }
        }
        if ($sequence -notcontains 'dcoir_review.repair_pipeline') { throw 'Canonical repair pipeline missing from production sequence' }
        if ($sequence -contains 'dcoir_review_required_runtime_patch_v28') { throw 'Retired v28 module still in production sequence' }
        foreach ($stableOwner in @('dcoir_review.repair_pipeline','dcoir_review.repair_reliability','dcoir_review.repair_render')) {
            $ownerPath = '.github/dcoir_review/scripts/' + ($stableOwner.Replace('.', '/')) + '.py'
            if (-not (Test-Path -LiteralPath $ownerPath -PathType Leaf)) { throw "Missing stable repair owner: $stableOwner ($ownerPath)" }
        }

        foreach ($retiredPath in @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v25.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v25_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v29.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v29_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v28.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v28_selftest.py'
        )) {
            if (Test-Path -LiteralPath $retiredPath) { throw "Retired historical file still exists: $retiredPath" }
        }

        foreach ($path in @(
            '.github/dcoir_review/scripts/dcoir_review/repair.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_pipeline.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_support.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_reliability.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_render.py'
        )) {
            $bytes = (Get-Item -LiteralPath $path).Length
            Write-Host "connector-safe-size $path = $bytes"
            if ($bytes -gt 15000) { throw "Connector-safe size limit exceeded: $path = $bytes" }
        }

        $provenanceText = (& python .github/dcoir_review/scripts/dcoir_review_runtime_provenance.py) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Runtime provenance failed' }
        $provenance = $provenanceText | ConvertFrom-Json
        if (@($provenance.production_patch_sequence).Count -ne 56) { throw 'Runtime provenance production count mismatch' }
        foreach ($retired in @('dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29')) {
            if (@($provenance.production_patch_sequence) -contains $retired) { throw "Retired module appears in runtime provenance: $retired" }
        }

        & git diff --check "$base...$expectedHead"
        if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
        $dirty = @(& git status --porcelain)
        if ($dirty.Count -ne 0) { throw "Isolated worktree dirty after validation: $($dirty -join ', ')" }

        $summaryPath = Join-Path $downloads 'issue550-pr553-v28-retirement-validation-002-summary.txt'
        @(
            'result=PASS',
            "exact_head=$expectedHead",
            "production_components=$($inventory.production_patch_count)",
            "max_numbered_version=$($inventory.max_numbered_version)",
            'retired=v25,v27,v28,v29',
            'repair_owner=dcoir_review.repair_pipeline',
            'repair_reliability_owner=dcoir_review.repair_reliability',
            'repair_render_owner=dcoir_review.repair_render'
        ) | Out-File -FilePath $summaryPath -Encoding utf8
    }
    finally { Pop-Location }
}
finally {
    if ($created) { & git -C $repo worktree remove --force $worktree | Out-Null }
}

$sharedHeadAfter = (& git -C $repo rev-parse HEAD).Trim()
$sharedRefLinesAfter = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefAfter = if ($LASTEXITCODE -eq 0) { ($sharedRefLinesAfter -join "`n").Trim() } else { '' }
$requestHashAfter = (Get-Sha256Hex -Path $requestPath)
if ($sharedHeadAfter -ne $sharedHeadBefore) { throw "Shared harness HEAD changed: $sharedHeadBefore -> $sharedHeadAfter" }
if ($sharedRefAfter -ne $sharedRefBefore) { throw "Shared harness ref changed: $sharedRefBefore -> $sharedRefAfter" }
if ($requestHashAfter -ne $requestHashBefore) { throw 'Exec request file changed during validation' }

Write-Output 'ISSUE550_PR553_V28_RETIREMENT_VALIDATION_002_PASS'
