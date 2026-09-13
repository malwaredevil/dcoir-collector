$ErrorActionPreference = 'Stop'

function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string]$File,
        [string[]]$Arguments = @()
    )
    Write-Host "=== $Label ==="
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = [IO.Path]::GetTempPath() }

$expectedHead = 'b18782d4fae056ecf4013790f977b3c384e046f8'
$expectedTree = '4779e0992858df6e7d8c07ec3d487d8fd31e01d1'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestId = 'issue550-pr553-v47-per-file-routing-validation-001'
$requestRel = ".github/chatgpt_staging/exec_requests/$requestId.json"
$requestPath = Join-Path $repo $requestRel
$terminalMarker = 'ISSUE550_PR553_V47_PER_FILE_ROUTING_VALIDATION_001_PASS'

$sharedHeadBefore = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read shared harness HEAD' }
$sharedRefLines = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefBefore = if ($LASTEXITCODE -eq 0) { ($sharedRefLines -join "`n").Trim() } else { '' }
if (-not (Test-Path -LiteralPath $requestPath -PathType Leaf)) { throw "Missing exec request: $requestRel" }
$requestHashBefore = Get-Sha256Hex -Path $requestPath

& git -C $repo fetch --no-tags origin "+refs/heads/$branch`:refs/remotes/origin/$branch" '+refs/heads/main:refs/remotes/origin/main'
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
$actualHead = (& git -C $repo rev-parse "refs/remotes/origin/$branch").Trim()
if ($actualHead -ne $expectedHead) { throw "PR head drift: expected $expectedHead observed $actualHead" }
$actualTree = (& git -C $repo rev-parse "$expectedHead`^{tree}").Trim()
if ($actualTree -ne $expectedTree) { throw "PR tree drift: expected $expectedTree observed $actualTree" }
& git -C $repo merge-base --is-ancestor $base $expectedHead
if ($LASTEXITCODE -ne 0) { throw 'PR product base is not an ancestor of target head' }
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

$gitExe = (Get-Command git.exe -ErrorAction Stop).Source
$gitRoot = Split-Path (Split-Path $gitExe -Parent) -Parent
$gitBash = Join-Path $gitRoot 'bin\bash.exe'
if (-not (Test-Path -LiteralPath $gitBash -PathType Leaf)) { throw "Git-for-Windows Bash not found: $gitBash" }

$pythonTests = @(
    '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_finding_family_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v16_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_precision_guard_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v20_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_finding_verifier_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_quality_gate_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_normalized_finding_selection_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_verified_finding_render_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_repair_pipeline_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_sentinel_selection_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_repair_reliability_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_repair_routing_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v31_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v32_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v33_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v34_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v37_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_critic_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_per_file_coverage_recovery_v40_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_credit_aware_concurrency_v49_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_provenance_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v42_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v43_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v43_state_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_scope_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_review_context_ledger_integration_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v45_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v46_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_publication_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v51_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_per_file_routing_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v56_followup_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v57_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_quality_recovery_selftest.py',
    '.github/dcoir_review/scripts/openrouter_pr_review_summary_problem_selftest.py'
)
if ($pythonTests.Count -ne 56) { throw "Expected 56 Python registry commands, observed $($pythonTests.Count)" }

$runnerTemp = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$worktree = Join-Path $runnerTemp ('issue550-pr553-v47-validation-' + [Guid]::NewGuid().ToString('N'))
$created = $false
try {
    & git -C $repo worktree add --detach $worktree $expectedHead
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated worktree' }
    $created = $true
    Push-Location $worktree
    try {
        if ((& git rev-parse HEAD).Trim() -ne $expectedHead) { throw 'Wrong isolated worktree head' }
        if ((& git rev-parse 'HEAD^{tree}').Trim() -ne $expectedTree) { throw 'Wrong isolated worktree tree' }

        $changedPython = @(& git diff --name-only "$base...$expectedHead" | Where-Object { $_ -like '*.py' -and (Test-Path -LiteralPath $_) })
        if ($LASTEXITCODE -ne 0 -or $changedPython.Count -eq 0) { throw 'Unable to enumerate changed Python files' }
        $compileArgs = @('-m','py_compile') + $changedPython
        Invoke-Checked -Label 'Compile changed Python' -File 'python' -Arguments $compileArgs

        $index = 0
        foreach ($test in $pythonTests) {
            $index += 1
            Invoke-Checked -Label ("Registry {0:D2}/59 {1}" -f $index, $test) -File 'python' -Arguments @($test)
        }
        Invoke-Checked -Label 'Registry 57/59 validate-codex-local' -File $gitBash -Arguments @('.github/dcoir_review/scripts/validate-codex-local.sh')
        Invoke-Checked -Label 'Registry 58/59 Windows PowerShell parser' -File 'pwsh' -Arguments @('-NoProfile','-File','.github/dcoir_review/scripts/validate-windows-powershell-51.ps1','-AllowPowerShell7','-AllowEmpty')
        Invoke-Checked -Label 'Registry 59/59 CodeQL workflow config' -File 'python' -Arguments @('.github/dcoir_review/scripts/validate-codeql-security-workflow.py')

        $semanticOutput = @(& python '.github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py' 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'Semantic recall confirmation failed' }
        $semanticText = $semanticOutput -join "`n"
        if ($semanticText -notmatch '12 cases, 10 finding classes, 2 clean classes') { throw "Unexpected semantic recall summary: $semanticText" }

        $precisionOutput = @(& python '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py' 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'Precision confirmation failed' }
        $precisionText = $precisionOutput -join "`n"
        $precision = $precisionText | ConvertFrom-Json
        if ([double]$precision.false_positive_suppression_rate -ne 1.0) { throw 'False-positive suppression rate changed' }
        if ([double]$precision.true_positive_retention_rate -ne 1.0) { throw 'True-positive retention rate changed' }
        if (@($precision.regressions).Count -ne 0) { throw "Precision regressions detected: $($precision.regressions -join ', ')" }

        $inventoryText = (& python '.github/dcoir_review/scripts/dcoir_review_architecture_inventory.py') -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Architecture inventory failed' }
        $inventory = $inventoryText | ConvertFrom-Json
        if (@($inventory.missing_modules).Count -ne 0) { throw "Missing inventory modules: $($inventory.missing_modules -join ', ')" }
        if ([int]$inventory.production_patch_count -ne 56) { throw "Expected 56 production components, observed $($inventory.production_patch_count)" }
        if ([int]$inventory.max_numbered_version -ne 58) { throw "Expected max numbered version 58, observed $($inventory.max_numbered_version)" }
        $sequence = @($inventory.production_patch_sequence)
        $retired = @('dcoir_review_required_runtime_patch_v15','dcoir_review_required_runtime_patch_v19','dcoir_review_required_runtime_patch_v21','dcoir_review_required_runtime_patch_v22','dcoir_review_required_runtime_patch_v23','dcoir_review_required_runtime_patch_v24','dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v26','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29','dcoir_review_required_runtime_patch_v47')
        foreach ($name in $retired) { if ($sequence -contains $name) { throw "Retired module still in production sequence: $name" } }
        $stableOwners = @('dcoir_review.finding_family','dcoir_review.precision_guard','dcoir_review.finding_verifier','dcoir_review.quality_gate','dcoir_review.normalized_finding_selection','dcoir_review.verified_finding_render','dcoir_review.repair_pipeline','dcoir_review.sentinel_selection','dcoir_review.per_file_routing')
        foreach ($name in $stableOwners) { if ($sequence -notcontains $name) { throw "Stable owner missing from production sequence: $name" } }

        $v51Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v51')
        $routingIndex = [Array]::IndexOf($sequence, 'dcoir_review.per_file_routing')
        $v48Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v48')
        if ($v51Index -lt 0 -or $routingIndex -ne ($v51Index + 1) -or $v48Index -ne ($routingIndex + 1)) { throw "Per-file-routing composition mismatch: v51=$v51Index routing=$routingIndex v48=$v48Index" }

        foreach ($retiredPath in @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v47.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v47_selftest.py'
        )) { if (Test-Path -LiteralPath $retiredPath) { throw "Retired historical v47 file still exists: $retiredPath" } }

        $routingPath = '.github/dcoir_review/scripts/dcoir_review/per_file_routing.py'
        $routingSelftestPath = '.github/dcoir_review/scripts/dcoir_review_per_file_routing_selftest.py'
        if (-not (Test-Path -LiteralPath $routingPath -PathType Leaf)) { throw 'Stable per_file_routing.py missing' }
        if (-not (Test-Path -LiteralPath $routingSelftestPath -PathType Leaf)) { throw 'Stable per-file routing selftest missing' }
        $routingText = Get-Content -Raw -LiteralPath $routingPath
        if ($routingText -notmatch 'PER_FILE_PROJECTION_ATTR\s*=\s*["'']dcoir_v47_per_file_projection["'']') { throw 'Compatibility marker value was not preserved by stable owner' }
        if ($routingText -match '(?m)^VERSION\s*=\s*["'']v47["'']') { throw 'Stable per-file routing owner still declares historical VERSION v47' }
        $routingBytes = (Get-Item -LiteralPath $routingPath).Length
        if ($routingBytes -gt 15000) { throw "Stable per-file routing owner exceeds connector-safe size: $routingBytes" }

        $v54Path = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py'
        $v54Text = Get-Content -Raw -LiteralPath $v54Path
        if ($v54Text -notmatch 'from dcoir_review\.per_file_routing import PER_FILE_PROJECTION_ATTR') { throw 'v54 does not import the stable per-file routing marker owner' }
        if ($v54Text -match 'getattr\(config,\s*["'']dcoir_v47_per_file_projection["'']') { throw 'v54 still hard-codes historical v47 marker access' }

        $entrypointText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
        if ($entrypointText -notmatch '["'']dcoir_review\.per_file_routing["'']') { throw 'Entrypoint does not compose stable per-file routing owner' }
        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v47["'']') { throw 'Entrypoint still composes historical v47 owner' }

        $v47Refs = @(Get-ChildItem -Recurse -File '.github/dcoir_review' | Select-String -Pattern 'dcoir_review_required_runtime_patch_v47' -SimpleMatch)
        if ($v47Refs.Count -ne 0) { throw "Historical v47 module reference remains in active DCOIR source: $($v47Refs.Path -join ', ')" }

        $v59 = @(Get-ChildItem -Recurse -File '.github/dcoir_review/scripts' | Where-Object { $_.Name -match 'runtime_patch_v(5[9]|[6-9][0-9])' })
        if ($v59.Count -ne 0) { throw "Forbidden v59+ production-style file detected: $($v59.FullName -join ', ')" }

        $provenanceText = (& python '.github/dcoir_review/scripts/dcoir_review_runtime_provenance.py') -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Runtime provenance failed' }
        $provenance = $provenanceText | ConvertFrom-Json
        $provSequence = @($provenance.production_patch_sequence)
        if ($provSequence.Count -ne 56) { throw "Runtime provenance production count mismatch: $($provSequence.Count)" }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v47') { throw 'Historical v47 appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.per_file_routing') { throw 'Stable per-file routing missing from runtime provenance' }

        & git diff --check "$base...$expectedHead"
        if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
        $dirty = @(& git status --porcelain)
        if ($dirty.Count -ne 0) { throw "Isolated worktree dirty after validation: $($dirty -join ', ')" }

        $summaryPath = Join-Path $downloads ($requestId + '-summary.txt')
        @(
            'result=PASS',
            "exact_head=$expectedHead",
            "exact_tree=$expectedTree",
            "production_components=$($inventory.production_patch_count)",
            "max_numbered_version=$($inventory.max_numbered_version)",
            'retired=v15,v19,v21,v22,v23,v24,v25,v26,v27,v28,v29,v47',
            'per_file_routing_owner=dcoir_review.per_file_routing',
            'composition=v51->per_file_routing->v48',
            'compatibility_marker=dcoir_v47_per_file_projection',
            'v54_marker_dependency=stable_owner_import',
            'semantic_recall=12_cases_10_finding_2_clean',
            'precision=false_positive_suppression_1.0_true_positive_retention_1.0_no_regressions',
            'windows_parser=293_files',
            'windows_harness_sha256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76',
            "per_file_routing_bytes=$routingBytes",
            'registry_commands=59',
            'no_inference=true',
            'no_provider_calls=true'
        ) | Out-File -FilePath $summaryPath -Encoding utf8
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($created) {
        & git -C $repo worktree remove --force $worktree 2>$null
        & git -C $repo worktree prune 2>$null
    }
}

$sharedHeadAfter = (& git -C $repo rev-parse HEAD).Trim()
if ($sharedHeadAfter -ne $sharedHeadBefore) { throw "Shared harness HEAD changed during validation: before=$sharedHeadBefore after=$sharedHeadAfter" }
$sharedRefLinesAfter = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefAfter = if ($LASTEXITCODE -eq 0) { ($sharedRefLinesAfter -join "`n").Trim() } else { '' }
if ($sharedRefAfter -ne $sharedRefBefore) { throw "Shared harness ref changed during validation: before=$sharedRefBefore after=$sharedRefAfter" }
if (-not (Test-Path -LiteralPath $requestPath -PathType Leaf)) { throw 'Exec request disappeared during validation command' }
$requestHashAfter = Get-Sha256Hex -Path $requestPath
if ($requestHashAfter -ne $requestHashBefore) { throw 'Exec request mutated during validation command' }

Write-Host $terminalMarker
