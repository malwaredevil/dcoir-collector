<#
.SYNOPSIS
DCOIR collector PR #186 external-review fix helpers.

.DESCRIPTION
Applies narrowly scoped helper refinements for external review findings after the initial
PR #186 review fixes and before the main collector entrypoint runs.

.FILE NAME
DCOIR_Collector.04G1_PR186_External_Review_Fixes.ps1

.INPUTS
Current collector globals, run-root directory names, package name, and operator-supplied
or generated RunId value.

.OUTPUTS
Maintained helper functions used by the compiled collector runtime.
#>

<#
.SYNOPSIS
Checks whether an exact custom RunId root is safe to purge before collection.

.DESCRIPTION
Requires the expected run-root name plus collector ownership evidence before a custom
RunId collect may remove a pre-existing exact run root. A state-backed run root is treated
as collector-owned. A no-state run root must satisfy the same collector-created child
structure required by no-state cleanup. Unsafe existing roots are not removed.

.FUNCTION NAME
Test-DCOIRExactCustomRunRootPurgeCandidate

.INPUTS
DirectoryInfo object.

.OUTPUTS
Boolean.
#>
function Test-DCOIRExactCustomRunRootPurgeCandidate {
  param([object]$Directory)
  if (-not $Directory) { return $false }
  if (-not (Test-DCOIRRunDirectoryName -Name $Directory.Name)) { return $false }
  if (Test-Path -LiteralPath (Join-Path $Directory.FullName 'state.json')) { return $true }
  return (Test-DCOIRNoStateCleanupCandidate -Directory $Directory)
}

<#
.SYNOPSIS
Deletes prior collector run directories before a new collect starts.

.DESCRIPTION
Keeps blank/latest automatic purge bounded to timestamp-style collector run roots. When a
custom RunId is supplied for a new collect, also deletes only the exact expected custom
run root when collector ownership is proven by state.json or the no-state cleanup child
structure. If an unsafe exact custom root exists, collection stops before new artifacts are
written. If a required exact custom root or prior package purge is declined, collection
returns the same skipped-preparation contract used by the main collect handler.

.FUNCTION NAME
Purge-PreviousRuns

.INPUTS
Root string and CurrentPackageName string.

.OUTPUTS
Boolean true when prior run/package purge did not block collect startup, false when a
required confirmation-decline path skipped collect preparation. Throws when the exact
custom run root is unsafe or remains after deletion.
#>
function Purge-PreviousRuns {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$Root,[string]$CurrentPackageName)

  $script:CollectPrepSkipReason = $null

  try {
    $currentRunId = [string]$script:RunId
    if (-not [string]::IsNullOrWhiteSpace($currentRunId)) {
      $expectedRunRoot = Get-RunRoot -Root $Root -CurrentRunId $currentRunId
      $expectedRunName = Split-Path -Leaf $expectedRunRoot
      if ((Test-DCOIRRunDirectoryName -Name $expectedRunName) -and
          -not (Test-DCOIRBulkPurgeRunDirectoryName -Name $expectedRunName) -and
          (Test-Path -LiteralPath $expectedRunRoot)) {
        $expectedRunDir = Get-Item -LiteralPath $expectedRunRoot -ErrorAction SilentlyContinue
        if (-not (Test-DCOIRExactCustomRunRootPurgeCandidate -Directory $expectedRunDir)) {
          throw "Existing custom RunId directory is not collector-owned and will not be removed before collect: $expectedRunRoot"
        }
        if ($PSCmdlet.ShouldProcess($expectedRunRoot, 'Remove existing custom collector run root')) {
          Remove-Item -LiteralPath $expectedRunRoot -Recurse -Force -ErrorAction SilentlyContinue
          if (Test-Path -LiteralPath $expectedRunRoot) {
            throw "Existing custom RunId directory could not be removed before collect: $expectedRunRoot"
          }
        } else {
          $script:CollectPrepSkipReason = 'CUSTOM_RUN_PURGE_SKIPPED'
          return $false
        }
      }
    }
  } catch {
    Add-CollectorError "Failed to purge exact custom RunId directory: $($_.Exception.Message)"
    throw
  }

  try {
    $dirs = Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue |
      Where-Object { Test-DCOIRBulkPurgeRunDirectoryName -Name $_.Name }
    foreach ($dir in $dirs) {
      if ($PSCmdlet.ShouldProcess($dir.FullName, 'Remove previous collector run directory')) {
        Remove-Item -LiteralPath $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
      }
    }
  } catch {
    Add-CollectorError "Failed to purge previous DCOIR directories: $($_.Exception.Message)"
  }

  try {
    $pkg = Join-Path $Root $CurrentPackageName
    if (Test-Path -LiteralPath $pkg) {
      if ($PSCmdlet.ShouldProcess($pkg, 'Remove previous collector package')) {
        Remove-Item -LiteralPath $pkg -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $pkg) {
          $script:CollectPrepSkipReason = 'PACKAGE_PURGE_SKIPPED'
          return $false
        }
      } else {
        $script:CollectPrepSkipReason = 'PACKAGE_PURGE_SKIPPED'
        return $false
      }
    }
  } catch {
    Add-CollectorError "Failed to remove previous collector package: $($_.Exception.Message)"
    $script:CollectPrepSkipReason = 'PACKAGE_PURGE_SKIPPED'
    return $false
  }

  return $true
}

<#
.SYNOPSIS
Adds bounded collect fields to the collection metadata artifact when absent.

.DESCRIPTION
Keeps collection_metadata.txt aligned with the run-window fields already emitted in the
metadata report so bundle-level validators and operators can read the bounded collection
shape from either metadata surface.

.FUNCTION NAME
Add-BoundedCollectFieldsToCollectionMetadataText

.INPUTS
Artifact name and candidate text.

.OUTPUTS
Text with Mode, Tier, Hours, and MaxEvents fields appended when the artifact is
collection_metadata.txt and those fields are absent.
#>
function Add-BoundedCollectFieldsToCollectionMetadataText {
  param([string]$Name,[string]$Text)

  if ($Name -ne 'collection_metadata.txt') { return $Text }
  $updated = [string]$Text
  $lines = New-Object System.Collections.ArrayList
  if ($updated -notmatch '(?m)^Mode=') { [void]$lines.Add('Mode=Collect') }
  if ($updated -notmatch '(?m)^Tier=') { [void]$lines.Add(('Tier={0}' -f $Tier)) }
  if ($updated -notmatch '(?m)^Hours=') { [void]$lines.Add(('Hours={0}' -f $Hours)) }
  if ($updated -notmatch '(?m)^MaxEvents=') { [void]$lines.Add(('MaxEvents={0}' -f $MaxEvents)) }
  if (@($lines).Count -gt 0) {
    if (-not $updated.EndsWith([Environment]::NewLine)) { $updated += [Environment]::NewLine }
    $updated += ((@($lines) -join [Environment]::NewLine) + [Environment]::NewLine)
  }
  return $updated
}

<#
.SYNOPSIS
Normalizes collection metadata text for strict line-oriented bundle validators.

.DESCRIPTION
Converts collection_metadata.txt to LF line endings after bounded collect fields are
present. This preserves the metadata values while ensuring validators that use exact
line anchors can match Tier, Hours, and MaxEvents inside ZIP entries on Windows runners.

.FUNCTION NAME
Convert-CollectionMetadataValidationText

.INPUTS
Metadata text.

.OUTPUTS
LF-normalized metadata text.
#>
function Convert-CollectionMetadataValidationText {
  param([string]$Text)
  return ([string]$Text -replace "`r`n", "`n" -replace "`r", "`n")
}

<#
.SYNOPSIS
Writes UTF-8 text without BOM using exact text content.

.DESCRIPTION
Avoids Set-Content newline normalization for metadata surfaces that are validated with
strict line anchors from inside ZIP bundles.

.FUNCTION NAME
Write-DCOIRUtf8NoBomText

.INPUTS
Path and text.

.OUTPUTS
No direct output. Writes text to disk.
#>
function Write-DCOIRUtf8NoBomText {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$Path,[string]$Text)
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  if ($PSCmdlet.ShouldProcess($Path, 'Write UTF-8 text without BOM')) {
    [System.IO.File]::WriteAllText($Path, [string]$Text, $utf8NoBom)
    return $Path
  }
  return $null
}

<#
.SYNOPSIS
Writes one collector artifact and a section-directory companion copy.

.DESCRIPTION
Preserves the existing prefixed root artifact path returned by Write-ArtifactText while
also writing a same-content companion under final_artifacts/<section>/<name>. The collect
bundle already includes the artifact directory recursively, and the section companion
keeps bundle validation aligned with the documented section/key artifact model without
changing existing response paths, manifests, or upload-budget behavior.

.FUNCTION NAME
Write-ArtifactText

.INPUTS
Artifact directory, section name, artifact name, and text content.

.OUTPUTS
The existing prefixed root artifact path.
#>
function Write-ArtifactText {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param(
    [string]$ArtifactsDir,
    [string]$Section,
    [string]$Name,
    [string]$Text
  )

  $prefix = Get-BaselineArtifactPrefix -Name $Name
  $safeSection = ($Section -replace '[\/:*?"<>| ]','_')
  $safeName = ($Name -replace '[\/:*?"<>| ]','_')
  $artifactText = Add-BoundedCollectFieldsToCollectionMetadataText -Name $Name -Text $Text
  if ($Name -eq 'collection_metadata.txt') {
    $artifactText = Convert-CollectionMetadataValidationText -Text $artifactText
  }
  $path = Join-Path $ArtifactsDir ("{0}_{1}_{2}" -f $prefix, $safeSection, $safeName)
  $wroteRootArtifact = $false
  if ($PSCmdlet.ShouldProcess($path, 'Write collector artifact')) {
    Ensure-Directory -Path $ArtifactsDir
    if ($Name -eq 'collection_metadata.txt') {
      $wroteRootArtifact = -not [string]::IsNullOrWhiteSpace((Write-DCOIRUtf8NoBomText -Path $path -Text $artifactText))
    } else {
      Set-Content -Path $path -Value $artifactText -Encoding UTF8 -ErrorAction Stop
      $wroteRootArtifact = $true
    }
  }

  try {
    if (-not [string]::IsNullOrWhiteSpace($safeSection) -and -not [string]::IsNullOrWhiteSpace($safeName)) {
      $sectionDir = Join-Path $ArtifactsDir $safeSection
      $sectionPath = Join-Path $sectionDir $safeName
      if ($PSCmdlet.ShouldProcess($sectionPath, 'Write collector section companion artifact')) {
        Ensure-Directory -Path $sectionDir
        if ($Name -eq 'collection_metadata.txt') {
          Write-DCOIRUtf8NoBomText -Path $sectionPath -Text $artifactText
        } else {
          Set-Content -Path $sectionPath -Value $artifactText -Encoding UTF8 -ErrorAction Stop
        }
      }
    }
  } catch {
    Add-CollectorError ("Failed to write section companion artifact [{0}/{1}]: {2}" -f $safeSection, $safeName, $_.Exception.Message)
  }

  if ($wroteRootArtifact) { return $path }
  return $null
}
