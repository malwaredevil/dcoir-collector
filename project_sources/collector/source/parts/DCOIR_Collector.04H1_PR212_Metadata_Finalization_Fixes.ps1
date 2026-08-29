<#
.SYNOPSIS
DCOIR collector metadata finalization helpers for issue #212.

.DESCRIPTION
Provides collect-mode guidance builders that can reference the final metadata report path
before the report content is written, without snapshotting an empty placeholder file.

.FILE NAME
DCOIR_Collector.04H1_PR212_Metadata_Finalization_Fixes.ps1

.INPUTS
Collector state and baseline hashtables.

.OUTPUTS
Upload guidance artifacts and analyst overview artifacts that reference late-bound
metadata deterministically.
#>

<#
.SYNOPSIS
Removes partial upload-safe chunk companions after a declined chunk write.

.DESCRIPTION
When a per-chunk confirmation prompt is declined after earlier chunks in the same set
were written, removes the current-run companion files for the known oversized artifact
keys so collect can report the chunk companion set as skipped instead of leaving a partial
upload surface.

.FUNCTION NAME
Remove-SkippedUploadSafeChunkCompanionFiles

.INPUTS
Collector state hashtable.

.OUTPUTS
No direct output. Deletes matching current-run companion files when present.
#>
function Remove-SkippedUploadSafeChunkCompanionFiles {
  param([hashtable]$State)

  if (-not $State -or [string]::IsNullOrWhiteSpace([string]$State.ArtifactsDir) -or -not (Test-Path -LiteralPath $State.ArtifactsDir)) { return }
  foreach ($key in @('security_filtered','powershell_operational_filtered','taskscheduler_operational_filtered')) {
    $safeKey = ($key -replace '[\/:*?"<>| ]','_')
    $pattern = "90_UPLOAD_SAFE_CHUNKS_{0}_chunk_*.txt" -f $safeKey
    foreach ($chunkPath in @(Get-ChildItem -LiteralPath $State.ArtifactsDir -Filter $pattern -File -ErrorAction SilentlyContinue)) {
      Remove-Item -LiteralPath $chunkPath.FullName -Force -ErrorAction SilentlyContinue
    }
  }
}

<#
.SYNOPSIS
Detects upload-safe chunk companion writes that a WhatIf collect would skip.

.DESCRIPTION
Finds oversized upload-safe companion source artifacts before the shared chunk helper is
called. Under a top-level WhatIf run those chunk writes will be declined and return null,
so the active collect wrapper can mark the companion surface skipped without dereferencing
a null chunk result in the shared helper.

.FUNCTION NAME
Test-UploadSafeChunkCompanionWouldBeSkippedByWhatIf

.INPUTS
Collector state, artifact map, and upload budget hashtables.

.OUTPUTS
Boolean.
#>
function Test-UploadSafeChunkCompanionWouldBeSkippedByWhatIf {
  param([hashtable]$State,[hashtable]$ArtifactMap,[hashtable]$Budget)

  if (-not $WhatIfPreference) { return $false }
  if (-not $State -or -not $ArtifactMap -or -not $Budget) { return $false }

  foreach ($key in @('security_filtered','powershell_operational_filtered','taskscheduler_operational_filtered')) {
    if (-not $ArtifactMap.ContainsKey($key)) { continue }
    $sourcePath = [string]$ArtifactMap[$key]
    if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath)) { continue }
    $sourceSizeKB = Get-FileSizeKB -Path $sourcePath
    if ($sourceSizeKB -gt [int]$Budget.SafePerFileKB) { return $true }
  }

  return $false
}

<#
.SYNOPSIS
Creates production upload-safe chunk companions with skipped-write downgrade handling.

.DESCRIPTION
Calls the shared chunk companion builder and catches the specific confirmation-decline
error raised by a per-chunk companion write. It also pre-detects the pure WhatIf oversized
companion path, where the shared chunk helper returns null instead of throwing. The skipped
set is omitted from manifest rows, partial companion files are cleaned up, and the collect
state records that an upload-safe chunk companion surface was skipped.

.FUNCTION NAME
New-ProductionUploadSafeChunkCompanionsWithSkipStatus

.INPUTS
Collector state, artifact map, and upload budget hashtables.

.OUTPUTS
Array of ordered manifest rows, or an empty array when the chunk companion set was
skipped by confirmation decline or WhatIf.
#>
function New-ProductionUploadSafeChunkCompanionsWithSkipStatus {
  [CmdletBinding()]
  param([hashtable]$State,[hashtable]$ArtifactMap,[hashtable]$Budget)

  if ($State) { $State.UploadSafeChunkCompanionSkipped = $false }
  if (Test-UploadSafeChunkCompanionWouldBeSkippedByWhatIf -State $State -ArtifactMap $ArtifactMap -Budget $Budget) {
    if ($State) { $State.UploadSafeChunkCompanionSkipped = $true }
    Remove-SkippedUploadSafeChunkCompanionFiles -State $State
    return @()
  }

  try {
    return @(New-ProductionUploadSafeChunkCompanions -State $State -ArtifactMap $ArtifactMap -Budget $Budget)
  } catch {
    $message = [string]$_.Exception.Message
    if ($message -match '^Upload-safe chunk write was skipped before completing chunk set:') {
      if ($State) { $State.UploadSafeChunkCompanionSkipped = $true }
      Remove-SkippedUploadSafeChunkCompanionFiles -State $State
      return @()
    }
    throw
  }
}
