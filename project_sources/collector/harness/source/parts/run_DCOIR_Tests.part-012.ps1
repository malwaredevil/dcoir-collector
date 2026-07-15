  [void](Invoke-CollectorStep -StepName "22_EnrichStartSigcheck" -CollectorArgs @("-Quick","enrich-start-sigcheck","-Target",$sampleBinaryPath))
  [void](Invoke-CollectorStep -StepName "23_EnrichFinalize_Sigcheck" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "24_EnrichStartStrings" -CollectorArgs @("-Quick","enrich-start-strings","-Target",$sampleBinaryPath))
  [void](Invoke-CollectorStep -StepName "25_EnrichFinalize_Strings" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "26_EnrichStartStreams" -CollectorArgs @("-Quick","enrich-start-streams","-Target",$sampleScriptPath))
  [void](Invoke-CollectorStep -StepName "27_EnrichFinalize_Streams" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "28_EnrichStartListDlls" -CollectorArgs @("-Quick","enrich-start-listdlls","-Target",$PID.ToString()))
  [void](Invoke-CollectorStep -StepName "29_EnrichFinalize_ListDlls" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "30_EnrichStartAccessFile" -CollectorArgs @("-Quick","enrich-start-access-file","-Target",$sampleBinaryPath))
  [void](Invoke-CollectorStep -StepName "31_EnrichFinalize_AccessFile" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "32_EnrichStartAccessService" -CollectorArgs @("-Quick","enrich-start-access-service","-Target",$sampleService))
  [void](Invoke-CollectorStep -StepName "33_EnrichFinalize_AccessService" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "34_EnrichStartAccessReg" -CollectorArgs @("-Quick","enrich-start-access-reg","-Target",$sampleRegistry))
  [void](Invoke-CollectorStep -StepName "35_EnrichFinalize_AccessReg" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "36_EnrichStartPullFile" -CollectorArgs @("-Quick","enrich-start-pull-file","-Target",$sampleBinaryPath))
  [void](Invoke-CollectorStep -StepName "37_EnrichFinalize_PullFile" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "38_EnrichStartPullScript" -CollectorArgs @("-Quick","enrich-start-pull-script","-Target",$sampleScriptPath))
  [void](Invoke-CollectorStep -StepName "39_EnrichFinalize_PullScript" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "40_EnrichStartPullTask" -CollectorArgs @("-Quick","enrich-start-pull-task","-Target",$sampleTask))
  [void](Invoke-CollectorStep -StepName "41_EnrichFinalize_PullTask" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "42_EnrichStartPullService" -CollectorArgs @("-Quick","enrich-start-pull-service","-Target",$sampleService))
  [void](Invoke-CollectorStep -StepName "43_EnrichFinalize_PullService" -CollectorArgs @("-Quick","enrich-finalize"))
  [void](Invoke-CollectorStep -StepName "44_EnrichStartPullWmiFile" -CollectorArgs @("-Quick","enrich-start-pull-wmi-file","-Target",$sampleScriptPath))
  [void](Invoke-CollectorStep -StepName "45_EnrichFinalize_PullWmiFile" -CollectorArgs @("-Quick","enrich-finalize"))
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "46_Cleanup" -CollectorArgs @("-Quick","cleanup")) }
}

<#
.SYNOPSIS
Runs the session-behavior validation suite.

.DESCRIPTION
Exercises collect, enrich-start, enrich-add reuse behavior, finalize, and optional
cleanup plus the enrich-open and session-reuse verifiers.

.FUNCTION NAME
Run-SessionBehaviorSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-SessionBehaviorSuite {
  Restore-WorkingZip -Reason "SessionBehavior"
  $collect = Invoke-CollectorStep -StepName "51_CollectT1" -CollectorArgs @("-Quick","collect-t1")
  Assert-CollectorStepSucceeded -StepName "51_CollectT1" -CollectorStep $collect
  if ($collect.AttachmentBudgetManifestPath) { Invoke-AttachmentBudgetVerification -StepName "ZZ_AttachmentBudget_SessionBehaviorCollect" -ManifestPath $collect.AttachmentBudgetManifestPath }

  [void](Invoke-ExpectedFailureStep -StepName "51B_EnrichFinalizeWithoutOpenSession" -CollectorArgs @("-Quick","enrich-finalize","-RunId",$script:CollectorRunId) -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("No open enrichment session is available to finalize."))

  $startStep = Invoke-CollectorStep -StepName "52_EnrichStartTcp" -CollectorArgs @("-Quick","enrich-start-tcp")
  Assert-CollectorStepSucceeded -StepName "52_EnrichStartTcp" -CollectorStep $startStep
  Invoke-EnrichOpenOutputContractVerification -StepName "ZZ_EnrichOpenOutputContract" -EnrichStep $startStep

  $addStep = Invoke-CollectorStep -StepName "53_EnrichAddLogTextSecurity" -CollectorArgs @("-Quick","enrich-add-logtext","-Target","Security")
  Assert-CollectorStepSucceeded -StepName "53_EnrichAddLogTextSecurity" -CollectorStep $addStep
  Invoke-SessionBehaviorVerification -StepName "ZZ_SessionReuseValidation" -StartSessionId $startStep.EnrichSessionId -AddSessionId $addStep.EnrichSessionId -StartMode $startStep.SessionResolutionMode -AddMode $addStep.SessionResolutionMode

  $explicitStep = Invoke-CollectorStep -StepName "54_EnrichAddExplicitSession" -CollectorArgs @("-Mode","Enrich","-RunId",$script:CollectorRunId,"-EnrichSessionId",$startStep.EnrichSessionId,"-Action","LogText","-LogName","Security","-MaxEvents","5")
  Assert-CollectorStepSucceeded -StepName "54_EnrichAddExplicitSession" -CollectorStep $explicitStep
  Invoke-SessionResolutionVerification -StepName "ZZ_ExplicitSessionReuseValidation" -SessionStep $explicitStep -ExpectedMode 'REUSED_REQUESTED_SESSION' -ExpectedSessionId $startStep.EnrichSessionId

  $forceNewStep = Invoke-CollectorStep -StepName "55_EnrichForceNewSession" -CollectorArgs @("-Mode","Enrich","-RunId",$script:CollectorRunId,"-NewEnrichSession","-Action","LogText","-LogName","Security","-MaxEvents","5")
  Assert-CollectorStepSucceeded -StepName "55_EnrichForceNewSession" -CollectorStep $forceNewStep
  Invoke-SessionResolutionVerification -StepName "ZZ_ForceNewSessionValidation" -SessionStep $forceNewStep -ExpectedMode 'CREATED_NEW_SESSION' -UnexpectedSessionId $startStep.EnrichSessionId

  $requestedFinalize = Invoke-CollectorStep -StepName "56_EnrichFinalizeRequestedOriginal" -CollectorArgs @("-Mode","Enrich","-RunId",$script:CollectorRunId,"-EnrichSessionId",$startStep.EnrichSessionId,"-FinalizeEnrichSession")
  Assert-CollectorStepSucceeded -StepName "56_EnrichFinalizeRequestedOriginal" -CollectorStep $requestedFinalize
  Invoke-EnrichFinalizedOutputContractVerification -StepName "ZZ_RequestedFinalizeOutputContract" -EnrichStep $requestedFinalize

  [void](Invoke-ExpectedFailureStep -StepName "57_EnrichAddFinalizedRequestedSession" -CollectorArgs @("-Mode","Enrich","-RunId",$script:CollectorRunId,"-EnrichSessionId",$startStep.EnrichSessionId,"-Action","LogText","-LogName","Security","-MaxEvents","5") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @(("Requested enrichment session is finalized and cannot be appended: {0}" -f $startStep.EnrichSessionId)))

  $openFinalize = Invoke-CollectorStep -StepName "58_EnrichFinalizeOpen" -CollectorArgs @("-Quick","enrich-finalize")
  Assert-CollectorStepSucceeded -StepName "58_EnrichFinalizeOpen" -CollectorStep $openFinalize
  Invoke-EnrichFinalizedOutputContractVerification -StepName "ZZ_OpenFinalizeOutputContract" -EnrichStep $openFinalize

  $afterFinalize = Invoke-CollectorStep -StepName "59_EnrichAddAfterFinalize" -CollectorArgs @("-Quick","enrich-add-logtext","-Target","Security")
  Assert-CollectorStepSucceeded -StepName "59_EnrichAddAfterFinalize" -CollectorStep $afterFinalize
  Invoke-SessionResolutionVerification -StepName "ZZ_AddAfterFinalizeValidation" -SessionStep $afterFinalize -ExpectedMode 'CREATED_NEW_SESSION' -UnexpectedSessionId $forceNewStep.EnrichSessionId

  [void](Invoke-ExpectedFailureStep -StepName "60_MissingRequestedEnrichSession" -CollectorArgs @("-Mode","Enrich","-RunId",$script:CollectorRunId,"-EnrichSessionId","ENRICH_DOES_NOT_EXIST","-Action","LogText","-LogName","Security") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Requested enrichment session was not found: ENRICH_DOES_NOT_EXIST"))

  if (-not $SkipCleanup) {
    $cleanup = Invoke-CollectorStep -StepName "61_CleanupAfterOpenSession" -CollectorArgs @("-Quick","cleanup")
    Assert-CollectorStepSucceeded -StepName "61_CleanupAfterOpenSession" -CollectorStep $cleanup
  }
}

<#
.SYNOPSIS
Runs the targeted-collection validation suite.

.DESCRIPTION
Exercises the targeted popup quick path and verifies the targeted-collection artifact
contract plus optional cleanup.

.FUNCTION NAME
Run-TargetedCollectionSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-TargetedCollectionSuite {
  Restore-WorkingZip -Reason "TargetedCollection"
  $collect = Invoke-CollectorStep -StepName "61_CollectTargetedPopup" -CollectorArgs @("-Quick","collect-targeted-popup","-Target","User reported popup around 2026-04-08T09:00Z","-WindowStart","2026-04-08T08:45:00Z","-WindowEnd","2026-04-08T09:15:00Z")
  Assert-CollectorStepSucceeded -StepName "61_CollectTargetedPopup" -CollectorStep $collect
  if ($collect.AttachmentBudgetManifestPath) { Invoke-AttachmentBudgetVerification -StepName "ZZ_AttachmentBudget_TargetedCollect" -ManifestPath $collect.AttachmentBudgetManifestPath }
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedCollectionValidation" -CollectStep $collect -ExpectedExplicitEventWindow $true -ExpectedWindowStart "2026-04-08T08:45:00Z" -ExpectedWindowEnd "2026-04-08T09:15:00Z" -ExpectedTargetProfile "PopupWindow" -ExpectedUserReport "User reported popup around 2026-04-08T09:00Z" -ExpectedPlanMarkers @("Security high-signal events around the reported time window.","PowerShell operational events and scheduled task activity.")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "62_Cleanup" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "TargetedCollection_NeutralWindow"
  $neutral = Invoke-CollectorStep -StepName "63_CollectTargetedNeutralWindow" -CollectorArgs @("-Targeted","-TargetProfile","PopupWindow","-WindowStart","2026-04-08T08:45:00Z","-WindowEnd","2026-04-08T09:15:00Z","-UserReport","User reported popup around 2026-04-08T09:00Z")
  Assert-CollectorStepSucceeded -StepName "63_CollectTargetedNeutralWindow" -CollectorStep $neutral
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedNeutralWindowValidation" -CollectStep $neutral -ExpectedExplicitEventWindow $true -ExpectedWindowStart "2026-04-08T08:45:00Z" -ExpectedWindowEnd "2026-04-08T09:15:00Z" -ExpectedTargetProfile "PopupWindow" -ExpectedUserReport "User reported popup around 2026-04-08T09:00Z" -ExpectedPlanMarkers @("likely GUI-launching processes","scheduled task activity")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "64_CleanupNeutralWindow" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "TargetedCollection_GenericProfile"
  $generic = Invoke-CollectorStep -StepName "65_CollectTargetedGenericProfile" -CollectorArgs @("-Targeted","-TargetProfile","Generic","-UserReport","Generic narrow follow-up for a suspicious file path","-FocusPath","C:\Users\Public\generic-target.ps1","-IncludeArtifactCategory","process_inventory,structured_net")
  Assert-CollectorStepSucceeded -StepName "65_CollectTargetedGenericProfile" -CollectorStep $generic
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedGenericProfileValidation" -CollectStep $generic -ExpectedTargetProfile "Generic" -ExpectedFocusPath "C:\Users\Public\generic-target.ps1" -ExpectedUserReport "Generic narrow follow-up for a suspicious file path" -ExpectedIncludedArtifactCategories @("process_inventory","structured_net") -ExpectedPlanMarkers @("Avoid defaulting to oversized merged review artifacts when smaller decisive artifacts are sufficient.","No explicit start-end time window was supplied.")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "66_CleanupGenericProfile" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "TargetedCollection_ScriptExecutionProfile"
  $scriptExecution = Invoke-CollectorStep -StepName "67_CollectTargetedScriptExecutionProfile" -CollectorArgs @("-Targeted","-TargetProfile","ScriptExecution","-UserReport","Suspicious PowerShell execution from a writable path","-FocusProcess","powershell.exe","-FocusPath","C:\Users\Public\payload.ps1","-IncludeArtifactCategory","powershell_operational,security_filtered")
  Assert-CollectorStepSucceeded -StepName "67_CollectTargetedScriptExecutionProfile" -CollectorStep $scriptExecution
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedScriptExecutionProfileValidation" -CollectStep $scriptExecution -ExpectedTargetProfile "ScriptExecution" -ExpectedFocusProcess "powershell.exe" -ExpectedFocusPath "C:\Users\Public\payload.ps1" -ExpectedUserReport "Suspicious PowerShell execution from a writable path" -ExpectedIncludedArtifactCategories @("powershell_operational","security_filtered") -ExpectedPlanMarkers @("PowerShell operational events and Security 4688 process creation records.","Strings, streams, or signature enrichment on the focal script or binary path.")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "68_CleanupScriptExecutionProfile" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "TargetedCollection_PersistenceProfile"
  $persistence = Invoke-CollectorStep -StepName "69_CollectTargetedPersistenceProfile" -CollectorArgs @("-Targeted","-TargetProfile","PersistenceFollowUp","-UserReport","Follow a persistence lead tied to a suspicious service","-FocusPath","C:\ProgramData\Acme\svc.exe","-IncludeArtifactCategory","scheduled_tasks,services")
  Assert-CollectorStepSucceeded -StepName "69_CollectTargetedPersistenceProfile" -CollectorStep $persistence
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedPersistenceProfileValidation" -CollectStep $persistence -ExpectedTargetProfile "PersistenceFollowUp" -ExpectedFocusPath "C:\ProgramData\Acme\svc.exe" -ExpectedUserReport "Follow a persistence lead tied to a suspicious service" -ExpectedIncludedArtifactCategories @("scheduled_tasks","services") -ExpectedPlanMarkers @("Services, scheduled tasks, Run keys, and autoruns.","Registry, service ACL, and task XML follow-up actions.")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "70_CleanupPersistenceProfile" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "TargetedCollection_NetworkOnlyProfile"
  $networkOnly = Invoke-CollectorStep -StepName "71_CollectTargetedNetworkOnlyProfile" -CollectorArgs @("-Targeted","-TargetProfile","NetworkOnly","-Hours","6","-FocusIndicator","198.51.100.25","-FocusIndicatorType","ip","-UserReport","Investigate a suspicious outbound connection","-IncludeArtifactCategory","structured_net,netstat_pid_only")
  Assert-CollectorStepSucceeded -StepName "71_CollectTargetedNetworkOnlyProfile" -CollectorStep $networkOnly
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedNetworkOnlyProfileValidation" -CollectStep $networkOnly -ExpectedTargetProfile "NetworkOnly" -ExpectedFocusIndicator "198.51.100.25" -ExpectedFocusIndicatorType "ip" -ExpectedUserReport "Investigate a suspicious outbound connection" -ExpectedIncludedArtifactCategories @("structured_net","netstat_pid_only") -ExpectedPlanMarkers @("Structured network state, netstat, tcpvcon, dns cache, route, and arp.","Follow-up TCP refresh enrichment.")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "72_CleanupNetworkOnlyProfile" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "TargetedCollection_ProcessPowerShellProfile"
  $processPowerShell = Invoke-CollectorStep -StepName "73_CollectTargetedProcessPowerShellProfile" -CollectorArgs @("-Targeted","-TargetProfile","ProcessAndPowerShell","-UserReport","Investigate suspicious PowerShell launched from a process tree","-FocusProcess","pwsh.exe","-FocusPath","C:\Users\Public\ps-runner.ps1","-IncludeArtifactCategory","process_inventory,powershell_operational")
  Assert-CollectorStepSucceeded -StepName "73_CollectTargetedProcessPowerShellProfile" -CollectorStep $processPowerShell
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedProcessPowerShellProfileValidation" -CollectStep $processPowerShell -ExpectedTargetProfile "ProcessAndPowerShell" -ExpectedFocusProcess "pwsh.exe" -ExpectedFocusPath "C:\Users\Public\ps-runner.ps1" -ExpectedUserReport "Investigate suspicious PowerShell launched from a process tree" -ExpectedIncludedArtifactCategories @("process_inventory","powershell_operational") -ExpectedPlanMarkers @("Process inventory, pslist, Security 4688, and PowerShell operational records.","Repeatable enrichment of process-centric context in one bounded session.")
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "74_CleanupProcessPowerShellProfile" -CollectorArgs @("-Quick","cleanup")) }
}

<#
.SYNOPSIS
Runs the oversized-artifact chunking validation suite.

.DESCRIPTION
Exercises collect with the synthetic oversized artifact environment override and verifies
that the emitted chunk set satisfies the per-file budget expectations.

.FUNCTION NAME
Run-ChunkingOversizeArtifactSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-ChunkingOversizeArtifactSuite {
  Restore-WorkingZip -Reason "ChunkingOversizeArtifact"
  $collect = Invoke-CollectorStepWithEnvOverride -StepName "71_CollectT1_SyntheticOversize" -CollectorArgs @("-Quick","collect-t1") -EnvOverrides @{ 'DCOIR_TEST_SYNTHETIC_OVERSIZE_ARTIFACT_KB' = '2600' }
  Assert-CollectorStepSucceeded -StepName "71_CollectT1_SyntheticOversize" -CollectorStep $collect
  Invoke-ChunkingOversizeVerification -StepName "ZZ_ChunkingOversizeValidation" -CollectStep $collect
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "72_Cleanup" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "ChunkingProductionEventText"
