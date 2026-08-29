<#
.SYNOPSIS
DCOIR collector baseline collection and reporting helpers.

.DESCRIPTION
Builds the baseline collection surface, including execution-context and audit-policy
artifacts, host, identity, process, network, persistence, security, and event-log
artifacts, plus the analyst-facing baseline report, metadata report, upload summary, and
attachment-budget manifest.

.FILE NAME
DCOIR_Collector.02A_Baseline_Collection_And_Reports.ps1

.INPUTS
Collector state and tool-map hashtables, current tier and hour settings, artifact paths,
and collector-global notes, errors, recommendations, and targeted runtime settings.

.OUTPUTS
Baseline and metadata report text, upload-summary artifacts, attachment-budget manifest
artifacts, and helper return values used by the collector runtime.
#>

<#
.SYNOPSIS
Returns the Gemini upload budget thresholds used by the collector.

.DESCRIPTION
Defines the hard and safe per-file and total-size thresholds used to decide whether the
recommended Gemini upload set fits comfortably within the environment budget.

.FUNCTION NAME
Get-CollectorUploadBudget

.INPUTS
No direct parameters.

.OUTPUTS
Hashtable containing hard and safe per-file and total-size budget values in KB.
#>
function Get-CollectorUploadBudget {
  return @{
    HardPerFileKB = 1000
    HardTotalKB = 2000
    SafePerFileKB = 900
    SafeTotalKB = 1800
  }
}

<#
.SYNOPSIS
Returns the size of one file in KB.

.DESCRIPTION
Checks whether the file exists and returns a rounded-up KB size for the file. Returns
zero when the path does not exist.

.FUNCTION NAME
Get-FileSizeKB

.INPUTS
Path string for the file to inspect.

.OUTPUTS
Integer file size in KB.
#>
function Get-FileSizeKB {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return 0 }
  return [int][Math]::Ceiling(((Get-Item -LiteralPath $Path -ErrorAction Stop).Length) / 1KB)
}

<#
.SYNOPSIS
Returns the SHA256 hash for one file when available.

.DESCRIPTION
Computes a SHA256 digest for provenance and reconstruction metadata. Returns an empty
string when the path is blank, missing, or cannot be hashed.

.FUNCTION NAME
Get-FileSha256

.INPUTS
Path string for the file to inspect.

.OUTPUTS
SHA256 hash string or an empty string.
#>
function Get-FileSha256 {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) { return "" }
  try {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash
  } catch {
    Add-CollectorError ("Failed to hash file [{0}]: {1}" -f $Path, $_.Exception.Message)
    return ""
  }
}

<#
.SYNOPSIS
Chooses a UTF-8 safe byte length for one upload-safe chunk.

.DESCRIPTION
Returns a chunk length that stays within the target byte budget without ending in the
middle of a UTF-8 multibyte character whenever the source bytes are valid UTF-8.

.FUNCTION NAME
Get-Utf8SafeChunkLength

.INPUTS
Source byte array, current offset, and target chunk byte count.

.OUTPUTS
Integer byte length for the next chunk.
#>
function Get-Utf8SafeChunkLength {
  param([byte[]]$Bytes,[int]$Offset,[int]$TargetBytes)

  $remaining = $Bytes.Length - $Offset
  if ($remaining -le 0) { return 0 }
  $length = [Math]::Min($TargetBytes, $remaining)
  if (($Offset + $length) -ge $Bytes.Length) { return $length }

  $end = $Offset + $length
  $lead = $end - 1
  while (($lead -gt $Offset) -and (($Bytes[$lead] -band 0xC0) -eq 0x80)) { $lead -= 1 }
  $leadByte = $Bytes[$lead]

  if (($leadByte -band 0x80) -eq 0) { return $length }
  if (($leadByte -band 0xE0) -eq 0xC0) { $charLength = 2 }
  elseif (($leadByte -band 0xF0) -eq 0xE0) { $charLength = 3 }
  elseif (($leadByte -band 0xF8) -eq 0xF0) { $charLength = 4 }
  else { return $length }

  if (($lead + $charLength) -le $end) { return $length }
  $safeLength = $lead - $Offset
  if ($safeLength -gt 0) { return $safeLength }
  return [Math]::Min($charLength, $remaining)
}

<#
.SYNOPSIS
Splits a real text artifact into upload-safe chunk companions.

.DESCRIPTION
Creates ordered byte-preserving chunks that can be concatenated to reconstruct the original
artifact exactly. The source artifact is preserved; this helper writes derivative chunk
companions plus metadata used by the aggregate upload-safe chunk manifest.

.FUNCTION NAME
Split-TextArtifactIntoUploadSafeChunks

.INPUTS
Source artifact path, artifact directory, source key, target chunk size, and origin label.

.OUTPUTS
Ordered hashtable describing chunk paths, sizes, hashes, source provenance, and reconstruction.
#>
function Split-TextArtifactIntoUploadSafeChunks {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$SourcePath,
    [string]$ArtifactsDir,
    [string]$SourceKey,
    [int]$TargetChunkKB,
    [string]$Origin = 'collector_production_upload_safe'
  )

  $chunkPaths = New-Object System.Collections.ArrayList
  $chunkSizes = New-Object System.Collections.ArrayList
  $chunkSha256 = New-Object System.Collections.ArrayList
  $targetBytes = [Math]::Max(1, $TargetChunkKB) * 1024
  $sourceBytes = [System.IO.File]::ReadAllBytes($SourcePath)
  $safeKey = ($SourceKey -replace '[\/:*?"<>| ]','_')
  $chunkIndex = 1
  $offset = 0

  if ($sourceBytes.Length -eq 0) {
    $chunkPath = Join-Path $ArtifactsDir ("90_UPLOAD_SAFE_CHUNKS_{0}_chunk_{1:000}.txt" -f $safeKey, $chunkIndex)
    if ($PSCmdlet.ShouldProcess($chunkPath, 'Write upload-safe empty chunk companion')) {
      [System.IO.File]::WriteAllBytes($chunkPath, [byte[]]@())
      [void]$chunkPaths.Add($chunkPath)
      [void]$chunkSizes.Add((Get-FileSizeKB -Path $chunkPath))
      [void]$chunkSha256.Add((Get-FileSha256 -Path $chunkPath))
    } elseif ($WhatIfPreference) {
      return $null
    } else {
      throw ("Upload-safe chunk write was skipped before completing chunk set: {0}" -f $chunkPath)
    }
  }

  while ($offset -lt $sourceBytes.Length) {
    $length = Get-Utf8SafeChunkLength -Bytes $sourceBytes -Offset $offset -TargetBytes $targetBytes
    if ($length -le 0) { $length = [Math]::Min($targetBytes, ($sourceBytes.Length - $offset)) }
    $chunkBytes = New-Object byte[] $length
    [Array]::Copy($sourceBytes, $offset, $chunkBytes, 0, $length)
    $chunkPath = Join-Path $ArtifactsDir ("90_UPLOAD_SAFE_CHUNKS_{0}_chunk_{1:000}.txt" -f $safeKey, $chunkIndex)
    if ($PSCmdlet.ShouldProcess($chunkPath, 'Write upload-safe chunk companion')) {
      [System.IO.File]::WriteAllBytes($chunkPath, $chunkBytes)
      [void]$chunkPaths.Add($chunkPath)
      [void]$chunkSizes.Add((Get-FileSizeKB -Path $chunkPath))
      [void]$chunkSha256.Add((Get-FileSha256 -Path $chunkPath))
    } elseif ($WhatIfPreference) {
      return $null
    } else {
      throw ("Upload-safe chunk write was skipped before completing chunk set: {0}" -f $chunkPath)
    }
    $offset += $length
    $chunkIndex += 1
  }

  return [ordered]@{
    origin = $Origin
    source_artifact_key = $SourceKey
    source_path = $SourcePath
    source_size_kb = Get-FileSizeKB -Path $SourcePath
    source_size_bytes = $sourceBytes.Length
    source_sha256 = Get-FileSha256 -Path $SourcePath
    target_chunk_kb = $TargetChunkKB
    chunk_count = @($chunkPaths).Count
    chunk_paths = @($chunkPaths)
    chunk_file_sizes_kb = @($chunkSizes)
    chunk_sha256 = @($chunkSha256)
    reconstruction_order = 'Concatenate chunk_paths in listed order as bytes to reconstruct the original source artifact exactly.'
  }
}
<#
.SYNOPSIS
Creates upload-safe chunk companions for selected oversized real artifacts.

.DESCRIPTION
Detects selected human-readable artifact keys that exceed the configured safe per-file
budget, writes ordered chunk companions, and returns manifest rows for the normal collect
handoff surfaces.

.FUNCTION NAME
New-ProductionUploadSafeChunkCompanions

.INPUTS
Collector state, artifact map, and upload budget.

.OUTPUTS
Array of ordered manifest rows.
#>
function New-ProductionUploadSafeChunkCompanions {
  [CmdletBinding()]
  param([hashtable]$State,[hashtable]$ArtifactMap,[hashtable]$Budget)

  $rows = New-Object System.Collections.ArrayList
  foreach ($key in @('security_filtered','powershell_operational_filtered','taskscheduler_operational_filtered')) {
    if (-not $ArtifactMap.ContainsKey($key)) { continue }
    $sourcePath = [string]$ArtifactMap[$key]
    if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath)) { continue }
    $sourceSizeKB = Get-FileSizeKB -Path $sourcePath
    if ($sourceSizeKB -le [int]$Budget.SafePerFileKB) { continue }

    $chunkResult = Split-TextArtifactIntoUploadSafeChunks -SourcePath $sourcePath -ArtifactsDir $State.ArtifactsDir -SourceKey $key -TargetChunkKB ([Math]::Min(700, [int]$Budget.SafePerFileKB))
    if ([int]$chunkResult.chunk_count -le 0) { continue }
    [void]$rows.Add($chunkResult)
    foreach ($chunkPath in @($chunkResult.chunk_paths)) {
      [void]$ArtifactMap.Add(("{0}_upload_safe_chunk_{1:000}" -f $key, (@($ArtifactMap.Keys | Where-Object { $_ -like ("{0}_upload_safe_chunk_*" -f $key) }).Count + 1)), $chunkPath)
    }
  }

  return @($rows)
}
