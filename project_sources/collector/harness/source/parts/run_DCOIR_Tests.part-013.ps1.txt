  $productionCollect = Invoke-CollectorStepWithEnvOverride -StepName "73_CollectT1_ProductionEventTextOversize" -CollectorArgs @("-Quick","collect-t1") -EnvOverrides @{ 'DCOIR_TEST_SECURITY_FILTERED_OVERSIZE_KB' = '2600'; 'DCOIR_TEST_POWERSHELL_OPERATIONAL_OVERSIZE_KB' = '2600'; 'DCOIR_TEST_TASKSCHEDULER_OPERATIONAL_OVERSIZE_KB' = '2600' }
  Assert-CollectorStepSucceeded -StepName "73_CollectT1_ProductionEventTextOversize" -CollectorStep $productionCollect
  Invoke-ProductionChunkingVerification -StepName "ZZ_ProductionEventTextChunkingValidation" -CollectStep $productionCollect
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "74_CleanupProductionEventText" -CollectorArgs @("-Quick","cleanup")) }
}

<#
.SYNOPSIS
Runs the chunk-reconstruction metadata validation suite.

.DESCRIPTION
Exercises collect with the synthetic oversized artifact environment override and verifies
that the emitted reconstruction metadata can rebuild the original artifact exactly.

.FUNCTION NAME
Run-ChunkingReconstructionMetadataSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-ChunkingReconstructionMetadataSuite {
  Restore-WorkingZip -Reason "ChunkingReconstructionMetadata"
  $collect = Invoke-CollectorStepWithEnvOverride -StepName "81_CollectT1_SyntheticOversizeReconstruction" -CollectorArgs @("-Quick","collect-t1") -EnvOverrides @{ 'DCOIR_TEST_SYNTHETIC_OVERSIZE_ARTIFACT_KB' = '2600' }
  Assert-CollectorStepSucceeded -StepName "81_CollectT1_SyntheticOversizeReconstruction" -CollectorStep $collect
  Invoke-ChunkingReconstructionVerification -StepName "ZZ_ChunkingReconstructionValidation" -CollectStep $collect
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "82_Cleanup" -CollectorArgs @("-Quick","cleanup")) }
}

<#
.SYNOPSIS
Runs the bounded Tier 2 collect validation suite.

.DESCRIPTION
Exercises the advertised Tier 2 collection path under the normal runner-safe harness
contract and verifies the standard collect output contract plus attachment budget
manifest when emitted.

.FUNCTION NAME
Run-Tier2BoundedCollectSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-Tier2BoundedCollectSuite {
  Restore-WorkingZip -Reason "Tier2BoundedCollect"
  $collect = Invoke-CollectorStep -StepName "83_CollectT2_Bounded" -CollectorArgs @("-Tier","T2","-Hours","1","-MaxEvents","100")
  Assert-CollectorStepSucceeded -StepName "83_CollectT2_Bounded" -CollectorStep $collect
  Invoke-CollectOutputContractVerification -StepName "ZZ_CollectT2OutputContract" -CollectStep $collect
  Invoke-CollectManifestBundleComparison -StepName "ZZ_CollectT2ManifestBundleComparison" -CollectStep $collect
  Invoke-Tier2CollectVerification -StepName "ZZ_Tier2SpecificOutputValidation" -CollectStep $collect -ExpectedHours 1 -ExpectedMaxEvents 100
  if ($collect.AttachmentBudgetManifestPath) { Invoke-AttachmentBudgetVerification -StepName "ZZ_AttachmentBudget_CollectT2" -ManifestPath $collect.AttachmentBudgetManifestPath }
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "84_CleanupT2" -CollectorArgs @("-Quick","cleanup")) }
}
