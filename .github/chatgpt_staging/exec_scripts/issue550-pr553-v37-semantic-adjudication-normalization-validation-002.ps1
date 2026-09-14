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

$source = Join-Path $repo '.github\chatgpt_staging\exec_scripts\issue550-pr553-v37-semantic-adjudication-normalization-validation-001.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing v37 base wrapper: $source" }
$text = Get-Content -Raw -LiteralPath $source

$oldRequestLine = @'
$newRequestId = 'issue550-pr553-v37-semantic-adjudication-normalization-validation-001'
'@
$newRequestLine = @'
$newRequestId = 'issue550-pr553-v37-semantic-adjudication-normalization-validation-002'
'@
$text = Replace-RequiredText $text $oldRequestLine $newRequestLine 'retry request id'

$oldMarkerLine = @'
$newMarker = 'ISSUE550_PR553_V37_SEMANTIC_ADJUDICATION_NORMALIZATION_VALIDATION_001_PASS'
'@
$newMarkerLine = @'
$newMarker = 'ISSUE550_PR553_V37_SEMANTIC_ADJUDICATION_NORMALIZATION_VALIDATION_002_PASS'
'@
$text = Replace-RequiredText $text $oldMarkerLine $newMarkerLine 'retry terminal marker'

$patchedWrapper = Join-Path $env:RUNNER_TEMP 'issue550-pr553-v37-semantic-adjudication-normalization-validation-002-wrapper.ps1'
Set-Content -LiteralPath $patchedWrapper -Value $text -Encoding utf8
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $patchedWrapper
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
