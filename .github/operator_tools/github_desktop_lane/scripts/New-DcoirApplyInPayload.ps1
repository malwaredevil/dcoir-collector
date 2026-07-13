[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadZip,
    [string]$RequestId,
    [string]$RepoRoot,
    [string]$LogPath,
    [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'
$ToolVersion = '2026-05-03.3'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$toolRoot = Split-Path -Parent $scriptRoot
$loggingModule = Join-Path $toolRoot 'modules\Dcoir.Logging\Dcoir.Logging.psm1'
if (-not (Test-Path -LiteralPath $loggingModule -PathType Leaf)) { throw "Dcoir.Logging module not found: $loggingModule" }
Import-Module $loggingModule -Force
Initialize-DcoirToolLog -ToolName 'dcoir_apply_in_payload_stager' -ToolVersion $ToolVersion -LogPath $LogPath | Out-Null

function Get-Sha256Hex {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-SafeRequestId {
    param([string]$Value)
    return (-not [string]::IsNullOrWhiteSpace($Value) -and $Value -match '^[A-Za-z0-9._-]+$')
}

function ConvertTo-SafeRequestId {
    param([string]$Value)
    $safe = ([string]$Value -replace '[^A-Za-z0-9._-]', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = 'request' }
    return $safe
}

function Write-Utf8NoBom {
    param([Parameter(Mandatory=$true)][string]$Path, [AllowNull()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, [string]$Text, $enc)
}

function Write-AsciiText {
    param([Parameter(Mandatory=$true)][string]$Path, [AllowNull()][string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    [System.IO.File]::WriteAllText($Path, [string]$Text, [System.Text.Encoding]::ASCII)
}

function Test-ZipHasApplyManifest {
    param([Parameter(Mandatory=$true)][string]$ZipPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $entries = @($zip.Entries | ForEach-Object { $_.FullName })
        if ($entries -notcontains 'apply_manifest.json') { throw 'Input ZIP must contain apply_manifest.json at archive root.' }
        return $entries
    }
    finally {
        if ($zip) { $zip.Dispose() }
    }
}

$success = $false
$result = $null

try {
    Set-DcoirLogPhase -Phase 'resolve-inputs'
    Write-DcoirLogLine -Message ('Raw PayloadZip argument: {0}' -f $PayloadZip)
    Write-DcoirLogLine -Message ('Raw RequestId argument: {0}' -f $RequestId)

    if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
        $RepoRoot = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT', 'Machine')
        Write-DcoirLogLine -Message ('DCOIR_REPO_ROOT present: {0}' -f (-not [string]::IsNullOrWhiteSpace($RepoRoot)))
    }
    if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = (Get-Location).Path }
    $RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
    Write-DcoirLogLine -Message ('Resolved repo root: {0}' -f $RepoRoot)
    if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) { throw "Repo root not found: $RepoRoot" }

    $payloadZipFull = [System.IO.Path]::GetFullPath($PayloadZip)
    Write-DcoirLogLine -Message ('Resolved payload ZIP: {0}' -f $payloadZipFull)
    if (-not (Test-Path -LiteralPath $payloadZipFull -PathType Leaf)) { throw "Payload ZIP not found: $payloadZipFull. Create or provide an apply-in ZIP containing apply_manifest.json, then rerun with -PayloadZip pointing to that ZIP." }

    if ([string]::IsNullOrWhiteSpace($RequestId)) { $RequestId = '{0}-{1}' -f (ConvertTo-SafeRequestId ([IO.Path]::GetFileNameWithoutExtension($payloadZipFull))), (Get-Date -Format 'yyyyMMdd-HHmmss') }
    if (-not (Test-SafeRequestId $RequestId)) { throw 'RequestId may contain only letters, numbers, dot, underscore, and dash.' }
    Write-DcoirLogLine -Message ('Resolved request id: {0}' -f $RequestId)

    Set-DcoirLogPhase -Phase 'validate-input-zip'
    $entries = Test-ZipHasApplyManifest -ZipPath $payloadZipFull
    Write-DcoirLogLine -Message ('Input ZIP entry count: {0}' -f $entries.Count)
    $sourceSha = Get-Sha256Hex -Path $payloadZipFull
    Write-DcoirLogLine -Message ('Input ZIP SHA256: {0}' -f $sourceSha)
    $bytes = [System.IO.File]::ReadAllBytes($payloadZipFull)
    Write-DcoirLogLine -Message ('Input ZIP bytes: {0}' -f $bytes.Length)
    $encoded = [Convert]::ToBase64String($bytes, [Base64FormattingOptions]::InsertLineBreaks)

    Set-DcoirLogPhase -Phase 'stage-payload'
    $stagingDir = Join-Path $RepoRoot (Join-Path '.github\chatgpt_staging\in' $RequestId)
    $payloadB64Path = Join-Path $stagingDir 'payload.zip.b64'
    $reportPath = Join-Path $stagingDir 'payload_staging_report.json'
    Write-DcoirLogLine -Message ('Staging directory: {0}' -f $stagingDir)
    if ((Test-Path -LiteralPath $payloadB64Path -PathType Leaf) -and -not $Overwrite) { throw "Payload already exists: $payloadB64Path. Use -Overwrite to replace it." }

    New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null
    Write-AsciiText -Path $payloadB64Path -Text ($encoded + [Environment]::NewLine)
    Write-DcoirLogLine -Message ('Wrote payload base64: {0}' -f $payloadB64Path)

    Set-DcoirLogPhase -Phase 'round-trip-validate'
    $readBack = Get-Content -LiteralPath $payloadB64Path -Raw
    if ($readBack -match 'ERROR TRUNCATED') { throw 'Staged payload contains ERROR TRUNCATED marker.' }
    $decoded = [Convert]::FromBase64String($readBack)
    $tempZip = Join-Path ([IO.Path]::GetTempPath()) ('dcoir_apply_in_' + [guid]::NewGuid().ToString('N') + '.zip')
    try {
        [System.IO.File]::WriteAllBytes($tempZip, $decoded)
        $roundTripSha = Get-Sha256Hex -Path $tempZip
        Write-DcoirLogLine -Message ('Round-trip ZIP SHA256: {0}' -f $roundTripSha)
        if ($roundTripSha -ne $sourceSha) { throw "Round-trip SHA256 mismatch. Source=$sourceSha RoundTrip=$roundTripSha" }
        Test-ZipHasApplyManifest -ZipPath $tempZip | Out-Null
        Write-DcoirLogLine -Message 'Round-trip validation passed.'
    }
    finally {
        if (Test-Path -LiteralPath $tempZip -PathType Leaf) { Remove-Item -LiteralPath $tempZip -Force }
    }

    Set-DcoirLogPhase -Phase 'write-report'
    $relativePayload = '.github/chatgpt_staging/in/{0}/payload.zip.b64' -f $RequestId
    $relativeReport = '.github/chatgpt_staging/in/{0}/payload_staging_report.json' -f $RequestId
    $report = [ordered]@{
        tool = 'New-DcoirApplyInPayload.ps1'
        tool_version = $ToolVersion
        logging_module_version = Get-DcoirLoggingVersion
        created_at = (Get-Date -Format o)
        request_id = $RequestId
        staged_payload_path = $relativePayload
        staging_report_path = $relativeReport
        log_path = Get-DcoirToolLogPath
        source_payload_zip = $payloadZipFull
        source_payload_sha256 = $sourceSha
        source_payload_bytes = $bytes.Length
        round_trip_validated = $true
        zip_entry_count = $entries.Count
        workflow_dispatch_payload_b64_path = $relativePayload
        next_action = 'Commit and push the staged payload.zip.b64 and report to trigger the apply-in workflow, or use workflow_dispatch with the payload path.'
    }
    Write-Utf8NoBom -Path $reportPath -Text ($report | ConvertTo-Json -Depth 10)
    Write-DcoirLogLine -Message ('Wrote staging report: {0}' -f $reportPath)

    $success = $true
    $result = [ordered]@{
        success = $true
        request_id = $RequestId
        staged_payload_path = $relativePayload
        staging_report_path = $relativeReport
        source_payload_sha256 = $sourceSha
        round_trip_validated = $true
        log_path = Get-DcoirToolLogPath
    }
    Write-DcoirLogLine -Message 'Completed successfully.'
}
catch {
    $result = Write-DcoirCaughtError -ErrorRecord $_ -NextAction 'Upload the log_path file to ChatGPT, or rerun with -PayloadZip pointing to a valid apply-in ZIP containing apply_manifest.json.'
    $result | ConvertTo-Json -Depth 8
    exit 1
}

$result | ConvertTo-Json -Depth 8
if (-not $success) { exit 1 }
