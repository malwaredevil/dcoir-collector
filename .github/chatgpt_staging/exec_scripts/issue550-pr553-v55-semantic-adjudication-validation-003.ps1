$ErrorActionPreference = 'Stop'

function Replace-RequiredText {
    param(
        [Parameter(Mandatory=$true)][string]$Text,
        [Parameter(Mandatory=$true)][string]$Old,
        [Parameter(Mandatory=$true)][string]$New,
        [Parameter(Mandatory=$true)][string]$Label
    )
    if (-not $Text.Contains($Old)) { throw "Required retry-wrapper anchor missing: $Label" }
    return $Text.Replace($Old, $New)
}

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }

$source = Join-Path $repo '.github\chatgpt_staging\exec_scripts\issue550-pr553-v55-semantic-adjudication-validation-001.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing v55 base wrapper: $source" }
$text = Get-Content -Raw -LiteralPath $source

$oldRequestLine = @'
$newRequestId = 'issue550-pr553-v55-semantic-adjudication-validation-001'
'@
$newRequestLine = @'
$newRequestId = 'issue550-pr553-v55-semantic-adjudication-validation-003'
'@
$text = Replace-RequiredText $text $oldRequestLine $newRequestLine 'retry request id'

$oldMarkerLine = @'
$newMarker = 'ISSUE550_PR553_V55_SEMANTIC_ADJUDICATION_VALIDATION_001_PASS'
'@
$newMarkerLine = @'
$newMarker = 'ISSUE550_PR553_V55_SEMANTIC_ADJUDICATION_VALIDATION_003_PASS'
'@
$text = Replace-RequiredText $text $oldMarkerLine $newMarkerLine 'retry terminal marker'

$oldOwnerLine = @'
$text = Replace-Required $text "'provider_transport_retry_owner=dcoir_review.provider_transport_retry'," "'provider_transport_retry_owner=dcoir_review.provider_transport_retry',`n            'semantic_adjudication_recovery_owner=dcoir_review.semantic_adjudication_recovery'," 'summary stable semantic owner'
'@
$newOwnerLines = @'
$summaryOwnerNew = "'provider_transport_retry_owner=dcoir_review.provider_transport_retry'," + [Environment]::NewLine + "            'semantic_adjudication_recovery_owner=dcoir_review.semantic_adjudication_recovery',"
$text = Replace-Required $text "'provider_transport_retry_owner=dcoir_review.provider_transport_retry'," $summaryOwnerNew 'summary stable semantic owner'
'@
$text = Replace-RequiredText $text $oldOwnerLine $newOwnerLines 'summary owner newline construction'

$oldBytesLine = @'
$text = Replace-Required $text '"provider_transport_retry_bytes=$transportBytes",' '"provider_transport_retry_bytes=$transportBytes",`n            "semantic_adjudication_recovery_bytes=$recoveryBytes",' 'summary semantic owner size'
'@
$newBytesLines = @'
$summaryBytesNew = '"provider_transport_retry_bytes=$transportBytes",' + [Environment]::NewLine + '            "semantic_adjudication_recovery_bytes=$recoveryBytes",'
$text = Replace-Required $text '"provider_transport_retry_bytes=$transportBytes",' $summaryBytesNew 'summary semantic owner size'
'@
$text = Replace-RequiredText $text $oldBytesLine $newBytesLines 'summary bytes newline construction'

$patchedWrapper = Join-Path $env:RUNNER_TEMP 'issue550-pr553-v55-semantic-adjudication-validation-003-wrapper.ps1'
Set-Content -LiteralPath $patchedWrapper -Value $text -Encoding utf8
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $patchedWrapper
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
