
<#
.SYNOPSIS
Runs the major-version validation suite.

.DESCRIPTION
Executes the bounded group of suites that make up the current major-version validation
surface.

.FUNCTION NAME
Run-MajorVersionSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite group.
#>
function Run-MajorVersionSuite {
  Run-CoreSuite
  Run-QuickAliasesSuite
  Run-SessionBehaviorSuite
  Run-TargetedCollectionSuite
  Run-ChunkingOversizeArtifactSuite
  Run-ChunkingReconstructionMetadataSuite
  Run-Tier2BoundedCollectSuite
}

Ensure-Directory -Path $RunOutputRoot
Ensure-Directory -Path $LogsDir

try {
  switch ($Suite) {
    "Core" { Run-CoreSuite }
    "Retrieval" { Run-RetrievalSuite }
    "QuickAliases" { Run-QuickAliasesSuite }
    "SessionBehavior" { Run-SessionBehaviorSuite }
    "TargetedCollection" { Run-TargetedCollectionSuite }
    "ChunkingOversizeArtifact" { Run-ChunkingOversizeArtifactSuite }
    "ChunkingReconstructionMetadata" { Run-ChunkingReconstructionMetadataSuite }
    "Tier2BoundedCollect" { Run-Tier2BoundedCollectSuite }
    "MajorVersion" { Run-MajorVersionSuite }
    "FailureGates" { Run-FailureGatesSuite }
    "FullRegression" {
      Run-CoreSuite
      Run-RetrievalSuite
      Run-QuickAliasesSuite
      Run-SessionBehaviorSuite
      Run-TargetedCollectionSuite
      Run-ChunkingOversizeArtifactSuite
      Run-ChunkingReconstructionMetadataSuite
      Run-Tier2BoundedCollectSuite
      Run-FailureGatesSuite
    }
  }
  Save-Summary
  if (-not $ContinueOnError) {
    $failedResults = @($script:Results | Where-Object { $_.Status -eq 'FAIL' })
    if (@($failedResults).Count -gt 0) {
      Write-Error ("Harness recorded {0} failed result row(s); see summary at {1}" -f @($failedResults).Count, $RunOutputRoot)
      exit 1
    }
  }
} catch {
  Save-Summary
  Write-Error $_.Exception.Message
  exit 1
}
