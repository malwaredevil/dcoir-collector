
<#
.SYNOPSIS
Runs the failure-gates validation suite.

.DESCRIPTION
Exercises bind-reject, malformed quick input, and targeted explicit-window degradation
cases plus the targeted-collection verifier and optional cleanup.

.FUNCTION NAME
Run-FailureGatesSuite

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes the suite and writes harness results.
#>
function Run-FailureGatesSuite {
  Restore-WorkingZip -Reason "FailureGates"

  [void](Invoke-ExpectedFailureStep -StepName "91_InvalidMode" -CollectorArgs @("-Mode","Bogus") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("Mode","Bogus"))
  [void](Invoke-ExpectedFailureStep -StepName "92_InvalidTier" -CollectorArgs @("-Tier","Bogus") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("Tier","Bogus"))
  [void](Invoke-ExpectedFailureStep -StepName "93_InvalidAction" -CollectorArgs @("-Mode","Enrich","-Action","Bogus") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("Action","Bogus"))
  [void](Invoke-ExpectedFailureStep -StepName "94_InvalidTargetProfile" -CollectorArgs @("-TargetProfile","Bogus") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("TargetProfile","Bogus"))

  $quickHelp = Invoke-CollectorStep -StepName "95_QuickHelp" -CollectorArgs @("-Quick","help")
  Assert-CollectorStepSucceeded -StepName "95_QuickHelp" -CollectorStep $quickHelp
  if (-not [regex]::IsMatch($quickHelp.StdOut, [regex]::Escape("Quick command examples:"))) {
    throw "Quick help output did not include quick command examples."
  }
  [void](Invoke-ExpectedFailureStep -StepName "96_QuickUnknown" -CollectorArgs @("-Quick","unknown-value") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("Unknown -Quick value","Quick command examples:"))
  [void](Invoke-ExpectedFailureStep -StepName "97_QuickSigcheckMissingTarget" -CollectorArgs @("-Quick","enrich-start-sigcheck") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("requires -Target <path>"))
  [void](Invoke-ExpectedFailureStep -StepName "98_QuickListDllsBadPid" -CollectorArgs @("-Quick","enrich-start-listdlls","-Target","abc") -ExpectedOutcome 'BIND_REJECT' -ExpectedPatterns @("requires a numeric -Target <pid>"))

  $unsafeInputOutRoot = Join-Path $RunOutputRoot 'unsafe_input_validation'
  Remove-Item -LiteralPath $unsafeInputOutRoot -Recurse -Force -ErrorAction SilentlyContinue
  $oversizedRunId = 'A' * 129
  [void](Invoke-ExpectedFailureStep -StepName "98A_UnsafeRunIdRejectsTraversal" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-RunId","..\escape") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid RunId","filename-leaf"))
  [void](Invoke-ExpectedFailureStep -StepName "98A2_UnsafeRunIdRejectsExplicitBlank" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-RunId","") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid RunId","must not be blank"))
  [void](Invoke-ExpectedFailureStep -StepName "98A3_UnsafeRunIdRejectsOversized" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-RunId",$oversizedRunId) -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid RunId","1-128"))
  [void](Invoke-ExpectedFailureStep -StepName "98A4_UnsafePackageNameRejectsTraversal" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-PackageName","..\DCOIR_Collector.zip") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid PackageName","filename leaf"))
  [void](Invoke-ExpectedFailureStep -StepName "98A5_UnsafePackageNameRejectsRootedPath" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-PackageName","C:\Temp\DCOIR_Collector.zip") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid PackageName","filename leaf"))
  [void](Invoke-ExpectedFailureStep -StepName "98A6_UnsafePackageNameRejectsNonZip" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-PackageName","DCOIR_Collector.txt") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid PackageName",".zip"))
  [void](Invoke-ExpectedFailureStep -StepName "98A7_UnsafePackageNameRejectsExplicitBlank" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-PackageName","") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid PackageName","nonblank"))
  [void](Invoke-ExpectedFailureStep -StepName "98A8_UnsafeRunIdRejectsRootedPath" -CollectorArgs @("-Quick","collect-t1","-OutRoot",$unsafeInputOutRoot,"-RunId","C:\Temp\escape") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid RunId","filename-leaf"))
  [void](Invoke-ExpectedFailureStep -StepName "98A9_UnsafeCleanupRunIdRejectsTraversal" -CollectorArgs @("-Quick","cleanup","-OutRoot",$unsafeInputOutRoot,"-RunId","..\escape") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid RunId","filename-leaf"))
  [void](Invoke-ExpectedFailureStep -StepName "98A10_UnsafeCleanupPackageNameRejectsTraversal" -CollectorArgs @("-Quick","cleanup","-OutRoot",$unsafeInputOutRoot,"-PackageName","..\DCOIR_Collector.zip") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid PackageName","filename leaf"))
  [void](Invoke-ExpectedFailureStep -StepName "98A11_UnsafeRunIdRejectsTrailingDot" -CollectorArgs @("-Quick","cleanup","-OutRoot",$unsafeInputOutRoot,"-RunId","custom.") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Invalid RunId","filename-leaf"))
  if (Test-Path -LiteralPath $unsafeInputOutRoot) {
    throw 'Unsafe RunId/PackageName validation created the unsafe-input OutRoot before rejecting the request.'
  }

  [void](Invoke-ExpectedFailureStep -StepName "98B_MissingPackageCheckedPaths" -CollectorArgs @("-Quick","collect-t1","-PackageName","DCOIR_MISSING_TEST_PACKAGE.zip") -ExpectedOutcome 'RUNTIME_ERROR' -ExpectedPatterns @("Package not found:","CheckedPaths="))
  $strayDir = Join-Path 'C:\Temp' 'DCOIR_OPERATOR_NOT_A_RUN'
  New-Item -Path $strayDir -ItemType Directory -Force | Out-Null
  Set-Content -Path (Join-Path $strayDir 'keep.txt') -Value 'must-not-delete' -Encoding UTF8
  $cleanupAfterMissingPackage = Invoke-CollectorStep -StepName "98C_CleanupAfterMissingPackageNoState" -CollectorArgs @("-Quick","cleanup")
  Assert-CollectorStepSucceeded -StepName "98C_CleanupAfterMissingPackageNoState" -CollectorStep $cleanupAfterMissingPackage
  if ($cleanupAfterMissingPackage.CleanupStatus -notin @('MISSING_STATE_ORPHAN_CLEANED','NO_TARGET_FOUND')) {
    throw ("Cleanup after missing package returned unexpected status: {0}" -f $cleanupAfterMissingPackage.CleanupStatus)
  }
  if (-not (Test-Path -LiteralPath (Join-Path $strayDir 'keep.txt'))) {
    throw 'No-state cleanup deleted an unrelated DCOIR_* directory.'
  }
  Remove-Item -LiteralPath $strayDir -Recurse -Force -ErrorAction SilentlyContinue

  $customLikeRunId = 'custom-like-preserve'
  $customLikeDir = Join-Path 'C:\Temp' ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $customLikeRunId)
  New-Item -Path $customLikeDir -ItemType Directory -Force | Out-Null
  foreach ($child in @('tools','reports','final_artifacts','logs','bundles')) {
    New-Item -Path (Join-Path $customLikeDir $child) -ItemType Directory -Force | Out-Null
  }
  Set-Content -Path (Join-Path $customLikeDir 'keep.txt') -Value 'custom-like-must-not-delete-without-explicit-runid' -Encoding UTF8
  $customNoStatePlainCleanup = Invoke-CollectorStep -StepName "98D_CleanupPreservesCustomLikeNoStateWithoutRunId" -CollectorArgs @("-Quick","cleanup")
  Assert-CollectorStepSucceeded -StepName "98D_CleanupPreservesCustomLikeNoStateWithoutRunId" -CollectorStep $customNoStatePlainCleanup
  if ($customNoStatePlainCleanup.CleanupStatus -notin @('NO_TARGET_FOUND','MISSING_STATE_ORPHAN_CLEANED')) {
    throw ("Plain cleanup returned unexpected status while preserving custom no-state root: {0}" -f $customNoStatePlainCleanup.CleanupStatus)
  }
  if (-not (Test-Path -LiteralPath (Join-Path $customLikeDir 'keep.txt'))) {
    throw 'Plain cleanup deleted a custom RunId-like no-state directory without an explicit RunId.'
  }

  $statefulCustomRunId = 'custom-state-preserve'
  $statefulCustomDir = Join-Path 'C:\Temp' ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $statefulCustomRunId)
  New-Item -Path $statefulCustomDir -ItemType Directory -Force | Out-Null
  foreach ($child in @('tools','reports','final_artifacts','logs','bundles')) {
    New-Item -Path (Join-Path $statefulCustomDir $child) -ItemType Directory -Force | Out-Null
  }
  Set-Content -Path (Join-Path $statefulCustomDir 'keep.txt') -Value 'stateful-custom-must-not-delete-without-explicit-runid' -Encoding UTF8
  $statefulCustomState = [ordered]@{
    RunId = $statefulCustomRunId
    RunRoot = $statefulCustomDir
    PackagePath = (Join-Path 'C:\Temp' 'DCOIR_STATEFUL_CUSTOM_TEST_PACKAGE.zip')
    CollectorVersion = '4.0.7'
  }
  Set-Content -Path (Join-Path $statefulCustomDir 'state.json') -Value ($statefulCustomState | ConvertTo-Json -Depth 5) -Encoding UTF8
  $statefulCustomPlainCleanup = Invoke-CollectorStep -StepName "98E_CleanupPreservesCustomStateWithoutRunId" -CollectorArgs @("-Quick","cleanup")
  Assert-CollectorStepSucceeded -StepName "98E_CleanupPreservesCustomStateWithoutRunId" -CollectorStep $statefulCustomPlainCleanup
  if (-not (Test-Path -LiteralPath (Join-Path $statefulCustomDir 'keep.txt'))) {
    throw 'Plain cleanup deleted a state-backed custom RunId directory without an explicit RunId.'
  }
  Remove-Item -LiteralPath $statefulCustomDir -Recurse -Force -ErrorAction SilentlyContinue

  $explicitCustomRunId = 'custom-like-preserve'
  $explicitCleanup = Invoke-CollectorStep -StepName "98F_CleanupExplicitCustomNoState" -CollectorArgs @("-Quick","cleanup","-RunId",$explicitCustomRunId)
  Assert-CollectorStepSucceeded -StepName "98F_CleanupExplicitCustomNoState" -CollectorStep $explicitCleanup
  if ($explicitCleanup.CleanupStatus -ne 'MISSING_STATE_ORPHAN_CLEANED') {
    throw ("Explicit custom RunId no-state cleanup returned unexpected status: {0}" -f $explicitCleanup.CleanupStatus)
  }
  if (Test-Path -LiteralPath $customLikeDir) {
    throw 'Explicit custom RunId no-state cleanup did not remove the collector-structured custom run root.'
  }

  $dottedCustomRunId = 'custom.safe-01'
  $dottedCustomDir = Join-Path 'C:\Temp' ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $dottedCustomRunId)
  New-Item -Path $dottedCustomDir -ItemType Directory -Force | Out-Null
  foreach ($child in @('tools','reports','final_artifacts','logs','bundles')) {
    New-Item -Path (Join-Path $dottedCustomDir $child) -ItemType Directory -Force | Out-Null
  }
  $dottedCustomCleanup = Invoke-CollectorStep -StepName "98G_CleanupExplicitDottedCustomNoState" -CollectorArgs @("-Quick","cleanup","-RunId",$dottedCustomRunId)
  Assert-CollectorStepSucceeded -StepName "98G_CleanupExplicitDottedCustomNoState" -CollectorStep $dottedCustomCleanup
  if ($dottedCustomCleanup.CleanupStatus -ne 'MISSING_STATE_ORPHAN_CLEANED') {
    throw ("Explicit dotted custom RunId no-state cleanup returned unexpected status: {0}" -f $dottedCustomCleanup.CleanupStatus)
  }
  if (Test-Path -LiteralPath $dottedCustomDir) {
    throw 'Explicit dotted custom RunId no-state cleanup did not remove the collector-structured custom run root.'
  }

