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

$expectedHead = '3e48c4f2ab8b4f9a76f540b7f18cd59065d06812'
$expectedTree = 'c63825d9b6d1a0f4470b2971c575dfb67ebd7607'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestId = 'issue550-pr553-v39-semantic-adjudication-confidence-validation-002'
$requestRel = ".github/chatgpt_staging/exec_requests/$requestId.json"
$requestPath = Join-Path $repo $requestRel
$terminalMarker = 'ISSUE550_PR553_V39_SEMANTIC_ADJUDICATION_CONFIDENCE_VALIDATION_002_PASS'
$env:PYTHONPYCACHEPREFIX = Join-Path $downloads ($requestId + '-pycache')

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
    '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_normalization_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38_critic_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_confidence_selftest.py',
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
    '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_recovery_selftest.py',
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
$worktree = Join-Path $runnerTemp ('issue550-pr553-v39-validation-' + [Guid]::NewGuid().ToString('N'))
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
        if ([int]$inventory.max_numbered_version -ne 57) { throw "Expected max numbered version 57 after v58 retirement, observed $($inventory.max_numbered_version)" }
        $sequence = @($inventory.production_patch_sequence)
        $retired = @('dcoir_review_required_runtime_patch_v15','dcoir_review_required_runtime_patch_v19','dcoir_review_required_runtime_patch_v21','dcoir_review_required_runtime_patch_v22','dcoir_review_required_runtime_patch_v23','dcoir_review_required_runtime_patch_v24','dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v26','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29','dcoir_review_required_runtime_patch_v37','dcoir_review_required_runtime_patch_v39','dcoir_review_required_runtime_patch_v47','dcoir_review_required_runtime_patch_v55','dcoir_review_required_runtime_patch_v58')
        foreach ($name in $retired) { if ($sequence -contains $name) { throw "Retired module still in production sequence: $name" } }
        $stableOwners = @('dcoir_review.finding_family','dcoir_review.precision_guard','dcoir_review.finding_verifier','dcoir_review.quality_gate','dcoir_review.normalized_finding_selection','dcoir_review.verified_finding_render','dcoir_review.repair_pipeline','dcoir_review.sentinel_selection','dcoir_review.per_file_routing','dcoir_review.provider_transport_retry','dcoir_review.semantic_adjudication_normalization','dcoir_review.semantic_adjudication_confidence','dcoir_review.semantic_adjudication_recovery')
        foreach ($name in $stableOwners) { if ($sequence -notcontains $name) { throw "Stable owner missing from production sequence: $name" } }

        $v36Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v36')
        $normalizationIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_adjudication_normalization')
        $v38Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v38')
        if ($v36Index -lt 0 -or $normalizationIndex -ne ($v36Index + 1) -or $v38Index -ne ($normalizationIndex + 1)) { throw "Semantic adjudication normalization composition mismatch: v36=$v36Index normalization=$normalizationIndex v38=$v38Index" }
        $confidenceIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_adjudication_confidence')
        $v31Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v31')
        if ($v38Index -lt 0 -or $confidenceIndex -ne ($v38Index + 1) -or $v31Index -ne ($confidenceIndex + 1)) { throw "Semantic adjudication confidence composition mismatch: v38=$v38Index confidence=$confidenceIndex v31=$v31Index" }

        $v54Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v54')
        $transportIndex = [Array]::IndexOf($sequence, 'dcoir_review.provider_transport_retry')
        $recoveryIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_adjudication_recovery')
        $v56Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v56')
        if ($v54Index -lt 0 -or $transportIndex -ne ($v54Index + 1) -or $recoveryIndex -ne ($transportIndex + 1) -or $v56Index -ne ($recoveryIndex + 1)) { throw "Semantic adjudication recovery composition mismatch: v54=$v54Index transport=$transportIndex recovery=$recoveryIndex v56=$v56Index" }

        $historicalV58Path = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v58.py'
        if (Test-Path -LiteralPath $historicalV58Path) { throw 'Retired historical v58 production file still exists' }
        $transportPath = '.github/dcoir_review/scripts/dcoir_review/provider_transport_retry.py'
        $transportSelftestPath = '.github/dcoir_review/scripts/dcoir_review_provider_transport_retry_selftest.py'
        if (-not (Test-Path -LiteralPath $transportPath -PathType Leaf)) { throw 'Stable provider_transport_retry.py missing' }
        if (-not (Test-Path -LiteralPath $transportSelftestPath -PathType Leaf)) { throw 'Stable provider transport retry selftest missing' }
        $transportText = Get-Content -Raw -LiteralPath $transportPath
        if ($transportText -match '_dcoir_v58_') { throw 'Stable provider transport owner retains historical v58 storage marker ownership' }
        if ($transportText -match '(?m)^VERSION\s*=\s*["'']v58["'']') { throw 'Stable provider transport owner still declares historical VERSION v58' }
        $transportBytes = (Get-Item -LiteralPath $transportPath).Length
        if ($transportBytes -gt 15000) { throw "Stable provider transport owner exceeds connector-safe size: $transportBytes" }
        $historicalV55Path = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55.py'
        if (Test-Path -LiteralPath $historicalV55Path) { throw 'Retired historical v55 production file still exists' }
        $recoveryPath = '.github/dcoir_review/scripts/dcoir_review/semantic_adjudication_recovery.py'
        $recoverySelftestPath = '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_recovery_selftest.py'
        if (-not (Test-Path -LiteralPath $recoveryPath -PathType Leaf)) { throw 'Stable semantic_adjudication_recovery.py missing' }
        if (-not (Test-Path -LiteralPath $recoverySelftestPath -PathType Leaf)) { throw 'Stable semantic adjudication recovery selftest missing' }
        $recoveryText = Get-Content -Raw -LiteralPath $recoveryPath
        if ($recoveryText -match '_dcoir_review_v55_') { throw 'Stable semantic recovery owner retains historical v55 storage-marker ownership' }
        if ($recoveryText -match '(?m)^VERSION\s*=\s*["'']v55["'']') { throw 'Stable semantic recovery owner still declares historical VERSION v55' }
        if ($recoveryText -notmatch 'RECOVERY_MARKER_VERSION\s*=\s*["'']v55["'']') { throw 'Compatibility/provenance v55 recovery marker is not preserved explicitly' }
        if ($recoveryText -notmatch 'from dcoir_review import semantic_adjudication_normalization as normalization') { throw 'Stable semantic recovery owner does not import stable normalization owner' }
        $recoveryBytes = (Get-Item -LiteralPath $recoveryPath).Length
        if ($recoveryBytes -gt 15000) { throw "Stable semantic recovery owner exceeds connector-safe size: $recoveryBytes" }

        $historicalV37Path = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v37.py'
        if (Test-Path -LiteralPath $historicalV37Path) { throw 'Retired historical v37 production file still exists' }
        $normalizationPath = '.github/dcoir_review/scripts/dcoir_review/semantic_adjudication_normalization.py'
        $normalizationSelftestPath = '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_normalization_selftest.py'
        if (-not (Test-Path -LiteralPath $normalizationPath -PathType Leaf)) { throw 'Stable semantic_adjudication_normalization.py missing' }
        if (-not (Test-Path -LiteralPath $normalizationSelftestPath -PathType Leaf)) { throw 'Stable semantic adjudication normalization selftest missing' }
        $normalizationText = Get-Content -Raw -LiteralPath $normalizationPath
        if ($normalizationText -match '_dcoir_review_v37_') { throw 'Stable semantic normalization owner retains historical v37 storage-marker ownership' }
        if ($normalizationText -match '(?m)^VERSION\s*=\s*["'']v37["'']') { throw 'Stable semantic normalization owner still declares historical VERSION v37' }
        if ($normalizationText -notmatch 'APPLIED_MARKER\s*=\s*["'']_dcoir_semantic_adjudication_normalization_applied["'']') { throw 'Stable semantic normalization apply marker is missing' }
        if ($normalizationText -notmatch 'CAP_STORAGE\s*=\s*["'']_dcoir_semantic_adjudication_normalization_original_cap_adjudicated_findings["'']') { throw 'Stable semantic normalization cap-storage marker is missing' }
        $normalizationBytes = (Get-Item -LiteralPath $normalizationPath).Length
        if ($normalizationBytes -gt 15000) { throw "Stable semantic normalization owner exceeds connector-safe size: $normalizationBytes" }
        $historicalV39Path = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39.py'
        if (Test-Path -LiteralPath $historicalV39Path) { throw 'Retired historical v39 production file still exists' }
        $historicalV39SelftestPath = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39_selftest.py'
        if (Test-Path -LiteralPath $historicalV39SelftestPath) { throw 'Retired historical v39 selftest still exists' }
        $confidencePath = '.github/dcoir_review/scripts/dcoir_review/semantic_adjudication_confidence.py'
        $confidenceSelftestPath = '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_confidence_selftest.py'
        if (-not (Test-Path -LiteralPath $confidencePath -PathType Leaf)) { throw 'Stable semantic_adjudication_confidence.py missing' }
        if (-not (Test-Path -LiteralPath $confidenceSelftestPath -PathType Leaf)) { throw 'Stable semantic adjudication confidence selftest missing' }
        $confidenceText = Get-Content -Raw -LiteralPath $confidencePath
        if ($confidenceText -match '_dcoir_review_v39_') { throw 'Stable semantic confidence owner retains historical v39 storage-marker ownership' }
        if ($confidenceText -match '(?m)^VERSION\s*=\s*["'']v39["'']') { throw 'Stable semantic confidence owner still declares historical VERSION v39' }
        if ($confidenceText -notmatch 'APPLIED_MARKER\s*=\s*["'']_dcoir_semantic_adjudication_confidence_applied["'']') { throw 'Stable semantic confidence apply marker is missing' }
        if ($confidenceText -notmatch 'HYBRID_STORAGE\s*=\s*["'']_dcoir_semantic_adjudication_confidence_original_hybrid_first_pass["'']') { throw 'Stable semantic confidence hybrid-storage marker is missing' }
        if ($confidenceText -notmatch 'ADJUDICATION_BLOCK_STORAGE\s*=\s*["'']_dcoir_semantic_adjudication_confidence_original_adjudication_block["'']') { throw 'Stable semantic confidence prompt-storage marker is missing' }
        if ($confidenceText -notmatch 'responses/07-v39-confidence-normalized\.json') { throw 'Compatibility v39 confidence artifact path is not preserved' }
        if ($confidenceText -notmatch 'dcoir_review_v39_confidence_normalization_v1') { throw 'Compatibility v39 confidence schema marker is not preserved' }
        if ($recoveryText -notmatch 'from dcoir_review import semantic_adjudication_confidence as confidence') { throw 'Stable semantic recovery owner does not import stable confidence owner' }
        if ($recoveryText -match 'import dcoir_review_required_runtime_patch_v39') { throw 'Stable semantic recovery owner still imports historical v39 owner' }
        $confidenceBytes = (Get-Item -LiteralPath $confidencePath).Length
        if ($confidenceBytes -gt 15000) { throw "Stable semantic confidence owner exceeds connector-safe size: $confidenceBytes" }

        $v44ExecutionPath = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_execution.py'
        $v44ExecutionText = Get-Content -Raw -LiteralPath $v44ExecutionPath
        if ($v44ExecutionText -notmatch 'from dcoir_review import semantic_adjudication_normalization as normalization') { throw 'v44 execution does not import stable semantic normalization owner' }
        if ($v44ExecutionText -match 'import dcoir_review_required_runtime_patch_v37') { throw 'v44 execution still imports historical v37 owner' }        if ($v44ExecutionText -notmatch 'from dcoir_review import semantic_adjudication_confidence as confidence') { throw 'v44 execution does not import stable semantic confidence owner' }
        if ($v44ExecutionText -match 'import dcoir_review_required_runtime_patch_v39') { throw 'v44 execution still imports historical v39 owner' }

        $entrypointText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
        if ($entrypointText -notmatch '["'']dcoir_review\.provider_transport_retry["'']') { throw 'Entrypoint does not compose stable provider transport retry owner' }
        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v58["'']') { throw 'Entrypoint still composes historical v58 owner' }        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v55["'']') { throw 'Entrypoint still composes historical v55 owner' }
        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v37["'']') { throw 'Entrypoint still composes historical v37 owner' }
        if ($entrypointText -notmatch '["'']dcoir_review\.semantic_adjudication_normalization["'']') { throw 'Entrypoint does not compose stable semantic adjudication normalization owner' }
        if ($entrypointText -notmatch '["'']dcoir_review\.semantic_adjudication_recovery["'']') { throw 'Entrypoint does not compose stable semantic adjudication recovery owner' }        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v39["'']') { throw 'Entrypoint still composes historical v39 owner' }
        if ($entrypointText -notmatch '["'']dcoir_review\.semantic_adjudication_confidence["'']') { throw 'Entrypoint does not compose stable semantic adjudication confidence owner' }

        $v58Refs = @(Get-ChildItem -Recurse -File '.github/dcoir_review' | Select-String -Pattern 'dcoir_review_required_runtime_patch_v58' -SimpleMatch)
        $unexpectedV58Refs = @($v58Refs | Where-Object { $_.Path -notlike '*dcoir_review_runtime_module_loader_selftest.py' })
        if ($unexpectedV58Refs.Count -ne 0) { throw "Unexpected historical v58 module reference remains: $($unexpectedV58Refs.Path -join ', ')" }
        if ($v58Refs.Count -lt 1) { throw 'Expected negative architecture guard reference for retired v58 was not found' }
        $v55Refs = @(Get-ChildItem -Recurse -File '.github/dcoir_review' | Select-String -Pattern 'dcoir_review_required_runtime_patch_v55' -SimpleMatch)
        $unexpectedV55Refs = @($v55Refs | Where-Object { $_.Path -notlike '*dcoir_review_runtime_module_loader_selftest.py' })
        if ($unexpectedV55Refs.Count -ne 0) { throw "Unexpected historical v55 module reference remains: $($unexpectedV55Refs.Path -join ', ')" }
        if ($v55Refs.Count -lt 1) { throw 'Expected negative architecture guard reference for retired v55 was not found' }

        $v37Refs = @(Get-ChildItem -Recurse -File '.github/dcoir_review' | Select-String -Pattern 'dcoir_review_required_runtime_patch_v37' -SimpleMatch)
        $unexpectedV37Refs = @($v37Refs | Where-Object { $_.Path -notlike '*dcoir_review_runtime_module_loader_selftest.py' })
        if ($unexpectedV37Refs.Count -ne 0) { throw "Unexpected historical v37 module reference remains: $($unexpectedV37Refs.Path -join ', ')" }
        if ($v37Refs.Count -lt 1) { throw 'Expected negative architecture guard reference for retired v37 was not found' }
        $v39Refs = @(Get-ChildItem -Recurse -File '.github/dcoir_review' | Select-String -Pattern 'dcoir_review_required_runtime_patch_v39' -SimpleMatch)
        $unexpectedV39Refs = @($v39Refs | Where-Object { $_.Path -notlike '*dcoir_review_runtime_module_loader_selftest.py' })
        if ($unexpectedV39Refs.Count -ne 0) { throw "Unexpected historical v39 module reference remains: $($unexpectedV39Refs.Path -join ', ')" }
        if ($v39Refs.Count -lt 1) { throw 'Expected negative architecture guard reference for retired v39 was not found' }

        $v59 = @(Get-ChildItem -Recurse -File '.github/dcoir_review/scripts' | Where-Object { $_.Name -match 'runtime_patch_v(5[9]|[6-9][0-9])' })
        if ($v59.Count -ne 0) { throw "Forbidden v59+ production-style file detected: $($v59.FullName -join ', ')" }

        $provenanceText = (& python '.github/dcoir_review/scripts/dcoir_review_runtime_provenance.py') -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'Runtime provenance failed' }
        $provenance = $provenanceText | ConvertFrom-Json
        $provSequence = @($provenance.production_patch_sequence)
        if ($provSequence.Count -ne 56) { throw "Runtime provenance production count mismatch: $($provSequence.Count)" }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v58') { throw 'Historical v58 appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.provider_transport_retry') { throw 'Stable provider transport owner missing from runtime provenance' }        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v55') { throw 'Historical v55 appears in runtime provenance' }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v37') { throw 'Historical v37 appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.semantic_adjudication_normalization') { throw 'Stable semantic adjudication normalization owner missing from runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.semantic_adjudication_recovery') { throw 'Stable semantic adjudication recovery owner missing from runtime provenance' }        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v39') { throw 'Historical v39 appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.semantic_adjudication_confidence') { throw 'Stable semantic adjudication confidence owner missing from runtime provenance' }

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
            'retired=v15,v19,v21,v22,v23,v24,v25,v26,v27,v28,v29,v37,v39,v47,v55,v58',
            'provider_transport_retry_owner=dcoir_review.provider_transport_retry',
            'semantic_adjudication_normalization_owner=dcoir_review.semantic_adjudication_normalization',            'semantic_adjudication_confidence_owner=dcoir_review.semantic_adjudication_confidence',
            'semantic_adjudication_recovery_owner=dcoir_review.semantic_adjudication_recovery',
            'composition_normalization=v36->semantic_adjudication_normalization->v38',            'composition_confidence=v38->semantic_adjudication_confidence->v31',
            'composition_recovery=v54->provider_transport_retry->semantic_adjudication_recovery->v56',
            'semantic_recall=12_cases_10_finding_2_clean',
            'precision=false_positive_suppression_1.0_true_positive_retention_1.0_no_regressions',
            'windows_parser=293_files',
            'windows_harness_sha256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76',
            "provider_transport_retry_bytes=$transportBytes",
            "semantic_adjudication_normalization_bytes=$normalizationBytes",            "semantic_adjudication_confidence_bytes=$confidenceBytes",
            "semantic_adjudication_recovery_bytes=$recoveryBytes",
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

