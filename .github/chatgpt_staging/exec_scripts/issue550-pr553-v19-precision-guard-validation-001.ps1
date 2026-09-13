$ErrorActionPreference = 'Stop'

function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Invoke-NativeCheck {
    param([string]$Label, [string]$CommandLine)
    Write-Host "=== $Label ==="
    $output = @(& cmd.exe /d /c "$CommandLine 2>&1")
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) { Write-Host $line }
    if ($exitCode -ne 0) { throw "$Label failed with exit code $exitCode" }
    return $output
}

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = [IO.Path]::GetTempPath() }

$expectedHead = '9b7d3d35bfac3b99d7ed09a5be640deb398dcbf4'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestRel = '.github/chatgpt_staging/exec_requests/issue550-pr553-v19-precision-guard-validation-001.json'
$requestPath = Join-Path $repo $requestRel

$sharedHeadBefore = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read shared harness HEAD' }
$sharedRefLines = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefBefore = if ($LASTEXITCODE -eq 0) { ($sharedRefLines -join "`n").Trim() } else { '' }
if (-not (Test-Path -LiteralPath $requestPath)) { throw "Missing exec request: $requestRel" }
$requestHashBefore = Get-Sha256Hex -Path $requestPath

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
$worktree = Join-Path $runnerTemp ('issue550-pr553-v19-validation-' + [Guid]::NewGuid().ToString('N'))
$created = $false
try {
    & git -C $repo worktree add --detach $worktree $expectedHead
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated worktree' }
    $created = $true
    Push-Location $worktree
    try {
        if ((& git rev-parse HEAD).Trim() -ne $expectedHead) { throw 'Wrong isolated worktree head' }

        $changedPython = @(& git diff --name-only "$base...$expectedHead" | Where-Object { $_ -like '*.py' -and (Test-Path -LiteralPath $_) })
        if ($LASTEXITCODE -ne 0 -or $changedPython.Count -eq 0) { throw 'Unable to enumerate changed Python files' }
        $compileArgs = ($changedPython | ForEach-Object { '"' + $_ + '"' }) -join ' '
        Invoke-NativeCheck 'Compile changed Python' ("python -m py_compile " + $compileArgs) | Out-Null

        $tests = @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v16_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v17_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v18_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_precision_guard_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v20_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_finding_verifier_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_quality_gate_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_normalized_finding_selection_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_verified_finding_render_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_pipeline_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_sentinel_selection_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_reliability_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_routing_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v33_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v34_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v45_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_publication_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v51_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_followup_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py'
        )
        foreach ($test in $tests) { Invoke-NativeCheck "Selftest $test" "python $test" | Out-Null }

        $parserOutput = Invoke-NativeCheck 'Windows PowerShell validation' 'pwsh -NoProfile -File .github/dcoir_review/scripts/validate-windows-powershell-51.ps1 -AllowPowerShell7 -AllowEmpty'
        $parserText = $parserOutput -join "`n"
        if ($parserText -notmatch 'Validating 293 PowerShell file\(s\)\.') { throw 'Windows parser did not validate expected 293 files' }
        if ($parserText -notmatch 'ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76') { throw 'Windows parser harness SHA mismatch' }
        Invoke-NativeCheck 'CodeQL workflow config validation' 'python .github/dcoir_review/scripts/validate-codeql-security-workflow.py' | Out-Null

        $inventoryText = (& python .github/dcoir_review/scripts/dcoir_review_architecture_inventory.py) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Architecture inventory failed' }
        $inventory = $inventoryText | ConvertFrom-Json
        if (@($inventory.missing_modules).Count -ne 0) { throw "Missing inventory modules: $($inventory.missing_modules -join ', ')" }
        if ([int]$inventory.production_patch_count -ne 56) { throw "Expected 56 production components, observed $($inventory.production_patch_count)" }
        if ([int]$inventory.max_numbered_version -ne 58) { throw "Expected max numbered version 58, observed $($inventory.max_numbered_version)" }
        $sequence = @($inventory.production_patch_sequence)
        $retired = @('dcoir_review_required_runtime_patch_v15','dcoir_review_required_runtime_patch_v19','dcoir_review_required_runtime_patch_v21','dcoir_review_required_runtime_patch_v22','dcoir_review_required_runtime_patch_v23','dcoir_review_required_runtime_patch_v24','dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v26','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29')
        foreach ($name in $retired) { if ($sequence -contains $name) { throw "Retired module still in production sequence: $name" } }
        $stableOwners = @('dcoir_review.finding_family','dcoir_review.precision_guard','dcoir_review.finding_verifier','dcoir_review.quality_gate','dcoir_review.normalized_finding_selection','dcoir_review.verified_finding_render','dcoir_review.repair_pipeline','dcoir_review.sentinel_selection')
        foreach ($name in $stableOwners) { if ($sequence -notcontains $name) { throw "Stable owner missing from production sequence: $name" } }

        $v18Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v18')
        $guardIndex = [Array]::IndexOf($sequence, 'dcoir_review.precision_guard')
        $v20Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v20')
        if ($v18Index -lt 0 -or $guardIndex -ne ($v18Index + 1) -or $v20Index -ne ($guardIndex + 1)) { throw "Precision-guard composition mismatch: v18=$v18Index guard=$guardIndex v20=$v20Index" }

        foreach ($retiredPath in @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v19.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v19_selftest.py'
        )) { if (Test-Path -LiteralPath $retiredPath) { throw "Retired historical v19 file still exists: $retiredPath" } }
        $guardPath = '.github/dcoir_review/scripts/dcoir_review/precision_guard.py'
        if (-not (Test-Path -LiteralPath $guardPath -PathType Leaf)) { throw 'Stable precision_guard.py missing' }
        if (-not (Test-Path -LiteralPath '.github/dcoir_review/scripts/dcoir_review_precision_guard_selftest.py' -PathType Leaf)) { throw 'Stable precision guard selftest missing' }
        $guardText = Get-Content -Raw -LiteralPath $guardPath
        if ($guardText -notmatch 'OUTCOME_ARTIFACT\s*=\s*["'']metadata/fix-synthesis-outcomes-v19\.json["'']') { throw 'Legacy v19 outcome artifact path was not preserved' }
        if ($guardText -notmatch 'ARTIFACT_SCHEMA_VERSION\s*=\s*["'']v19["'']') { throw 'Legacy v19 artifact schema marker was not preserved' }
        if ($guardText -match '(?m)^VERSION\s*=\s*["'']v19["'']') { throw 'Stable precision guard still declares historical VERSION v19' }
        $guardBytes = (Get-Item -LiteralPath $guardPath).Length
        Write-Host "connector-safe-size $guardPath = $guardBytes"
        if ($guardBytes -gt 15000) { throw "Connector-safe size limit exceeded: $guardBytes" }

        $v59 = @(Get-ChildItem -Recurse -File '.github/dcoir_review/scripts' | Where-Object { $_.Name -match 'runtime_patch_v(5[9]|[6-9][0-9])' })
        if ($v59.Count -ne 0) { throw "Forbidden v59+ production-style file detected: $($v59.FullName -join ', ')" }
        $provenanceText = (& python .github/dcoir_review/scripts/dcoir_review_runtime_provenance.py) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Runtime provenance failed' }
        $provenance = $provenanceText | ConvertFrom-Json
        if (@($provenance.production_patch_sequence).Count -ne 56) { throw 'Runtime provenance production count mismatch' }
        foreach ($name in $retired) { if (@($provenance.production_patch_sequence) -contains $name) { throw "Retired module appears in runtime provenance: $name" } }

        & git diff --check "$base...$expectedHead"
        if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
        $dirty = @(& git status --porcelain)
        if ($dirty.Count -ne 0) { throw "Isolated worktree dirty after validation: $($dirty -join ', ')" }

        $summaryPath = Join-Path $downloads 'issue550-pr553-v19-precision-guard-validation-001-summary.txt'
        @(
            'result=PASS',
            "exact_head=$expectedHead",
            "production_components=$($inventory.production_patch_count)",
            "max_numbered_version=$($inventory.max_numbered_version)",
            'retired=v15,v19,v21,v22,v23,v24,v25,v26,v27,v28,v29',
            'precision_guard_owner=dcoir_review.precision_guard',
            'composition=v18->precision_guard->v20',
            'compatibility_artifact=metadata/fix-synthesis-outcomes-v19.json',
            'compatibility_schema=v19',
            'semantic_recall=12_cases_10_finding_2_clean',
            'precision=false_positive_suppression_1.0_true_positive_retention_1.0_no_regressions',
            'windows_parser=293_files',
            'windows_harness_sha256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76',
            "precision_guard_bytes=$guardBytes",
            'no_inference=true',
            'no_provider_calls=true'
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
$requestHashAfter = Get-Sha256Hex -Path $requestPath
if ($sharedHeadAfter -ne $sharedHeadBefore) { throw "Shared harness HEAD changed: $sharedHeadBefore -> $sharedHeadAfter" }
if ($sharedRefAfter -ne $sharedRefBefore) { throw "Shared harness ref changed: $sharedRefBefore -> $sharedRefAfter" }
if ($requestHashAfter -ne $requestHashBefore) { throw 'Exec request file changed during validation' }

Write-Output 'ISSUE550_PR553_V19_PRECISION_GUARD_VALIDATION_001_PASS'