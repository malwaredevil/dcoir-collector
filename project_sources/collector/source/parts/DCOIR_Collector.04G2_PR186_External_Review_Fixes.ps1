<#
.SYNOPSIS
DCOIR collector PR #186 manifest and bundle synchronization helpers.

.DESCRIPTION
Applies narrowly scoped manifest and ZIP bundle refinements for external review findings
after the initial PR #186 review fixes and before the main collector entrypoint runs.

.FILE NAME
DCOIR_Collector.04G2_PR186_External_Review_Fixes.ps1

.INPUTS
Collector state, manifest inputs, artifact directories, and bundle paths.

.OUTPUTS
Maintained manifest and bundle helper functions used by the compiled collector runtime.
#>

<#
.SYNOPSIS
Returns Tier 2 deep-check root artifact paths that should be present in collect manifests.

.DESCRIPTION
Finds the prefixed root artifact files emitted for Tier 2 deep checks. These paths are
added to manifest_collect.json so the manifest inventories the same Tier 2 evidence that
is already included in the collect bundle.

.FUNCTION NAME
Get-Tier2DeepCheckManifestArtifactPaths

.INPUTS
Collector state hashtable.

.OUTPUTS
String array of existing Tier 2 deep-check artifact paths.
#>
function Get-Tier2DeepCheckManifestArtifactPaths {
  param([hashtable]$State)

  if (-not $State -or [string]::IsNullOrWhiteSpace([string]$State.ArtifactsDir) -or -not (Test-Path -LiteralPath $State.ArtifactsDir)) { return @() }

  $names = @(
    '28_TIER2_DEEP_CHECKS_tier2_reg_ifeo.txt',
    '29_TIER2_DEEP_CHECKS_tier2_reg_winlogon.txt',
    '30_TIER2_DEEP_CHECKS_tier2_reg_lsa.txt',
    '31_TIER2_DEEP_CHECKS_tier2_wmi_persistence.txt',
    '32_TIER2_DEEP_CHECKS_tier2_net_share.txt',
    '33_TIER2_DEEP_CHECKS_tier2_net_session.txt',
    '34_TIER2_DEEP_CHECKS_tier2_firewall_profiles.txt'
  )

  $paths = New-Object System.Collections.ArrayList
  foreach ($name in $names) {
    $path = Join-Path $State.ArtifactsDir $name
    if (Test-Path -LiteralPath $path) { [void]$paths.Add($path) }
  }
  return @($paths)
}

<#
.SYNOPSIS
Creates the run manifest JSON file with Tier 2 deep-check artifact inventory repair.

.DESCRIPTION
Preserves the original manifest behavior while appending existing Tier 2 deep-check root
artifact paths for Collect/T2 manifests. This keeps manifest_collect.json aligned with the
collect bundle contents and avoids downstream evidence-inventory gaps.

.FUNCTION NAME
New-Manifest

.INPUTS
ManifestPath, State, ModeName, TierName, Files array, ToolMap hashtable, and Extra
hashtable.

.OUTPUTS
String manifest path.
#>
function New-Manifest {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$ManifestPath,
    [hashtable]$State,
    [string]$ModeName,
    [string]$TierName,
    [string[]]$Files,
    [hashtable]$ToolMap,
    [hashtable]$Extra
  )

  $manifestFiles = New-Object System.Collections.ArrayList
  foreach ($file in @($Files)) {
    if ([string]::IsNullOrWhiteSpace($file)) { continue }
    if (-not @($manifestFiles).Contains($file)) { [void]$manifestFiles.Add($file) }
  }

  if (($ModeName -eq 'Collect') -and ($TierName -eq 'T2')) {
    foreach ($tier2Path in @(Get-Tier2DeepCheckManifestArtifactPaths -State $State)) {
      if (-not @($manifestFiles).Contains($tier2Path)) { [void]$manifestFiles.Add($tier2Path) }
    }
  }

  $manifest = [ordered]@{
    host = $env:COMPUTERNAME
    run_id = $State.RunId
    mode = $ModeName
    tier = $TierName
    script_version = $ScriptVersion
    created_local = (Get-Date).ToString('o')
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    files = @($manifestFiles)
    notes = @($Global:CollectorNotes)
    errors = @($Global:CollectorErrors)
    recommendations = @($Global:RecommendedActions)
    tool_map = $ToolMap
    extra = $Extra
  }
  if ($PSCmdlet.ShouldProcess($ManifestPath, 'Write collector manifest')) {
    Set-Content -Path $ManifestPath -Value (Convert-ToCollectorJsonText -InputObject $manifest -Label 'manifest JSON' -ThrowOnTruncation) -Encoding UTF8 -ErrorAction Stop
    return $ManifestPath
  }
  return $null
}

<#
.SYNOPSIS
Synchronizes the collection metadata section companion before bundling.

.DESCRIPTION
Uses the existing prefixed root collection metadata artifact as the source of truth and
rewrites final_artifacts/COLLECTION_METADATA/collection_metadata.txt immediately before
bundle creation. This keeps the strict Tier 2 bundle verifier aligned with the emitted
collector artifact shape without fabricating metadata when the root artifact is missing.
If the companion cannot be refreshed after manifest_collect.json has been written, bundle
creation stops so the collector does not emit a successful ZIP with a manifest that omits
the bundle-time error.

.FUNCTION NAME
Sync-CollectionMetadataCompanionArtifact

.INPUTS
ArtifactsDir string.

.OUTPUTS
Boolean true when no sync is required or the companion was refreshed; false when sync was
skipped by ShouldProcess.
#>
function Sync-CollectionMetadataCompanionArtifact {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$ArtifactsDir)

  if ([string]::IsNullOrWhiteSpace($ArtifactsDir) -or -not (Test-Path -LiteralPath $ArtifactsDir)) { return $true }

  $rootPath = Join-Path $ArtifactsDir '01_COLLECTION_METADATA_collection_metadata.txt'
  if (-not (Test-Path -LiteralPath $rootPath)) { return $true }

  try {
    $artifactText = Get-Content -LiteralPath $rootPath -Raw -ErrorAction Stop
    $artifactText = Add-BoundedCollectFieldsToCollectionMetadataText -Name 'collection_metadata.txt' -Text $artifactText
    $artifactText = Convert-CollectionMetadataValidationText -Text $artifactText
    $sectionDir = Join-Path $ArtifactsDir 'COLLECTION_METADATA'
    $sectionPath = Join-Path $sectionDir 'collection_metadata.txt'
    if ($PSCmdlet.ShouldProcess($sectionPath, 'Synchronize collection metadata companion artifact')) {
      Ensure-Directory -Path $sectionDir
      $syncPath = Write-DCOIRUtf8NoBomText -Path $sectionPath -Text $artifactText
      return (-not [string]::IsNullOrWhiteSpace($syncPath))
    }
    return $false
  } catch {
    $message = "Failed to synchronize collection metadata companion artifact: $($_.Exception.Message)"
    Add-CollectorError $message
    throw $message
  }
}

<#
.SYNOPSIS
Creates one ZIP bundle from the supplied paths after synchronizing metadata companions.

.DESCRIPTION
Preserves the original New-BundleZip behavior while refreshing collection metadata
section companions for any final_artifacts directory in the bundle input list. This makes
bundle-level metadata validation deterministic even when the verifier reads the section
companion path instead of the prefixed root artifact path.

.FUNCTION NAME
New-BundleZip

.INPUTS
BundlesDir string, BundleName string, and Paths string array.

.OUTPUTS
String bundle ZIP path, or null when archive creation is skipped.
#>
function New-BundleZip {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$BundlesDir,
    [string]$BundleName,
    [string[]]$Paths
  )

  $bundlePath = Join-Path $BundlesDir $BundleName
  if (-not $PSCmdlet.ShouldProcess($bundlePath, 'Create collector ZIP bundle')) {
    return $null
  }

  $existing = @($Paths | Where-Object { $_ -and (Test-Path -LiteralPath $_) })
  if (@($existing).Count -eq 0) {
    throw 'No bundle inputs were found.'
  }

  foreach ($candidatePath in @($Paths)) {
    if ([string]::IsNullOrWhiteSpace($candidatePath) -or -not (Test-Path -LiteralPath $candidatePath)) { continue }
    $item = Get-Item -LiteralPath $candidatePath -ErrorAction SilentlyContinue
    if ($item -and $item.PSIsContainer -and ($item.Name -eq 'final_artifacts')) {
      $metadataCompanionSynced = Sync-CollectionMetadataCompanionArtifact -ArtifactsDir $item.FullName
      if (-not $metadataCompanionSynced) { return $null }
    }
  }

  Ensure-Directory -Path $BundlesDir
  if (Test-Path -LiteralPath $bundlePath) {
    Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
  }
  Compress-Archive -LiteralPath $existing -DestinationPath $bundlePath -CompressionLevel Optimal -Force -ErrorAction Stop
  return $bundlePath
}
