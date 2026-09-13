$ErrorActionPreference = 'Stop'

function Replace-Required {
    param(
        [Parameter(Mandatory=$true)][string]$Text,
        [Parameter(Mandatory=$true)][string]$Old,
        [Parameter(Mandatory=$true)][string]$New,
        [Parameter(Mandatory=$true)][string]$Label
    )
    if (-not $Text.Contains($Old)) { throw "Required harness anchor missing: $Label" }
    return $Text.Replace($Old, $New)
}

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }

$source = Join-Path $repo '.github\chatgpt_staging\exec_scripts\issue550-pr553-v58-provider-transport-retry-validation-001.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing validated base harness: $source" }

$oldRequestId = 'issue550-pr553-v58-provider-transport-retry-validation-001'
$newRequestId = 'issue550-pr553-v55-semantic-adjudication-validation-001'
$oldMarker = 'ISSUE550_PR553_V58_PROVIDER_TRANSPORT_RETRY_VALIDATION_001_PASS'
$newMarker = 'ISSUE550_PR553_V55_SEMANTIC_ADJUDICATION_VALIDATION_001_PASS'
$text = Get-Content -Raw -LiteralPath $source

$text = Replace-Required $text '4fa7fbb9ec9d287e6a084c2d4ab81212e83bd787' 'fcf55880fb007289b3c377fc8412ae2d6fe4280d' 'exact head'
$text = Replace-Required $text '7dddb386b3ca829babc4d0fe59cb83ec0f872bd0' '1b2058610981623da75a2734fa9a685b38058bbf' 'exact tree'
$text = Replace-Required $text $oldRequestId $newRequestId 'request id'
$text = Replace-Required $text $oldMarker $newMarker 'terminal marker'
$text = Replace-Required $text 'issue550-pr553-v58-validation-' 'issue550-pr553-v55-validation-' 'isolated worktree prefix'
$text = Replace-Required $text '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v55_selftest.py' '.github/dcoir_review/scripts/dcoir_review_semantic_adjudication_recovery_selftest.py' 'stable v55 selftest path'

$oldRetired = "'dcoir_review_required_runtime_patch_v47','dcoir_review_required_runtime_patch_v58')"
$newRetired = "'dcoir_review_required_runtime_patch_v47','dcoir_review_required_runtime_patch_v55','dcoir_review_required_runtime_patch_v58')"
$text = Replace-Required $text $oldRetired $newRetired 'retired production module set'

$oldStable = "'dcoir_review.per_file_routing','dcoir_review.provider_transport_retry')"
$newStable = "'dcoir_review.per_file_routing','dcoir_review.provider_transport_retry','dcoir_review.semantic_adjudication_recovery')"
$text = Replace-Required $text $oldStable $newStable 'stable responsibility owner set'

$oldComposition = @'
        $v54Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v54')
        $transportIndex = [Array]::IndexOf($sequence, 'dcoir_review.provider_transport_retry')
        $v55Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v55')
        if ($v54Index -lt 0 -or $transportIndex -ne ($v54Index + 1) -or $v55Index -ne ($transportIndex + 1)) { throw "Provider transport retry composition mismatch: v54=$v54Index transport=$transportIndex v55=$v55Index" }
'@
$newComposition = @'
        $v54Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v54')
        $transportIndex = [Array]::IndexOf($sequence, 'dcoir_review.provider_transport_retry')
        $recoveryIndex = [Array]::IndexOf($sequence, 'dcoir_review.semantic_adjudication_recovery')
        $v56Index = [Array]::IndexOf($sequence, 'dcoir_review_required_runtime_patch_v56')
        if ($v54Index -lt 0 -or $transportIndex -ne ($v54Index + 1) -or $recoveryIndex -ne ($transportIndex + 1) -or $v56Index -ne ($recoveryIndex + 1)) { throw "Semantic adjudication recovery composition mismatch: v54=$v54Index transport=$transportIndex recovery=$recoveryIndex v56=$v56Index" }
'@
$text = Replace-Required $text $oldComposition $newComposition 'post-telemetry composition assertion'

$transportAnchor = @'
        $transportBytes = (Get-Item -LiteralPath $transportPath).Length
        if ($transportBytes -gt 15000) { throw "Stable provider transport owner exceeds connector-safe size: $transportBytes" }
'@
$recoveryChecks = @'

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
        $recoveryBytes = (Get-Item -LiteralPath $recoveryPath).Length
        if ($recoveryBytes -gt 15000) { throw "Stable semantic recovery owner exceeds connector-safe size: $recoveryBytes" }
'@
$text = Replace-Required $text $transportAnchor ($transportAnchor + $recoveryChecks) 'stable semantic recovery source assertions'

$entryAnchor = @'
        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v58["'']') { throw 'Entrypoint still composes historical v58 owner' }
'@
$entryChecks = @'
        if ($entrypointText -match '["'']dcoir_review_required_runtime_patch_v55["'']') { throw 'Entrypoint still composes historical v55 owner' }
        if ($entrypointText -notmatch '["'']dcoir_review\.semantic_adjudication_recovery["'']') { throw 'Entrypoint does not compose stable semantic adjudication recovery owner' }
'@
$text = Replace-Required $text $entryAnchor ($entryAnchor + $entryChecks) 'entrypoint v55 ownership assertions'

$v58RefAnchor = @'
        if ($v58Refs.Count -lt 1) { throw 'Expected negative architecture guard reference for retired v58 was not found' }
'@
$v55RefChecks = @'

        $v55Refs = @(Get-ChildItem -Recurse -File '.github/dcoir_review' | Select-String -Pattern 'dcoir_review_required_runtime_patch_v55' -SimpleMatch)
        $unexpectedV55Refs = @($v55Refs | Where-Object { $_.Path -notlike '*dcoir_review_runtime_module_loader_selftest.py' })
        if ($unexpectedV55Refs.Count -ne 0) { throw "Unexpected historical v55 module reference remains: $($unexpectedV55Refs.Path -join ', ')" }
        if ($v55Refs.Count -lt 1) { throw 'Expected negative architecture guard reference for retired v55 was not found' }
'@
$text = Replace-Required $text $v58RefAnchor ($v58RefAnchor + $v55RefChecks) 'active-source v55 provenance scan'

$provAnchor = @'
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v58') { throw 'Historical v58 appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.provider_transport_retry') { throw 'Stable provider transport owner missing from runtime provenance' }
'@
$provChecks = @'
        if ($provSequence -contains 'dcoir_review_required_runtime_patch_v55') { throw 'Historical v55 appears in runtime provenance' }
        if ($provSequence -notcontains 'dcoir_review.semantic_adjudication_recovery') { throw 'Stable semantic adjudication recovery owner missing from runtime provenance' }
'@
$text = Replace-Required $text $provAnchor ($provAnchor + $provChecks) 'runtime provenance v55 assertions'

$text = Replace-Required $text "'retired=v15,v19,v21,v22,v23,v24,v25,v26,v27,v28,v29,v47,v58'" "'retired=v15,v19,v21,v22,v23,v24,v25,v26,v27,v28,v29,v47,v55,v58'" 'summary retired set'
$text = Replace-Required $text "'composition=v54->provider_transport_retry->v55'" "'composition=v54->provider_transport_retry->semantic_adjudication_recovery->v56'" 'summary composition'
$text = Replace-Required $text "'provider_transport_retry_owner=dcoir_review.provider_transport_retry'," "'provider_transport_retry_owner=dcoir_review.provider_transport_retry',`n            'semantic_adjudication_recovery_owner=dcoir_review.semantic_adjudication_recovery'," 'summary stable semantic owner'
$text = Replace-Required $text '"provider_transport_retry_bytes=$transportBytes",' '"provider_transport_retry_bytes=$transportBytes",`n            "semantic_adjudication_recovery_bytes=$recoveryBytes",' 'summary semantic owner size'

$patched = Join-Path $env:RUNNER_TEMP ($newRequestId + '.ps1')
Set-Content -LiteralPath $patched -Value $text -Encoding utf8
$env:PYTHONPYCACHEPREFIX = Join-Path $env:RUNNER_TEMP ($newRequestId + '-pycache')

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $patched
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
