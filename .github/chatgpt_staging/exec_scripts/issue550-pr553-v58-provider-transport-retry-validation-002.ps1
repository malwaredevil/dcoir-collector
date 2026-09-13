$ErrorActionPreference = 'Stop'

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }

$source = Join-Path $repo '.github\chatgpt_staging\exec_scripts\issue550-pr553-v58-provider-transport-retry-validation-001.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing validated base harness: $source" }

$oldRequestId = 'issue550-pr553-v58-provider-transport-retry-validation-001'
$newRequestId = 'issue550-pr553-v58-provider-transport-retry-validation-002'
$oldMarker = 'ISSUE550_PR553_V58_PROVIDER_TRANSPORT_RETRY_VALIDATION_001_PASS'
$newMarker = 'ISSUE550_PR553_V58_PROVIDER_TRANSPORT_RETRY_VALIDATION_002_PASS'
$text = Get-Content -Raw -LiteralPath $source
if (-not $text.Contains($oldRequestId)) { throw 'Base harness request id marker not found' }
if (-not $text.Contains($oldMarker)) { throw 'Base harness terminal marker not found' }
$text = $text.Replace($oldRequestId, $newRequestId).Replace($oldMarker, $newMarker)
if ($text.Contains($oldRequestId) -or $text.Contains($oldMarker)) { throw 'Base harness retry identity replacement was incomplete' }

$patched = Join-Path $env:RUNNER_TEMP ($newRequestId + '.ps1')
Set-Content -LiteralPath $patched -Value $text -Encoding utf8
$env:PYTHONPYCACHEPREFIX = Join-Path $env:RUNNER_TEMP ($newRequestId + '-pycache')

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $patched
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
