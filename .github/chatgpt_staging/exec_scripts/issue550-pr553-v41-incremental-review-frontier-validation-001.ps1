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

$expectedHead = '1916d4ecde5dd16f519167d1ef4696fc085bda17'
$expectedTree = 'bb44401f3e69fcde1e624df1025c14413bd9a4af'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestId = 'issue550-pr553-v41-incremental-review-frontier-validation-001'
$requestRel = ".github/chatgpt_staging/exec_requests/$requestId.json"
$requestPath = Join-Path $repo $requestRel
$terminalMarker = 'ISSUE550_PR553_V41_INCREMENTAL_REVIEW_FRONTIER_VALIDATION_001_PASS'
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
    '.github/dcoir_review/scripts/dcoir_review_semantic_evidence_hardening_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_normalization_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_repair_contract_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_repair_contract_critic_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_confidence_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_per_file_coverage_recovery_v40_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_credit_aware_concurrency_v49_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_incremental_review_frontier_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_incremental_review_provenance_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v42_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v43_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v43_state_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_scope_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v44_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_review_context_ledger_integration_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_publication_disposition_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v46_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_verified_finding_gate_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_verified_finding_gate_publication_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_semantic_candidate_identity_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_per_file_routing_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_review_scope_guard_selftest.py',
    '.github/dcoir_review/scripts/dcoir_review_structured_result_recovery_selftest.py',
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
$worktree = Join-Path $runnerTemp ('issue550-pr553-v41-incremental-review-frontier-validation-' + [Guid]::NewGuid().ToString('N'))
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
        Invoke-Checked -Label 'Compile changed Python' -File 'python' -Arguments (@('-m','py_compile') + $changedPython)

        $index = 0
        foreach ($test in $pythonTests) {
            $index += 1
            Invoke-Checked -Label ("Registry {0:D2}/59 {1}" -f $index, $test) -File 'python' -Arguments @($test)
        }
        Invoke-Checked -Label 'Registry 57/59 validate-codex-local' -File $gitBash -Arguments @('.github/dcoir_review/scripts/validate-codex-local.sh')

        Write-Host '=== Registry 58/59 Windows PowerShell parser ==='
        $parserOutput = @(& pwsh -NoProfile -File '.github/dcoir_review/scripts/validate-windows-powershell-51.ps1' -AllowPowerShell7 -AllowEmpty 2>&1)
        if ($LASTEXITCODE -ne 0) { throw "Windows PowerShell parser failed with exit code $LASTEXITCODE" }
        $parserText = $parserOutput -join "`n"
        $parserOutput | ForEach-Object { Write-Host $_ }
        if ($parserText -notmatch 'Validating 293 PowerShell file\(s\)\.') { throw 'Windows parser did not validate expected 293 files' }
        if ($parserText -notmatch 'ASSEMBLED_HARNESS_SHA256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76') { throw 'Windows parser harness SHA mismatch' }

        Invoke-Checked -Label 'Registry 59/59 CodeQL workflow config' -File 'python' -Arguments @('.github/dcoir_review/scripts/validate-codeql-security-workflow.py')

        $semanticOutput = @(& python '.github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py' 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'Semantic recall confirmation failed' }
        $semanticText = $semanticOutput -join "`n"
        if ($semanticText -notmatch '12 cases, 10 finding classes, 2 clean classes') { throw "Unexpected semantic recall summary: $semanticText" }

        $precisionOutput = @(& python '.github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py' 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'Precision confirmation failed' }
        $precision = (($precisionOutput -join "`n") | ConvertFrom-Json)
        if ([double]$precision.false_positive_suppression_rate -ne 1.0) { throw 'False-positive suppression rate changed' }
        if ([double]$precision.true_positive_retention_rate -ne 1.0) { throw 'True-positive retention rate changed' }
        if (@($precision.regressions).Count -ne 0) { throw "Precision regressions detected: $($precision.regressions -join ', ')" }

        $inventory = ((& python '.github/dcoir_review/scripts/dcoir_review_architecture_inventory.py') -join "`n") | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { throw 'Architecture inventory failed' }
        if (@($inventory.missing_modules).Count -ne 0) { throw "Missing inventory modules: $($inventory.missing_modules -join ', ')" }
        if ([int]$inventory.production_patch_count -ne 56) { throw "Expected 56 production components, observed $($inventory.production_patch_count)" }
        if ([int]$inventory.max_numbered_version -ne 57) { throw "Expected max numbered version 57, observed $($inventory.max_numbered_version)" }
        $sequence = @($inventory.production_patch_sequence)
        $retired = @('dcoir_review_required_runtime_patch_v15','dcoir_review_required_runtime_patch_v19','dcoir_review_required_runtime_patch_v21','dcoir_review_required_runtime_patch_v22','dcoir_review_required_runtime_patch_v23','dcoir_review_required_runtime_patch_v24','dcoir_review_required_runtime_patch_v25','dcoir_review_required_runtime_patch_v26','dcoir_review_required_runtime_patch_v27','dcoir_review_required_runtime_patch_v28','dcoir_review_required_runtime_patch_v29','dcoir_review_required_runtime_patch_v34','dcoir_review_required_runtime_patch_v37','dcoir_review_required_runtime_patch_v38','dcoir_review_required_runtime_patch_v39','dcoir_review_required_runtime_patch_v41','dcoir_review_required_runtime_patch_v45','dcoir_review_required_runtime_patch_v50','dcoir_review_required_runtime_patch_v52','dcoir_review_required_runtime_patch_v47','dcoir_review_required_runtime_patch_v48','dcoir_review_required_runtime_patch_v51','dcoir_review_required_runtime_patch_v55','dcoir_review_required_runtime_patch_v58')
        foreach ($name in $retired) { if ($sequence -contains $name) { throw "Retired module still in production sequence: $name" } }
        $stableOwners = @('dcoir_review.finding_family','dcoir_review.precision_guard','dcoir_review.finding_verifier','dcoir_review.quality_gate','dcoir_review.normalized_finding_selection','dcoir_review.verified_finding_render','dcoir_review.publication_disposition','dcoir_review.verified_finding_gate','dcoir_review.incremental_review_frontier','dcoir_review.repair_pipeline','dcoir_review.sentinel_selection','dcoir_review.per_file_routing','dcoir_review.provider_transport_retry','dcoir_review.semantic_adjudication_normalization','dcoir_review.repair_contract','dcoir_review.semantic_adjudication_confidence','dcoir_review.semantic_adjudication_recovery','dcoir_review.semantic_candidate_identity','dcoir_review.semantic_evidence_hardening','dcoir_review.review_scope_guard','dcoir_review.prompt_review_scope_guard','dcoir_review.structured_result_recovery')
        foreach ($name in $stableOwners) { if ($sequence -notcontains $name) { throw "Stable owner missing from production sequence: $name" } }
        $historicalV41 = @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_hooks.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_review_state.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_scope.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v41_provenance_selftest.py'
        )
        foreach ($path in $historicalV41) { if (Test-Path -LiteralPath $path) { throw "Retired historical v41 owner still exists: $path" } }
        $frontierPath = '.github/dcoir_review/scripts/dcoir_review/incremental_review_frontier.py'
        $frontierHooksPath = '.github/dcoir_review/scripts/dcoir_review/incremental_review_frontier_hooks.py'
        $frontierStatePath = '.github/dcoir_review/scripts/dcoir_review/incremental_review_state.py'
        $frontierScopePath = '.github/dcoir_review/scripts/dcoir_review/incremental_review_scope.py'
        foreach ($path in @($frontierPath,$frontierHooksPath,$frontierStatePath,$frontierScopePath)) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Stable incremental-review file missing: $path" }
            $bytes=(Get-Item -LiteralPath $path).Length
            if ($bytes -gt 15000) { throw "Stable incremental-review owner exceeds connector-safe size: $path=$bytes" }
        }
        $frontierText = Get-Content -Raw -LiteralPath $frontierPath
        $frontierHooksText = Get-Content -Raw -LiteralPath $frontierHooksPath
        $frontierStateText = Get-Content -Raw -LiteralPath $frontierStatePath
        $frontierScopeText = Get-Content -Raw -LiteralPath $frontierScopePath
        if (($frontierText + $frontierHooksText + $frontierStateText + $frontierScopeText) -match 'dcoir_review_required_runtime_patch_v41') { throw 'Stable incremental-review family still imports historical v41 ownership' }
        foreach ($literal in @('VERSION = "v41"','ARCHITECTURE_CONTRACT = "architecture-b-v1"','BASE_CONTRACT_PREFIX = "DCOIR review base: "','PROVENANCE_PREFIX = "DCOIR review provenance: "','TRUSTED_WORKFLOW_NAME = "28 Review - DCOIR Review"','TRUSTED_WORKFLOW_PATH = ".github/workflows/openrouter-pr-review.yml"','TRUSTED_WORKFLOW_EVENT = "issue_comment"','TRUSTED_DEFAULT_BRANCH = "main"','dcoir-review-frontier-v1')) { if ($frontierStateText -notmatch [regex]::Escape($literal)) { throw "v41 compatibility contract missing: $literal" } }
        if ($frontierScopeText -notmatch [regex]::Escape('SCOPE_CACHE_ATTR = "_dcoir_review_incremental_scope"')) { throw 'Stable incremental review scope cache marker missing' }
        foreach ($literal in @('_dcoir_review_incremental_frontier_original_get_pr_diff','_dcoir_review_incremental_frontier_original_list_files','_dcoir_review_incremental_frontier_original_build_deep_context_block','_dcoir_review_incremental_frontier_original_write_debug_json_artifact_safely')) { if ($frontierHooksText -notmatch [regex]::Escape($literal)) { throw "Stable frontier hook marker missing: $literal" } }
        if ($frontierText -notmatch 'from dcoir_review\.incremental_review_frontier_hooks import apply_pareto_context_module') { throw 'Frontier owner does not import stable hook installer' }
        if ($frontierText -notmatch 'from dcoir_review\.incremental_review_state import') { throw 'Frontier owner does not import stable review state' }
        if ($frontierText -notmatch 'from dcoir_review\.incremental_review_scope import') { throw 'Frontier owner does not import stable review scope' }
        foreach ($consumer in @('.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v42_fingerprints.py','.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v42_ledger.py','.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v43.py','.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v43_reuse.py','.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v46_context.py','.github/dcoir_review/scripts/dcoir_review/verified_finding_gate_prior.py')) { $consumerText=Get-Content -Raw -LiteralPath $consumer; if ($consumerText -match 'dcoir_review_required_runtime_patch_v41') { throw "Downstream consumer retains historical v41 dependency: $consumer" } }
        $v31FrontierIndex = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v31')
        $frontierIndex = [Array]::IndexOf($sequence, 'dcoir_review.incremental_review_frontier')
        $v42Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v42')
        $v43Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v43')
        if ($v31FrontierIndex -lt 0 -or $frontierIndex -ne ($v31FrontierIndex + 1) -or $v42Index -ne ($frontierIndex + 1) -or $v43Index -ne ($v42Index + 1)) { throw "Incremental-review composition mismatch: v31=$v31FrontierIndex frontier=$frontierIndex v42=$v42Index v43=$v43Index" }
        $frontierBytes = (Get-Item -LiteralPath $frontierPath).Length
        $frontierHooksBytes = (Get-Item -LiteralPath $frontierHooksPath).Length
        $frontierStateBytes = (Get-Item -LiteralPath $frontierStatePath).Length
        $frontierScopeBytes = (Get-Item -LiteralPath $frontierScopePath).Length

        $historicalV52 = @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_provider.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_disposition.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_retry.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py'
        )
        foreach ($path in $historicalV52) { if (Test-Path -LiteralPath $path) { throw "Retired historical v52 owner still exists: $path" } }
        $structuredRecoveryPath = '.github/dcoir_review/scripts/dcoir_review/structured_result_recovery.py'
        $structuredProviderPath = '.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py'
        $structuredDispositionPath = '.github/dcoir_review/scripts/dcoir_review/structured_result_disposition.py'
        $structuredRetryPath = '.github/dcoir_review/scripts/dcoir_review/structured_result_retry.py'
        foreach ($path in @($structuredRecoveryPath,$structuredProviderPath,$structuredDispositionPath,$structuredRetryPath)) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Stable structured-result owner missing: $path" }
            $bytes=(Get-Item -LiteralPath $path).Length
            if ($bytes -gt 15000) { throw "Stable structured-result owner exceeds connector-safe size: $path=$bytes" }
        }
        $structuredRecoveryText = Get-Content -Raw -LiteralPath $structuredRecoveryPath
        $structuredProviderText = Get-Content -Raw -LiteralPath $structuredProviderPath
        $structuredDispositionText = Get-Content -Raw -LiteralPath $structuredDispositionPath
        $structuredRetryText = Get-Content -Raw -LiteralPath $structuredRetryPath
        if ($structuredRecoveryText -match 'dcoir_review_required_runtime_patch_v52') { throw 'Stable structured-result recovery retains historical v52 import' }
        if ($structuredProviderText -match '_dcoir_review_v52_(?:prior|applied)') { throw 'Stable structured-result provider retains private v52 implementation marker' }
        if ($structuredDispositionText -match '_dcoir_review_v52_(?:prior|applied)') { throw 'Stable structured-result disposition retains private v52 implementation marker' }
        foreach ($literal in @('VERSION = "v52"','ALLOW_ATTR = "_dcoir_v52_allow_low_confidence_disposition"','PENDING_ATTR = "_dcoir_v52_pending_low_confidence_disposition"','metadata/v52-structured-low-confidence.json')) {
            if ($structuredDispositionText -notmatch [regex]::Escape($literal)) { throw "v52 disposition compatibility literal missing: $literal" }
        }
        if ($structuredProviderText -notmatch [regex]::Escape('RECOVERY_ATTR = "_dcoir_v52_last_structured_output_recovery"')) { throw 'v52 provider recovery compatibility attr missing' }
        foreach ($literal in @('prompts/10-v52-broad-quality-retry.txt','responses/10-v52-broad-quality-retry.json')) {
            if ($structuredRetryText -notmatch [regex]::Escape($literal)) { throw "v52 retry compatibility artifact missing: $literal" }
        }
        $scopeIndex = [Array]::IndexOf($sequence, 'dcoir_review.review_scope_guard')
        $promptIndex = [Array]::IndexOf($sequence, 'dcoir_review.prompt_review_scope_guard')
        $structuredIndex = [Array]::IndexOf($sequence, 'dcoir_review.structured_result_recovery')
        $v53Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v53')
        if ($scopeIndex -lt 0 -or $promptIndex -ne ($scopeIndex + 1) -or $structuredIndex -ne ($promptIndex + 1) -or $v53Index -ne ($structuredIndex + 1)) {
            throw "Structured-result composition mismatch: scope=$scopeIndex prompt=$promptIndex structured=$structuredIndex v53=$v53Index"
        }
        $v54Text = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py'
        if ($v54Text -notmatch 'from dcoir_review import structured_result_disposition as structured_disposition') { throw 'v54 does not import stable structured-result disposition owner' }
        if ($v54Text -notmatch 'filename == "structured_result_retry.py"') { throw 'v54 does not recognize stable structured-result retry owner' }
        if ($v54Text -match 'dcoir_review_required_runtime_patch_v52_retry.py') { throw 'v54 still hard-codes historical v52 retry filename' }
        if ($v54Text -notmatch 'structured_disposition\.PENDING_ATTR') { throw 'v54 no longer consumes stable pending-disposition contract' }

        $historicalV45 = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v45.py'
        $historicalV45Selftest = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v45_selftest.py'
        foreach ($path in @($historicalV45,$historicalV45Selftest)) { if (Test-Path -LiteralPath $path) { throw "Retired historical v45 owner still exists: $path" } }
        $publicationPath = '.github/dcoir_review/scripts/dcoir_review/publication_disposition.py'
        if (-not (Test-Path -LiteralPath $publicationPath -PathType Leaf)) { throw "Stable publication-disposition owner missing: $publicationPath" }
        $publicationText = Get-Content -Raw -LiteralPath $publicationPath
        if ($publicationText -match '_dcoir_v45_') { throw 'Stable publication-disposition owner retains private v45 implementation markers' }
        if ($publicationText -notmatch '_dcoir_review_publication_disposition_applied') { throw 'Stable publication-disposition apply marker missing' }
        if ($publicationText -notmatch 'VERSION\s*=\s*["'']v45["'']') { throw 'v45 compatibility version changed' }
        if ($publicationText -notmatch 'SCHEMA_VERSION\s*=\s*["'']dcoir_review_final_publication_disposition_v1["'']') { throw 'v45 publication-disposition schema changed' }
        if ($publicationText -notmatch 'ARTIFACT_PATH\s*=\s*["'']metadata/final-publication-disposition-v45\.json["'']') { throw 'v45 publication-disposition artifact path changed' }
        $publicationBytes = (Get-Item -LiteralPath $publicationPath).Length
        if ($publicationBytes -gt 15000) { throw "Stable publication-disposition owner exceeds connector-safe size: $publicationBytes" }
        $v44Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v44')
        $publicationIndex = [Array]::IndexOf($sequence, 'dcoir_review.publication_disposition')
        $v46Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v46')
        if ($v44Index -lt 0 -or $publicationIndex -ne ($v44Index + 1) -or $v46Index -ne ($publicationIndex + 1)) {
            throw "Publication-disposition composition mismatch: v44=$v44Index publication=$publicationIndex v46=$v46Index"
        }
        $v50PublicationText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/verified_finding_gate.py'
        if ($v50PublicationText -notmatch 'from dcoir_review import publication_disposition as publication') { throw 'v50 does not import stable publication-disposition owner' }
        if ($v50PublicationText -match 'dcoir_review_required_runtime_patch_v45') { throw 'v50 still imports historical v45 owner' }
        if ($v50PublicationText -notmatch 'publication\._DISPOSITION_ATTR') { throw 'v50 no longer consumes stable publication disposition state' }
        $v50PriorText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/verified_finding_gate_prior.py'
        if ($v50PriorText -notmatch 'from dcoir_review import publication_disposition as publication') { throw 'v50 prior loader does not import stable publication-disposition owner' }
        if ($v50PriorText -match 'dcoir_review_required_runtime_patch_v45') { throw 'v50 prior loader still imports historical v45 owner' }
        if ($v50PriorText -notmatch 'publication\.ARTIFACT_PATH') { throw 'v50 prior loader no longer consumes stable publication artifact path' }


        $historicalV50 = @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_prior.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_state.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_publication_selftest.py'
        )
        foreach ($path in $historicalV50) { if (Test-Path -LiteralPath $path) { throw "Retired historical v50 owner still exists: $path" } }
        $gatePath = '.github/dcoir_review/scripts/dcoir_review/verified_finding_gate.py'
        $gatePriorPath = '.github/dcoir_review/scripts/dcoir_review/verified_finding_gate_prior.py'
        $gateStatePath = '.github/dcoir_review/scripts/dcoir_review/verified_finding_gate_state.py'
        foreach ($path in @($gatePath,$gatePriorPath,$gateStatePath)) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Stable verified-finding gate file missing: $path" } }
        $gateText = Get-Content -Raw -LiteralPath $gatePath
        $gatePriorText = Get-Content -Raw -LiteralPath $gatePriorPath
        $gateStateText = Get-Content -Raw -LiteralPath $gateStatePath
        if (($gateText + $gatePriorText) -match 'dcoir_review_required_runtime_patch_v50') { throw 'Stable verified-finding gate family still imports historical v50 ownership' }
        if ($gateText -match '_dcoir_v50_(?:applied|original_|prior_gate_context|gate_state|gate_aware)') { throw 'Stable verified-finding gate retains private v50 implementation markers' }
        foreach ($literal in @('_dcoir_review_verified_finding_gate_applied','_dcoir_review_verified_finding_gate_prior_context','_dcoir_review_verified_finding_gate_state','_dcoir_review_verified_finding_gate_aware')) { if ($gateText -notmatch [regex]::Escape($literal)) { throw "Stable verified-finding gate marker missing: $literal" } }
        foreach ($literal in @('VERSION = "v50"','STATE_CONTRACT = "architecture-b-verified-finding-gate-v1"','DISPOSITION_CONTRACT = "architecture-b-verified-finding-gate-disposition-v1"','STATE_ARTIFACT_PATH = "metadata/verified-finding-gate-state-v50.json"','FINAL_ARTIFACT_PATH = "metadata/final-gate-disposition-v50.json"')) { if ($gateStateText -notmatch [regex]::Escape($literal)) { throw "v50 compatibility contract missing: $literal" } }
        foreach ($literal in @('"reason": "trusted-v50-gate-state"','"source": "v50-state"')) { if ($gatePriorText -notmatch [regex]::Escape($literal)) { throw "v50 prior provenance literal missing: $literal" } }
        if ($gateText -notmatch 'from dcoir_review import publication_disposition as publication') { throw 'Stable verified-finding gate no longer imports stable publication-disposition owner' }
        if ($gateText -notmatch 'from dcoir_review import verified_finding_gate_prior as gate_prior') { throw 'Stable verified-finding gate no longer imports stable prior-readback owner' }
        if ($gateText -notmatch 'from dcoir_review import verified_finding_gate_state as gate_state') { throw 'Stable verified-finding gate no longer imports stable state owner' }
        if ($gatePriorText -notmatch 'from dcoir_review import verified_finding_gate_state as state') { throw 'Stable verified-finding prior reader no longer imports stable state owner' }
        if ($gatePriorText -notmatch 'from dcoir_review import publication_disposition as publication') { throw 'Stable verified-finding prior reader no longer imports publication owner' }
        $gateBytes = (Get-Item -LiteralPath $gatePath).Length
        $gatePriorBytes = (Get-Item -LiteralPath $gatePriorPath).Length
        $gateStateBytes = (Get-Item -LiteralPath $gateStatePath).Length
        if ($gateBytes -gt 15000 -or $gatePriorBytes -gt 15000 -or $gateStateBytes -gt 15000) { throw "Stable verified-finding gate family exceeds connector-safe size: gate=$gateBytes prior=$gatePriorBytes state=$gateStateBytes" }
        $v46GateIndex = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v46')
        $gateIndex = [Array]::IndexOf($sequence, 'dcoir_review.verified_finding_gate')
        $identityAfterGateIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_candidate_identity')
        if ($v46GateIndex -lt 0 -or $gateIndex -ne ($v46GateIndex + 1) -or $identityAfterGateIndex -ne ($gateIndex + 1)) { throw "Verified-finding gate composition mismatch: v46=$v46GateIndex gate=$gateIndex identity=$identityAfterGateIndex" }

        $historicalV51 = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v51.py'
        $historicalV51Selftest = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v51_selftest.py'
        foreach ($path in @($historicalV51,$historicalV51Selftest)) { if (Test-Path -LiteralPath $path) { throw "Retired historical v51 owner still exists: $path" } }
        $identityPath = '.github/dcoir_review/scripts/dcoir_review/semantic_candidate_identity.py'
        $identityHooksPath = '.github/dcoir_review/scripts/dcoir_review/semantic_candidate_identity_hooks.py'
        foreach ($path in @($identityPath,$identityHooksPath)) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Stable semantic-candidate identity file missing: $path" } }
        $identityText = Get-Content -Raw -LiteralPath $identityPath
        $identityHooksText = Get-Content -Raw -LiteralPath $identityHooksPath
        if ($identityText -match 'from\s+dcoir_review\s+import\s+finding_verifier\s+as\s+v21') { throw 'Stable semantic-candidate identity owner retains unused verifier import' }
        if ($identityHooksText -match 'from\s+dcoir_review\s+import\s+semantic_candidate_identity|import\s+dcoir_review\.semantic_candidate_identity') { throw 'Stable semantic-candidate identity hooks back-import the owner' }
        if ($identityText -notmatch 'semantic_candidate_identity_hooks\.apply_pareto_context_module\(') { throw 'Stable semantic-candidate identity owner no longer delegates hook installation' }
        if ($identityText -match '_dcoir_v51_(?:applied|original_)') { throw 'Stable semantic-candidate identity owner retains private v51 implementation markers' }
        if ($identityText -notmatch '_dcoir_review_semantic_candidate_identity_applied') { throw 'Stable semantic-candidate identity apply marker missing' }
        foreach ($literal in @('_dcoir_v51_candidate_id','_dcoir_v51_semantic_candidate_key','metadata/v51-candidate-integrity.json','metadata/v51-final-selection-integrity.json','metadata/v51-verifier-candidate-provenance.json','dcoir_review_v51_candidate_integrity_v1','semantic_candidate:')) {
            if (($identityText + $identityHooksText) -notmatch [regex]::Escape($literal)) { throw "v51 compatibility literal missing: $literal" }
        }
        foreach ($literal in @('dcoir_review_v51_final_selection_integrity_v1','dcoir_review_v51_verifier_candidate_provenance_v1')) {
            if ($identityHooksText -notmatch [regex]::Escape($literal)) { throw "v51 hook compatibility schema missing: $literal" }
        }
        $identityBytes = (Get-Item -LiteralPath $identityPath).Length
        $identityHooksBytes = (Get-Item -LiteralPath $identityHooksPath).Length
        if ($identityBytes -gt 15000 -or $identityHooksBytes -gt 15000) { throw "Stable semantic-candidate identity split exceeds connector-safe size: owner=$identityBytes hooks=$identityHooksBytes" }
        $v50Index = [Array]::IndexOf($sequence, 'dcoir_review.verified_finding_gate')
        $identityIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_candidate_identity')
        $perFileIndex = [Array]::IndexOf($sequence, 'dcoir_review.per_file_routing')
        $scopeAfterIdentityIndex = [Array]::IndexOf($sequence, 'dcoir_review.review_scope_guard')
        if ($v50Index -lt 0 -or $identityIndex -ne ($v50Index + 1) -or $perFileIndex -ne ($identityIndex + 1) -or $scopeAfterIdentityIndex -ne ($perFileIndex + 1)) {
            throw "Semantic-candidate identity composition mismatch: v50=$v50Index identity=$identityIndex per_file=$perFileIndex scope=$scopeAfterIdentityIndex"
        }
        $recoveryText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/semantic_adjudication_recovery.py'
        if ($recoveryText -notmatch 'from dcoir_review import semantic_candidate_identity as candidate_identity') { throw 'Semantic recovery does not import stable candidate-identity owner' }
        if ($recoveryText -match 'dcoir_review_required_runtime_patch_v51') { throw 'Semantic recovery still imports historical v51 owner' }

        $v36Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v36')
        $normalizationIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_adjudication_normalization')
        $repairIndex = [Array]::IndexOf($sequence, 'dcoir_review.repair_contract')
        $confidenceIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_adjudication_confidence')
        $v31Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v31')
        if ($v36Index -lt 0 -or $normalizationIndex -ne ($v36Index + 1) -or $repairIndex -ne ($normalizationIndex + 1) -or $confidenceIndex -ne ($repairIndex + 1) -or $v31Index -ne ($confidenceIndex + 1)) {
            throw "Stable composition mismatch: v36=$v36Index normalization=$normalizationIndex repair=$repairIndex confidence=$confidenceIndex v31=$v31Index"
        }

        $historicalV48 = @(
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_core.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_hooks.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_prompt_guard.py'
        )
        foreach ($path in $historicalV48) { if (Test-Path -LiteralPath $path) { throw "Retired historical v48 owner still exists: $path" } }
        $stableScope = '.github/dcoir_review/scripts/dcoir_review/review_scope_guard.py'
        $stableHooks = '.github/dcoir_review/scripts/dcoir_review/review_scope_guard_hooks.py'
        $stablePromptGuard = '.github/dcoir_review/scripts/dcoir_review/prompt_review_scope_guard.py'
        foreach ($path in @($stableScope,$stableHooks,$stablePromptGuard)) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Stable review-scope file missing: $path" } }
        $scopeText = Get-Content -Raw -LiteralPath $stableScope
        $hooksText = Get-Content -Raw -LiteralPath $stableHooks
        $promptGuardText = Get-Content -Raw -LiteralPath $stablePromptGuard
        if ($hooksText -match 'from\s+dcoir_review\s+import\s+review_scope_guard|import\s+dcoir_review\.review_scope_guard') { throw 'Stable review-scope hooks still back-import the scope owner' }
        if ($scopeText -notmatch 'review_scope_guard_hooks\.apply_pareto_context_module\(module,\s*sys\.modules\[__name__\]\)') { throw 'Stable review-scope owner no longer injects its module API into the hook installer' }
        if (($scopeText + $hooksText + $promptGuardText) -match '_dcoir_review_v48_') { throw 'Stable review-scope owners still declare private v48 implementation markers' }
        if ($scopeText -notmatch 'APPLIED_MARKER\s*=\s*["'']_dcoir_review_review_scope_guard_applied["'']') { throw 'Stable review-scope apply marker missing' }
        if ($scopeText -notmatch 'GUARD_ATTR\s*=\s*["'']_dcoir_review_review_scope_guard_context["'']') { throw 'Stable review-scope context marker missing' }
        if ($scopeText -notmatch 'ARTIFACT_PATH\s*=\s*["'']metadata/stale-head-supersession\.json["'']') { throw 'Stable stale-head artifact path changed' }
        if ($scopeText -notmatch 'dcoir_review_stale_head_guard_v1') { throw 'Stable stale-head artifact schema changed' }
        if ($scopeText -notmatch 'DCOIR_REVIEW_SUPERSEDED:') { throw 'Stable supersession terminal prefix changed' }
        if ($scopeText -notmatch 'DCOIR_REVIEW_HEAD_VERIFICATION_FAILED:') { throw 'Stable verification terminal prefix changed' }
        if ($promptGuardText -notmatch 'from dcoir_review import review_scope_guard as scope_core') { throw 'Stable prompt-review guard no longer delegates to stable review-scope authority' }
        $scopeBytes = (Get-Item -LiteralPath $stableScope).Length
        $hooksBytes = (Get-Item -LiteralPath $stableHooks).Length
        $promptGuardBytes = (Get-Item -LiteralPath $stablePromptGuard).Length
        foreach ($pair in @(@('review_scope_guard',$scopeBytes),@('review_scope_guard_hooks',$hooksBytes),@('prompt_review_scope_guard',$promptGuardBytes))) { if ([int]$pair[1] -gt 15000) { throw "Stable $($pair[0]) exceeds connector-safe size: $($pair[1])" } }

        $scopeIndex = [Array]::IndexOf($sequence, 'dcoir_review.review_scope_guard')
        $promptGuardIndex = [Array]::IndexOf($sequence, 'dcoir_review.prompt_review_scope_guard')
        $structuredIndex = [Array]::IndexOf($sequence, 'dcoir_review.structured_result_recovery')
        $v53Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v53')
        if ($scopeIndex -lt 0 -or $promptGuardIndex -ne ($scopeIndex + 1) -or $structuredIndex -ne ($promptGuardIndex + 1) -or $v53Index -ne ($structuredIndex + 1)) {
            throw "Review-scope composition mismatch: scope=$scopeIndex prompt_guard=$promptGuardIndex structured_result=$structuredIndex v53=$v53Index"
        }

        $entrypointText = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
        if ($entrypointText -notmatch '["'']dcoir_review\.review_scope_guard["'']') { throw 'Entrypoint does not compose stable review-scope owner' }
        if ($entrypointText -notmatch '["'']dcoir_review\.prompt_review_scope_guard["'']') { throw 'Entrypoint does not compose stable prompt-review guard owner' }
        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v48["'']') { throw 'Entrypoint still composes historical v48 owner' }

        $structuredProviderText2 = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review/structured_result_provider.py'
        if ($structuredProviderText2 -notmatch 'from dcoir_review import review_scope_guard as review_scope') { throw 'Structured-result provider does not import stable review-scope owner' }
        if ($structuredProviderText2 -notmatch '_dcoir_review_review_scope_guard_original_openrouter_request_once') { throw 'Structured-result provider stable scope-boundary marker missing' }
        if ($structuredProviderText2 -match '_dcoir_review_v48_original_openrouter_request_once') { throw 'Structured-result provider still depends on private v48 provider marker' }

        $provenance = ((& python '.github/dcoir_review/scripts/dcoir_review_runtime_provenance.py') -join "`n") | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { throw 'Runtime provenance failed' }
        $provSequence = @($provenance.production_patch_sequence)
        if ($provSequence.Count -ne 56) { throw "Runtime provenance production count mismatch: $($provSequence.Count)" }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v48') { throw 'Historical v48 owner appears in runtime provenance' }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v48_prompt_guard') { throw 'Historical v48 prompt-review companion appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.review_scope_guard') { throw 'Stable review-scope owner missing from runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.prompt_review_scope_guard') { throw 'Stable prompt-review guard owner missing from runtime provenance' }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v50') { throw 'Historical v50 owner appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.verified_finding_gate') { throw 'Stable verified-finding gate owner missing from runtime provenance' }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v51') { throw 'Historical v51 owner appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.semantic_candidate_identity') { throw 'Stable semantic-candidate identity owner missing from runtime provenance' }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v45') { throw 'Historical v45 owner appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.publication_disposition') { throw 'Stable publication-disposition owner missing from runtime provenance' }
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v52') { throw 'Historical v52 owner appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.structured_result_recovery') { throw 'Stable structured-result recovery owner missing from runtime provenance' }

        $historicalV34 = '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v34.py'
        if (Test-Path -LiteralPath $historicalV34) { throw "Retired historical v34 owner still exists: $historicalV34" }
        $stableEvidence = '.github/dcoir_review/scripts/dcoir_review/semantic_evidence_hardening.py'
        if (-not (Test-Path -LiteralPath $stableEvidence -PathType Leaf)) { throw "Stable semantic-evidence owner missing: $stableEvidence" }
        $stableEvidenceText = Get-Content -Raw -LiteralPath $stableEvidence
        if ($stableEvidenceText -match '_dcoir_review_v34_') { throw 'Stable semantic-evidence owner still declares private v34 implementation markers' }
        if ($stableEvidenceText -notmatch 'APPLIED_MARKER\s*=\s*["'']_dcoir_review_semantic_evidence_hardening_applied["'']') { throw 'Stable semantic-evidence apply marker missing' }
        if ($stableEvidenceText -notmatch 'metadata/v34-verifier-input\.json') { throw 'Historical v34 verifier input artifact path changed' }
        if ($stableEvidenceText -notmatch 'responses/v34-verifier-output\.json') { throw 'Historical v34 verifier output artifact path changed' }
        if ($stableEvidenceText -notmatch 'dcoir_review_v34_verifier_input_v1') { throw 'Historical v34 verifier input schema changed' }
        if ($stableEvidenceText -notmatch 'dcoir_review_v34_verifier_output_v1') { throw 'Historical v34 verifier output schema changed' }
        $stableEvidenceBytes = (Get-Item -LiteralPath $stableEvidence).Length
        if ($stableEvidenceBytes -gt 15000) { throw "Stable semantic-evidence owner exceeds connector-safe size: $stableEvidenceBytes" }

        $v33Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v33')
        $evidenceIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_evidence_hardening')
        $v35Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v35')
        if ($v33Index -lt 0 -or $evidenceIndex -ne ($v33Index + 1) -or $v35Index -ne ($evidenceIndex + 1)) {
            throw "Semantic-evidence composition mismatch: v33=$v33Index stable=$evidenceIndex v35=$v35Index"
        }
        $v35Text = Get-Content -Raw -LiteralPath '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v35.py'
        if ($v35Text -notmatch 'from dcoir_review import semantic_evidence_hardening as semantic_evidence') { throw 'v35 does not import stable semantic-evidence owner' }
        if ($v35Text -match 'dcoir_review_required_runtime_patch_v34') { throw 'v35 still depends on historical v34 owner' }
        if ($v35Text -notmatch 'semantic_evidence\.PREDICATE_AUDIT_BLOCK') { throw 'v35 no longer consumes stable predicate-audit block' }

        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v34') { throw 'Historical v34 owner appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.semantic_evidence_hardening') { throw 'Stable semantic-evidence owner missing from runtime provenance' }

        $v59 = @(Get-ChildItem -Recurse -File '.github/dcoir_review/scripts' | Where-Object { $_.Name -match 'runtime_patch_v(5[9]|[6-9][0-9])' })
        if ($v59.Count -ne 0) { throw "Forbidden v59+ production-style file detected: $($v59.FullName -join ', ')" }

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
            'retired=v15,v19,v21,v22,v23,v24,v25,v26,v27,v28,v29,v34,v37,v38,v39,v41,v45,v47,v48,v50,v51,v52,v55,v58',
            'incremental_review_frontier_owner=dcoir_review.incremental_review_frontier',
            'incremental_review_frontier_helpers=hooks,state,scope',
            'incremental_review_frontier_composition=v31->incremental_review_frontier->v42->v43',
            'v41_compatibility_contract_markers_hmac=preserved',
            "incremental_review_frontier_bytes=$frontierBytes",
            "incremental_review_frontier_hooks_bytes=$frontierHooksBytes",
            "incremental_review_state_bytes=$frontierStateBytes",
            "incremental_review_scope_bytes=$frontierScopeBytes",            'ghas_review_scope_cycle_fix=scope_owner_injection_no_hook_backimport',
            'verified_finding_gate_owner=dcoir_review.verified_finding_gate',
            'verified_finding_gate_helpers=prior,state',
            'verified_finding_gate_composition=v46->verified_finding_gate->semantic_candidate_identity',
            'v50_compatibility_contracts_artifacts_provenance=preserved',
            "verified_finding_gate_bytes=$gateBytes",
            "verified_finding_gate_prior_bytes=$gatePriorBytes",
            "verified_finding_gate_state_bytes=$gateStateBytes",
            'publication_disposition_owner=dcoir_review.publication_disposition',
            'publication_disposition_composition=v44->publication_disposition->v46',
            'v45_compatibility_version_schema_artifact=preserved',
            'structured_result_owner=dcoir_review.structured_result_recovery',
            'structured_result_helpers=provider,disposition,retry',
            'structured_result_composition=review_scope_guard->prompt_review_scope_guard->structured_result_recovery->v53',
            'v52_compatibility_attrs_artifacts=preserved',
            "publication_disposition_bytes=$publicationBytes",
            'semantic_candidate_identity_owner=dcoir_review.semantic_candidate_identity',
            'semantic_candidate_identity_hooks=dcoir_review.semantic_candidate_identity_hooks',
            'semantic_candidate_identity_composition=verified_finding_gate->semantic_candidate_identity->per_file_routing->review_scope_guard',
            'v51_compatibility_fields_artifacts_schemas=preserved',
            "semantic_candidate_identity_bytes=$identityBytes",
            "semantic_candidate_identity_hooks_bytes=$identityHooksBytes",
              'semantic_evidence_hardening_owner=dcoir_review.semantic_evidence_hardening',
            'semantic_evidence_composition=v33->semantic_evidence_hardening->v35',
            'v34_compatibility_artifacts=preserved',
            "semantic_evidence_hardening_bytes=$stableEvidenceBytes",
            'review_scope_guard_owner=dcoir_review.review_scope_guard',
            'prompt_review_scope_guard_owner=dcoir_review.prompt_review_scope_guard',
            'review_scope_composition=review_scope_guard->prompt_review_scope_guard->structured_result_recovery->v53',
            'composition=v36->semantic_adjudication_normalization->repair_contract->semantic_adjudication_confidence->v31',
            'semantic_recall=12_cases_10_finding_2_clean',
            'precision=false_positive_suppression_1.0_true_positive_retention_1.0_no_regressions',
            'windows_parser=293_files',
            'windows_harness_sha256=7a7bf1b5a842c29a42ede8851cf090ab8019adf74fc2ae7a8bd305839a682d76',
            "review_scope_guard_bytes=$scopeBytes",
            "review_scope_guard_hooks_bytes=$hooksBytes",
            "prompt_review_scope_guard_bytes=$promptGuardBytes",
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
