$ErrorActionPreference = 'Stop'

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is unavailable' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is unavailable' }

$expectedHead = 'fc8c400ae0991728687a2797d40cf361dba8839d'
$base = '9dc055d81fba2bcd4e840ad1e9c9645bdc6a6a20'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestRel = '.github/chatgpt_staging/exec_requests/issue550-pr553-first-patch-retirement-validation-003.json'
$requestPath = Join-Path $repo $requestRel

$sharedHeadBefore = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read shared checkout HEAD' }
$sharedRefLines = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefBefore = if ($LASTEXITCODE -eq 0) { ($sharedRefLines -join "`n").Trim() } else { '' }
if (-not (Test-Path -LiteralPath $requestPath)) { throw "Exec request missing: $requestRel" }

& git -C $repo fetch --no-tags origin "+refs/heads/$branch`:refs/remotes/origin/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch PR branch' }
$actualHead = (& git -C $repo rev-parse "refs/remotes/origin/$branch").Trim()
if ($LASTEXITCODE -ne 0 -or $actualHead -ne $expectedHead) { throw "PR head drift: expected $expectedHead observed $actualHead" }
& git -C $repo merge-base --is-ancestor $base $expectedHead
if ($LASTEXITCODE -ne 0) { throw 'Expected product base is not ancestor of PR head' }

& git -C $repo fetch --no-tags origin '+refs/heads/main:refs/remotes/origin/main'
if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch live main' }
$liveMain = (& git -C $repo rev-parse 'refs/remotes/origin/main').Trim()
& git -C $repo merge-base --is-ancestor $base $liveMain
if ($LASTEXITCODE -ne 0) { throw "Product base is no longer ancestor of live main $liveMain" }
$mainDelta = @(& git -C $repo diff --name-only "$base...$liveMain")
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect live-main movement' }
$nonStagingMainDelta = @($mainDelta | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -notlike '.github/chatgpt_staging/*' })
if ($nonStagingMainDelta.Count -ne 0) { throw "Live main contains non-staging movement: $($nonStagingMainDelta -join ', ')" }

foreach ($name in @('DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN','DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY')) {
    [Environment]::SetEnvironmentVariable($name, $null, 'Machine')
    [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

function Invoke-NativeCheck {
    param([string]$Label,[string]$CommandLine)
    Write-Host "=== $Label ==="
    $output = @(& cmd.exe /d /c "$CommandLine 2>&1")
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) { Write-Host $line }
    if ($exitCode -ne 0) { throw "$Label failed with exit code $exitCode" }
}

$runnerTemp = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$worktree = Join-Path $runnerTemp ('dcoir-pr553-first-retirement-validation-' + [Guid]::NewGuid().ToString('N'))
$worktreeCreated = $false
$capturedError = $null
$cleanupError = $null

try {
    & git -C $repo worktree add --detach $worktree $expectedHead
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated validation worktree' }
    $worktreeCreated = $true
    Push-Location $worktree
    try {
        $observed = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $observed -ne $expectedHead) { throw "Worktree head mismatch: $observed" }

        $expectedFiles = @(
            '.github/dcoir_review/ARCHITECTURE.md',
            '.github/dcoir_review/scripts/dcoir_review/base/part_01a_progress_diff.py',
            '.github/dcoir_review/scripts/dcoir_review/base/part_07_main.py',
            '.github/dcoir_review/scripts/dcoir_review/entrypoint.py',
            '.github/dcoir_review/scripts/dcoir_review/hardened/part_07_review_body_main.py',
            '.github/dcoir_review/scripts/dcoir_review/pareto_context/part_08_review_body_main.py',
            '.github/dcoir_review/scripts/dcoir_review/pareto_context/part_08a_review_body_main.py',
            '.github/dcoir_review/scripts/dcoir_review/selftests/base_selftest/part_03.py',
            '.github/dcoir_review/scripts/dcoir_review/selftests/pareto_context_selftest/part_01a.py',
            '.github/dcoir_review/scripts/dcoir_review/status.py',
            '.github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_architecture_inventory.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_runtime_provenance.py',
            '.github/dcoir_review/scripts/dcoir_review_status_comment_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py'
        )
        $changedFiles = @(& git diff --name-only "$base...$expectedHead")
        if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect PR scope' }
        $scopeDelta = @(Compare-Object -ReferenceObject ($expectedFiles | Sort-Object) -DifferenceObject ($changedFiles | Sort-Object))
        if ($scopeDelta.Count -ne 0) { throw "Unexpected PR scope: $($changedFiles -join ', ')" }
        if (Test-Path '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27.py') { throw 'Retired v27 source still present' }

        $changedPython = @(& git diff --name-only --diff-filter=ACMRT "$base...$expectedHead" | Where-Object { $_ -like '*.py' })
        if ($LASTEXITCODE -ne 0 -or $changedPython.Count -eq 0) { throw 'Unable to determine changed Python scope' }
        Invoke-NativeCheck 'Python compilation' ('python -m py_compile ' + ($changedPython -join ' '))

        $tests = @(
            '.github/dcoir_review/scripts/dcoir_review_anchor_normalization_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v27_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v26_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v28_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v29_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v30_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_status_comment_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py',
            '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v50_selftest.py',
            '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
        )
        foreach ($test in $tests) { Invoke-NativeCheck "Selftest $test" "python $test" }

        $inventoryPath = Join-Path $downloads 'dcoir-review-first-patch-retirement-inventory.json'
        $inventoryOutput = @(& cmd.exe /d /c "python .github/dcoir_review/scripts/dcoir_review_architecture_inventory.py 2>&1")
        if ($LASTEXITCODE -ne 0) { foreach ($line in $inventoryOutput) { Write-Host $line }; throw 'Architecture inventory failed' }
        $inventoryText = $inventoryOutput -join "`r`n"
        $inventoryText | Out-File $inventoryPath -Encoding utf8
        $inventory = $inventoryText | ConvertFrom-Json
        if (@($inventory.missing_modules).Count -ne 0) { throw "Missing inventory modules: $($inventory.missing_modules -join ', ')" }
        if ([int]$inventory.max_numbered_version -ne 58) { throw "Unexpected max numbered version: $($inventory.max_numbered_version)" }
        if ([int]$inventory.production_patch_count -ne 58) { throw "Expected 58 production patches; observed $($inventory.production_patch_count)" }
        if (@($inventory.production_patch_sequence) -contains 'dcoir_review_required_runtime_patch_v27') { throw 'v27 remains in production patch sequence' }

        $provenancePath = Join-Path $downloads 'dcoir-review-first-patch-retirement-provenance.json'
        $provenanceOutput = @(& cmd.exe /d /c "python .github/dcoir_review/scripts/dcoir_review_runtime_provenance.py 2>&1")
        if ($LASTEXITCODE -ne 0) { foreach ($line in $provenanceOutput) { Write-Host $line }; throw 'Runtime provenance failed' }
        $provenanceText = $provenanceOutput -join "`r`n"
        $provenanceText | Out-File $provenancePath -Encoding utf8
        $provenance = $provenanceText | ConvertFrom-Json
        if (@($provenance.production_patch_sequence).Count -ne 58) { throw "Unexpected provenance production patch count: $(@($provenance.production_patch_sequence).Count)" }
        if (@($provenance.production_patch_sequence) -contains 'dcoir_review_required_runtime_patch_v27') { throw 'Runtime provenance still contains v27' }
        $patchOwned = $provenance.final_namespaces.review.patch_owned_callables
        $reanchorOwner = $patchOwned.PSObject.Properties['reanchor_finding_to_changed_line']
        if ($null -ne $reanchorOwner) { throw "reanchor_finding_to_changed_line remains patch-owned: $([string]$reanchorOwner.Value.module)" }

        Write-Host "Inventory module count: $($inventory.inventory_module_count)"
        Write-Host "Production patch applications: $($inventory.production_patch_count)"
        Write-Host "Maximum numbered patch version: $($inventory.max_numbered_version)"
        & git diff --check "$base...$expectedHead"
        if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
        $state = @(& git status --porcelain)
        if ($state.Count -ne 0) { throw "Validation modified worktree: $($state -join '; ')" }
    }
    finally { Pop-Location }
}
catch { $capturedError = $_ }
finally {
    if ($worktreeCreated) {
        & git -C $repo worktree remove --force $worktree
        if ($LASTEXITCODE -ne 0) { $cleanupError = "Failed to remove worktree: $worktree" }
    }
}

$sharedHeadAfter = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read shared checkout HEAD after validation' }
$sharedRefLines = @(& git -C $repo symbolic-ref --quiet --short HEAD 2>$null)
$sharedRefAfter = if ($LASTEXITCODE -eq 0) { ($sharedRefLines -join "`n").Trim() } else { '' }
if ($sharedHeadAfter -ne $sharedHeadBefore) { throw "Shared checkout HEAD changed: before=$sharedHeadBefore after=$sharedHeadAfter" }
if ($sharedRefAfter -ne $sharedRefBefore) { throw "Shared checkout ref changed: before=$sharedRefBefore after=$sharedRefAfter" }
if (-not (Test-Path -LiteralPath $requestPath)) { throw 'Shared request disappeared during validation' }
if ($null -ne $cleanupError) { throw $cleanupError }
if ($null -ne $capturedError) { throw $capturedError }

Write-Host "PR #553 first patch-retirement validation passed at exact head: $expectedHead"
Write-Host "Live main observed: $liveMain"
Write-Host "Architecture inventory artifact: $inventoryPath"
Write-Host "Runtime provenance artifact: $provenancePath"
Write-Host "Shared harness checkout preserved: $sharedHeadAfter"
