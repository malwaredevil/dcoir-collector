$ErrorActionPreference = 'Stop'

function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Invoke-NativeCheck {
    param([string]$Label, [string]$CommandLine)
    Write-Host "=== $Label ==="
    $output = @(& cmd.exe /d /c "$CommandLine 2>&1")
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) { Write-Host $line }
    if ($exitCode -ne 0) { throw "$Label failed with exit code $exitCode" }
}

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = [IO.Path]::GetTempPath() }

$expectedHead = 'f42b9d43ea637cc88a5f13329f655b7352b85d84'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestRel = '.github/chatgpt_staging/exec_requests/issue550-pr553-v21-finding-verifier-validation-001.json'
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
$worktree = Join-Path $runnerTemp ('issue550-pr553-v21-validation-' + [Guid]::NewGuid().ToString('N'))
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
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v16_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v19_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v20_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_finding_verifier_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_quality_gate_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_normalized_finding_selection_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_verified_finding_render_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_pipeline_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_routing_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_sentinel_selection_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_repair_reliability_selftest.py',
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
        $retired = @('dcoir_review_required_runtime_patch_v15','dcoir_review_required_runtime_patch_v21','dcoir_review_required_runtime_patch_v22','dcoir_review_required_runtime_patch_v23','dcoir_review_required_runtime_patch_v24','dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v26','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29')
        foreach ($name in $retired) { if ($sequence -contains $name) { throw "Retired module still in production sequence: $name" } }
        $stableOwners = @('dcoir_review.finding_family','dcoir_review.finding_verifier','dcoir_review.quality_gate','dcoir_review.normalized_finding_selection','dcoir_review.verified_finding_render','dcoir_review.repair_pipeline','dcoir_review.sentinel_selection')
        foreach ($name in $stableOwners) { if ($sequence -notcontains $name) { throw "Stable owner missing from production sequence: $name" } }

        $v20Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v20')
        $verifierIndex = [Array]::IndexOf($sequence, 'dcoir_review.finding_verifier')
        $qualityIndex = [Array]::IndexOf($sequence, 'dcoir_review.quality_gate')
        $normalizedIndex = [Array]::IndexOf($sequence, 'dcoir_review.normalized_finding_selection')
        $verifiedIndex = [Array]::IndexOf($sequence, 'dcoir_review.verified_finding_render')
        $repairIndex = [Array]::IndexOf($sequence, 'dcoir_review.repair_pipeline')
        $sentinelIndex = [Array]::IndexOf($sequence, 'dcoir_review.sentinel_selection')
        $v30Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v30')
        if ($v20Index -lt 0 -or $verifierIndex -ne ($v20Index + 1) -or $qualityIndex -ne ($verifierIndex + 1) -or $normalizedIndex -ne ($qualityIndex + 1) -or $verifiedIndex -ne ($normalizedIndex + 1) -or $repairIndex -ne ($verifiedIndex + 1) -or $sentinelIndex -ne ($repairIndex + 1) -or $v30Index -ne ($sentinelIndex + 1)) {
            throw "Stable verifier/quality/selection/render/repair composition mismatch: v20=$v20Index verifier=$verifierIndex quality=$qualityIndex normalized=$normalizedIndex verified=$verifiedIndex repair=$repairIndex sentinel=$sentinelIndex v30=$v30Index"
        }

        foreach ($retiredPath in @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v21.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v21_selftest.py'
        )) { if (Test-Path -LiteralPath $retiredPath) { throw "Retired historical v21 file still exists: $retiredPath" } }
        if (-not (Test-Path -LiteralPath '.github/dcoir_review/scripts/dcoir_review/finding_verifier.py' -PathType Leaf)) { throw 'Stable finding_verifier.py missing' }
        if (-not (Test-Path -LiteralPath '.github/dcoir_review/scripts/dcoir_review_finding_verifier_selftest.py' -PathType Leaf)) { throw 'Stable finding verifier selftest missing' }

        $verifierText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/finding_verifier.py'
        if ($verifierText -notmatch 'VERIFIER_MARKER\s*=\s*["'']_dcoir_verifier_v21["'']') { throw 'Compatibility verifier marker was not preserved' }
        if ($verifierText -match '^VERSION\s*=\s*["'']v21["'']' ) { throw 'Stable verifier still declares historical VERSION v21' }

        foreach ($path in @(
            '.github/dcoir_review/scripts/dcoir_review/finding_family.py',
            '.github/dcoir_review/scripts/dcoir_review/finding_verifier.py',
            '.github/dcoir_review/scripts/dcoir_review/quality_gate.py',
            '.github/dcoir_review/scripts/dcoir_review/normalized_finding_selection.py',
            '.github/dcoir_review/scripts/dcoir_review/verified_finding_render.py',
            '.github/dcoir_review/scripts/dcoir_review/repair.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_pipeline.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_support.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_reliability.py',
            '.github/dcoir_review/scripts/dcoir_review/repair_render.py',
            '.github/dcoir_review/scripts/dcoir_review/sentinel_selection.py'
        )) {
            $bytes = (Get-Item -LiteralPath $path).Length
            Write-Host "connector-safe-size $path = $bytes"
            if ($bytes -gt 15000) { throw "Connector-safe size limit exceeded: $path = $bytes" }
        }

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

        $summaryPath = Join-Path $downloads 'issue550-pr553-v21-finding-verifier-validation-001-summary.txt'
        @(
            'result=PASS',
            "exact_head=$expectedHead",
            "production_components=$($inventory.production_patch_count)",
            "max_numbered_version=$($inventory.max_numbered_version)",
            'retired=v15,v21,v22,v23,v24,v25,v26,v27,v28,v29',
            'finding_verifier_owner=dcoir_review.finding_verifier',
            'composition=v20->finding_verifier->quality_gate->normalized_finding_selection->verified_finding_render->repair_pipeline->sentinel_selection->v30',
            'compatibility_marker=_dcoir_verifier_v21',
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

Write-Output 'ISSUE550_PR553_V21_FINDING_VERIFIER_VALIDATION_001_PASS'
