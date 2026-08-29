<#
.SYNOPSIS
DCOIR collector feature-wave synthetic chunk-validation helpers.

.DESCRIPTION
Creates deterministic oversized validation artifacts, splits them into upload-safe
chunks, records reconstruction metadata, and applies feature-wave collection
enhancements to the current baseline result.

.FILE NAME
DCOIR_Collector.04B2_Feature_Wave_Targeted_Collection.ps1

.INPUTS
Collector state and baseline hashtables plus validation-specific synthetic chunking
settings.

.OUTPUTS
Synthetic source artifacts, chunk files, path lists, manifests, collector notes, and
updates to the baseline artifact map and report builder.
#>

<#
.SYNOPSIS
Builds the synthetic oversized artifact text.

.DESCRIPTION
Creates deterministic text content large enough to exceed the requested size for chunking
validation.

.FUNCTION NAME
New-SyntheticOversizeArtifactText

.INPUTS
RequestedKB integer.

.OUTPUTS
String synthetic oversized artifact content.
#>
function New-SyntheticOversizeArtifactText {
  param([int]$RequestedKB)

  $line = 'DCOIR_SYNTHETIC_OVERSIZE_CHUNK_VALIDATION_PAYLOAD|ABCDEFGHIJKLMNOPQRSTUVWXYZ|0123456789|line='
  $targetBytes = $RequestedKB * 1024
  $currentBytes = 0
  $index = 1
  $sb = New-Object System.Text.StringBuilder
  while ($currentBytes -lt $targetBytes) {
    $lineText = ('{0}{1}' -f $line, $index) + [Environment]::NewLine
    [void]$sb.Append($lineText)
    $currentBytes += [System.Text.Encoding]::UTF8.GetByteCount($lineText)
    $index += 1
  }
  return $sb.ToString()
}

<#
.SYNOPSIS
Writes exact UTF-8 text without BOM to an artifact path.

.DESCRIPTION
Builds a deterministic artifact filename and writes the supplied text exactly using
UTF-8 without BOM.

.FUNCTION NAME
Write-ArtifactTextExact

.INPUTS
ArtifactsDir, Section, Name, and Text strings.

.OUTPUTS
String artifact path.
#>
function Write-ArtifactTextExact {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$ArtifactsDir,
    [string]$Section,
    [string]$Name,
    [string]$Text
  )

  $prefix = Get-BaselineArtifactPrefix -Name $Name
  $safeSection = ($Section -replace '[\\/:*?"<>| ]','_')
  $safeName = ($Name -replace '[\\/:*?"<>| ]','_')
  $path = Join-Path $ArtifactsDir ("{0}_{1}_{2}" -f $prefix, $safeSection, $safeName)
  if ($PSCmdlet.ShouldProcess($path, 'Write exact UTF-8 artifact')) {
    Ensure-Directory -Path $ArtifactsDir
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $Text, $utf8NoBom)
    return $path
  }
  return $null
}

<#
.SYNOPSIS
Splits a validation text artifact into smaller chunks.

.DESCRIPTION
Breaks the supplied source artifact into multiple ordered chunk files sized for upload
budget validation and reconstruction testing.

.FUNCTION NAME
Split-ValidationTextArtifactIntoChunks

.INPUTS
SourcePath, ArtifactsDir, RequestedKB, and TargetChunkKB.

.OUTPUTS
Hashtable describing chunk paths, sizes, and reconstruction metadata.
#>
function Split-ValidationTextArtifactIntoChunks {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$SourcePath,
    [string]$ArtifactsDir,
    [int]$RequestedKB,
    [int]$TargetChunkKB
  )

  $chunkPaths = New-Object System.Collections.ArrayList
  $targetBytes = $TargetChunkKB * 1024
  $lines = Get-Content -LiteralPath $SourcePath -ErrorAction Stop
  $chunkIndex = 1
  $currentBytes = 0
  $sb = New-Object System.Text.StringBuilder

  foreach ($line in $lines) {
    $lineText = $line + [Environment]::NewLine
    $lineBytes = [System.Text.Encoding]::UTF8.GetByteCount($lineText)
    if (($currentBytes + $lineBytes) -gt $targetBytes -and $currentBytes -gt 0) {
      $chunkPath = Write-ArtifactTextExact -ArtifactsDir $ArtifactsDir -Section 'VALIDATION_CHUNKING' -Name ('synthetic_oversize_{0}KB_chunk_{1:000}.txt' -f $RequestedKB, $chunkIndex) -Text $sb.ToString()
      if (-not [string]::IsNullOrWhiteSpace($chunkPath)) {
        [void]$chunkPaths.Add($chunkPath)
      }
      $chunkIndex += 1
      $sb = New-Object System.Text.StringBuilder
      $currentBytes = 0
    }
    [void]$sb.Append($lineText)
    $currentBytes += $lineBytes
  }

  if ($currentBytes -gt 0) {
    $chunkPath = Write-ArtifactTextExact -ArtifactsDir $ArtifactsDir -Section 'VALIDATION_CHUNKING' -Name ('synthetic_oversize_{0}KB_chunk_{1:000}.txt' -f $RequestedKB, $chunkIndex) -Text $sb.ToString()
    if (-not [string]::IsNullOrWhiteSpace($chunkPath)) {
      [void]$chunkPaths.Add($chunkPath)
    }
  }

  $chunkSizes = @()
  foreach ($chunkPath in @($chunkPaths)) {
    if (Test-Path -LiteralPath $chunkPath) {
      $chunkSizes += (Get-FileSizeKB -Path $chunkPath)
    }
  }

  return @{
    ChunkPaths = @($chunkPaths)
    ChunkSizesKB = $chunkSizes
    ChunkCount = @($chunkPaths).Count
    TargetChunkKB = $TargetChunkKB
    ReconstructionOrder = 'Concatenate the chunk_paths entries in listed order to reconstruct the original synthetic oversize artifact.'
  }
}

<#
.SYNOPSIS
Builds the synthetic chunk-validation artifacts.

.DESCRIPTION
Creates the synthetic oversized source, chunk files, path list, and manifest, then
registers them into collector state and baseline artifacts.

.FUNCTION NAME
New-SyntheticOversizeChunkValidationArtifacts

.INPUTS
State hashtable, Baseline hashtable, and RequestedKB integer.

.OUTPUTS
No direct output. Updates state and baseline structures.
#>
function New-SyntheticOversizeChunkValidationArtifacts {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([hashtable]$State,[hashtable]$Baseline,[int]$RequestedKB)

  $sourceText = New-SyntheticOversizeArtifactText -RequestedKB $RequestedKB
  $sourcePath = Write-ArtifactTextExact -ArtifactsDir $State.ArtifactsDir -Section 'VALIDATION_CHUNKING' -Name ('synthetic_oversize_{0}KB_source.txt' -f $RequestedKB) -Text $sourceText
  if ([string]::IsNullOrWhiteSpace($sourcePath)) { return }
  $chunkResult = Split-ValidationTextArtifactIntoChunks -SourcePath $sourcePath -ArtifactsDir $State.ArtifactsDir -RequestedKB $RequestedKB -TargetChunkKB 700
  $pathListPath = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'VALIDATION_CHUNKING' -Name ('synthetic_oversize_{0}KB_chunk_paths.json.txt' -f $RequestedKB) -Text (Convert-ToSafeJsonText -InputObject $chunkResult.ChunkPaths)

  $manifestObj = [ordered]@{
    fixture_origin = 'collector_synthetic_validation'
    source_path = $sourcePath
    source_size_kb = Get-FileSizeKB -Path $sourcePath
    target_chunk_kb = $chunkResult.TargetChunkKB
    chunk_count = $chunkResult.ChunkCount
    chunk_paths = $chunkResult.ChunkPaths
    chunk_file_sizes_kb = $chunkResult.ChunkSizesKB
    reconstruction_order = $chunkResult.ReconstructionOrder
  }
  $manifestPath = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'VALIDATION_CHUNKING' -Name ('synthetic_oversize_{0}KB_chunk_manifest.json.txt' -f $RequestedKB) -Text (Convert-ToSafeJsonText -InputObject $manifestObj)

  $State.SyntheticOversizeSourcePath = $sourcePath
  $State.ChunkManifestPath = $manifestPath
  $Baseline.ArtifactMap['synthetic_oversize_source'] = $sourcePath
  $Baseline.ArtifactMap['synthetic_oversize_chunk_manifest'] = $manifestPath
  $Baseline.ArtifactMap['synthetic_oversize_chunk_paths_json'] = $pathListPath
  [void]$Baseline.ArtifactPaths.Add($sourcePath)
  [void]$Baseline.ArtifactPaths.Add($pathListPath)
  [void]$Baseline.ArtifactPaths.Add($manifestPath)
  foreach ($chunkPath in $chunkResult.ChunkPaths) {
    [void]$Baseline.ArtifactPaths.Add($chunkPath)
  }

  $summaryText = @(
    'VALIDATION_SYNTHETIC_CHUNKING',
    ('REQUESTED_SYNTHETIC_SOURCE_KB={0}' -f $RequestedKB),
    ('SOURCE_PATH={0}' -f $sourcePath),
    ('SOURCE_SIZE_KB={0}' -f (Get-FileSizeKB -Path $sourcePath)),
    ('CHUNK_MANIFEST_PATH={0}' -f $manifestPath),
    ('CHUNK_COUNT={0}' -f $chunkResult.ChunkCount),
    ('TARGET_CHUNK_KB={0}' -f $chunkResult.TargetChunkKB)
  ) -join [Environment]::NewLine
  Add-Section -Builder $Baseline.ReportBuilder -Name 'VALIDATION_SYNTHETIC_CHUNKING' -Text $summaryText
  Add-CollectorNote ('Synthetic oversized validation artifact and chunk set were emitted for collector chunking regression at {0} KB.' -f $RequestedKB)
}

<#
.SYNOPSIS
Applies feature-wave collect enhancements to one baseline run.

.DESCRIPTION
Adds targeted collection artifacts, parallelism assessment, optional targeted planning,
and optional synthetic chunk-validation artifacts into the current baseline result.

.FUNCTION NAME
Apply-FeatureWaveCollectEnhancements

.INPUTS
State hashtable and Baseline hashtable.

.OUTPUTS
No direct output. Updates state, baseline, and collector notes/recommendations.
#>
function Apply-FeatureWaveCollectEnhancements {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([hashtable]$State,[hashtable]$Baseline)

  $scope = Get-TargetedCollectionScopeObject -State $State
  $scopeText = Get-TargetedCollectionScopeText -Scope $scope
  $scopePath = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "TARGETED_COLLECTION" -Name "collection_scope.txt" -Text $scopeText
  $State.CollectionScopePath = $scopePath
  $Baseline.ArtifactMap['collection_scope'] = $scopePath
  [void]$Baseline.ArtifactPaths.Add($scopePath)
  Add-Section -Builder $Baseline.ReportBuilder -Name "TARGETED_COLLECTION_SCOPE" -Text $scopeText

  $parallelText = Get-CollectorParallelismAssessmentText
  $parallelPath = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "TARGETED_COLLECTION" -Name "parallelism_assessment.txt" -Text $parallelText
  $State.ParallelismAssessmentPath = $parallelPath
  $Baseline.ArtifactMap['parallelism_assessment'] = $parallelPath
  [void]$Baseline.ArtifactPaths.Add($parallelPath)
  Add-Section -Builder $Baseline.ReportBuilder -Name "COLLECTOR_PARALLELISM_ASSESSMENT" -Text $parallelText

  if ($Targeted -or $scope.has_focus_context -or $scope.has_explicit_time_window) {
    $planText = Get-TargetedCollectionPlanText -Scope $scope
    $planPath = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "TARGETED_COLLECTION" -Name "targeted_collection_plan.txt" -Text $planText
    $State.TargetedCollectionPlanPath = $planPath
    $Baseline.ArtifactMap['targeted_collection_plan'] = $planPath
    [void]$Baseline.ArtifactPaths.Add($planPath)
    Add-Section -Builder $Baseline.ReportBuilder -Name "TARGETED_COLLECTION_PLAN" -Text $planText

    Add-Recommendation "A targeted collection plan was generated for this run."
    Add-Recommendation "For Gemini uploads, include COLLECTION_SCOPE_PATH and TARGETED_COLLECTION_PLAN_PATH before broader artifact expansion when the case is narrow or user-reported."
  }

  $syntheticKB = Get-ValidationSyntheticOversizeArtifactKB
  if ($syntheticKB -gt 0) {
    New-SyntheticOversizeChunkValidationArtifacts -State $State -Baseline $Baseline -RequestedKB $syntheticKB
  }

  if ($Targeted) {
    Add-CollectorNote ("Targeted collection mode was enabled with profile [{0}]." -f $TargetProfile)
  }
}
