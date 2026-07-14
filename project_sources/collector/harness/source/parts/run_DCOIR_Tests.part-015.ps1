  <#
  .SYNOPSIS
  Creates a synthetic state-backed cleanup authority fixture.

  .DESCRIPTION
  Builds a collector-shaped run root, writes a state.json record with caller-supplied
  cleanup authority fields, and returns the expected and recorded fixture paths for
  FailureGates state-cleanup refusal checks.

  .FUNCTION NAME
  Initialize-StateCleanupAuthorityFixture

  .INPUTS
  No pipeline input. Parameters describe the fixture out-root, run id, and state fields.

  .OUTPUTS
  Hashtable containing the expected run root, recorded run id, state path, recorded
  state path, and state package path.
  #>
  function Initialize-StateCleanupAuthorityFixture {
    param(
      [string]$FixtureOutRoot,
      [string]$FixtureRunId,
      [string]$StateRunRoot,
      [string]$StatePackagePath,
      [string]$StatePathOverride,
      [string]$StateRunIdOverride
    )

    New-Item -Path $FixtureOutRoot -ItemType Directory -Force | Out-Null
    $expectedRunRoot = Join-Path $FixtureOutRoot ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $FixtureRunId)
    New-Item -Path $expectedRunRoot -ItemType Directory -Force | Out-Null
    foreach ($child in @('tools','reports','final_artifacts','logs','bundles')) {
      New-Item -Path (Join-Path $expectedRunRoot $child) -ItemType Directory -Force | Out-Null
    }
    $statePath = Join-Path $expectedRunRoot 'state.json'
    $stateRunId = if ([string]::IsNullOrWhiteSpace($StateRunIdOverride)) { $FixtureRunId } else { $StateRunIdOverride }
    $state = [ordered]@{
      RunId = $stateRunId
      OutRoot = $FixtureOutRoot
      RunRoot = $StateRunRoot
      StatePath = if ([string]::IsNullOrWhiteSpace($StatePathOverride)) { $statePath } else { $StatePathOverride }
      PackagePath = $StatePackagePath
      CollectorVersion = '4.0.7'
    }
    Set-Content -Path $statePath -Value ($state | ConvertTo-Json -Depth 5) -Encoding UTF8
    return @{
      ExpectedRunRoot = $expectedRunRoot
      RecordedRunId = $stateRunId
      StatePath = $statePath
      RecordedStatePath = $state.StatePath
      StatePackagePath = $StatePackagePath
    }
  }

  <#
  .SYNOPSIS
  Asserts that a state-backed cleanup attempt was refused.

  .DESCRIPTION
  Verifies the collector step succeeded at the harness process level while reporting
  cleanup refusal status, a nonzero refused-target count, and refusal reason detail.

  .FUNCTION NAME
  Assert-StateCleanupRefused

  .INPUTS
  No pipeline input. Parameters identify the step name and collector step result.

  .OUTPUTS
  No direct output. Throws when refusal reporting is missing or unexpected.
  #>
  function Assert-StateCleanupRefused {
    param(
      [string]$StepName,
      $CollectorStep
    )
    Assert-CollectorStepSucceeded -StepName $StepName -CollectorStep $CollectorStep
    if (($CollectorStep.CleanupStatus -ne 'REFUSED') -and (-not [regex]::IsMatch($CollectorStep.StdOut, 'CLEANUP_STATUS=REFUSED'))) {
      throw ("{0} returned unexpected cleanup status: {1}" -f $StepName, $CollectorStep.CleanupStatus)
    }
    if (-not [regex]::IsMatch($CollectorStep.StdOut, 'CLEANUP_REFUSED_COUNT=[1-9]')) {
      throw ("{0} did not report refused cleanup targets." -f $StepName)
    }
    if (-not [regex]::IsMatch($CollectorStep.StdOut, 'CLEANUP_REFUSAL_REASON=')) {
      throw ("{0} did not report cleanup refusal reason detail." -f $StepName)
    }
  }

  $stateCleanupRoot = Join-Path $RunOutputRoot 'state_cleanup_path_authority'
  $stateCleanupOutRoot = Join-Path $stateCleanupRoot 'outroot'
  Remove-Item -LiteralPath $stateCleanupRoot -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -Path $stateCleanupOutRoot -ItemType Directory -Force | Out-Null

  $outsideRunRoot = Join-Path $stateCleanupRoot 'outside_runroot_must_not_delete'
  New-Item -Path $outsideRunRoot -ItemType Directory -Force | Out-Null
  Set-Content -Path (Join-Path $outsideRunRoot 'must-not-delete.txt') -Value 'outside-runroot' -Encoding UTF8
  $outsideRunRootPackage = Join-Path $stateCleanupOutRoot 'DCOIR_Collector.zip'
  Set-Content -Path $outsideRunRootPackage -Value 'package-placeholder' -Encoding UTF8
  [void](Initialize-StateCleanupAuthorityFixture -FixtureOutRoot $stateCleanupOutRoot -FixtureRunId 'state-outside-runroot' -StateRunRoot $outsideRunRoot -StatePackagePath $outsideRunRootPackage)
  $outsideRunRootCleanup = Invoke-CollectorStep -StepName "98H_StateCleanupRejectsOutsideRunRoot" -CollectorArgs @("-Quick","cleanup","-OutRoot",$stateCleanupOutRoot,"-RunId","state-outside-runroot")
  Assert-StateCleanupRefused -StepName "98H_StateCleanupRejectsOutsideRunRoot" -CollectorStep $outsideRunRootCleanup
  if (-not (Test-Path -LiteralPath (Join-Path $outsideRunRoot 'must-not-delete.txt'))) {
    throw 'State-backed cleanup deleted an outside RunRoot from state.json.'
  }

  $outsidePackagePath = Join-Path $stateCleanupRoot 'outside_package_must_not_delete.zip'
  Set-Content -Path $outsidePackagePath -Value 'outside-package' -Encoding UTF8
  $outsidePackageRunRoot = Join-Path $stateCleanupOutRoot ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, 'state-outside-package')
  [void](Initialize-StateCleanupAuthorityFixture -FixtureOutRoot $stateCleanupOutRoot -FixtureRunId 'state-outside-package' -StateRunRoot $outsidePackageRunRoot -StatePackagePath $outsidePackagePath)
  $outsidePackageCleanup = Invoke-CollectorStep -StepName "98I_StateCleanupRejectsOutsidePackagePath" -CollectorArgs @("-Quick","cleanup","-OutRoot",$stateCleanupOutRoot,"-RunId","state-outside-package")
  Assert-StateCleanupRefused -StepName "98I_StateCleanupRejectsOutsidePackagePath" -CollectorStep $outsidePackageCleanup
  if (-not (Test-Path -LiteralPath $outsidePackagePath)) {
    throw 'State-backed cleanup deleted an outside PackagePath from state.json.'
  }
  if (-not (Test-Path -LiteralPath $outsidePackageRunRoot)) {
    throw 'State-backed cleanup deleted the run root while refusing an outside PackagePath.'
  }

  $mismatchRunId = 'state-mismatch-runroot'
  $mismatchWrongRunRoot = Join-Path $stateCleanupOutRoot ("DCOIR_{0}_{1}_sibling" -f $env:COMPUTERNAME, $mismatchRunId)
  New-Item -Path $mismatchWrongRunRoot -ItemType Directory -Force | Out-Null
  Set-Content -Path (Join-Path $mismatchWrongRunRoot 'must-not-delete.txt') -Value 'mismatch-runroot' -Encoding UTF8
  $mismatchPackagePath = Join-Path $stateCleanupOutRoot 'DCOIR_Collector.zip'
  Set-Content -Path $mismatchPackagePath -Value 'package-placeholder' -Encoding UTF8
  [void](Initialize-StateCleanupAuthorityFixture -FixtureOutRoot $stateCleanupOutRoot -FixtureRunId $mismatchRunId -StateRunRoot $mismatchWrongRunRoot -StatePackagePath $mismatchPackagePath)
  $mismatchCleanup = Invoke-CollectorStep -StepName "98J_StateCleanupRejectsMismatchedRunRoot" -CollectorArgs @("-Quick","cleanup","-OutRoot",$stateCleanupOutRoot,"-RunId",$mismatchRunId)
  Assert-StateCleanupRefused -StepName "98J_StateCleanupRejectsMismatchedRunRoot" -CollectorStep $mismatchCleanup
  if (-not (Test-Path -LiteralPath (Join-Path $mismatchWrongRunRoot 'must-not-delete.txt'))) {
    throw 'State-backed cleanup deleted a mismatched RunRoot from state.json.'
  }

  $outsideStatePath = Join-Path $stateCleanupRoot 'outside_statepath_must_not_delete.json'
  Set-Content -Path $outsideStatePath -Value '{"statepath":"outside"}' -Encoding UTF8
  $outsideStatePathRunId = 'state-outside-statepath'
  $outsideStatePathRunRoot = Join-Path $stateCleanupOutRoot ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $outsideStatePathRunId)
  $outsideStatePathPackage = Join-Path $stateCleanupOutRoot 'DCOIR_Collector.zip'
  Set-Content -Path $outsideStatePathPackage -Value 'package-placeholder' -Encoding UTF8
  [void](Initialize-StateCleanupAuthorityFixture -FixtureOutRoot $stateCleanupOutRoot -FixtureRunId $outsideStatePathRunId -StateRunRoot $outsideStatePathRunRoot -StatePackagePath $outsideStatePathPackage -StatePathOverride $outsideStatePath)
  $outsideStatePathCleanup = Invoke-CollectorStep -StepName "98K_StateCleanupRejectsOutsideStatePath" -CollectorArgs @("-Quick","cleanup","-OutRoot",$stateCleanupOutRoot,"-RunId",$outsideStatePathRunId)
  Assert-StateCleanupRefused -StepName "98K_StateCleanupRejectsOutsideStatePath" -CollectorStep $outsideStatePathCleanup
  if (-not (Test-Path -LiteralPath $outsideStatePath)) {
    throw 'State-backed cleanup deleted an outside StatePath from state.json.'
  }
  if (-not (Test-Path -LiteralPath $outsideStatePathRunRoot)) {
    throw 'State-backed cleanup deleted the run root while refusing an outside StatePath.'
  }

  $selectedRunId = 'state-selected-runid-a'
  $stateRunId = 'state-selected-runid-b'
  $mismatchedRunIdRunRoot = Join-Path $stateCleanupOutRoot ("DCOIR_{0}_{1}" -f $env:COMPUTERNAME, $stateRunId)
  New-Item -Path $mismatchedRunIdRunRoot -ItemType Directory -Force | Out-Null
  Set-Content -Path (Join-Path $mismatchedRunIdRunRoot 'must-not-delete.txt') -Value 'mismatched-state-runid' -Encoding UTF8
  $mismatchedRunIdStatePath = Join-Path $mismatchedRunIdRunRoot 'state.json'
  Set-Content -Path $mismatchedRunIdStatePath -Value '{"state":"mismatched"}' -Encoding UTF8
  $mismatchedRunIdPackage = Join-Path $stateCleanupOutRoot 'DCOIR_Collector.zip'
  Set-Content -Path $mismatchedRunIdPackage -Value 'package-placeholder' -Encoding UTF8
  [void](Initialize-StateCleanupAuthorityFixture -FixtureOutRoot $stateCleanupOutRoot -FixtureRunId $selectedRunId -StateRunRoot $mismatchedRunIdRunRoot -StatePackagePath $mismatchedRunIdPackage -StatePathOverride $mismatchedRunIdStatePath -StateRunIdOverride $stateRunId)
  $mismatchedRunIdCleanup = Invoke-CollectorStep -StepName "98L_StateCleanupRejectsMismatchedRunId" -CollectorArgs @("-Quick","cleanup","-OutRoot",$stateCleanupOutRoot,"-RunId",$selectedRunId)
  Assert-StateCleanupRefused -StepName "98L_StateCleanupRejectsMismatchedRunId" -CollectorStep $mismatchedRunIdCleanup
  if (-not (Test-Path -LiteralPath (Join-Path $mismatchedRunIdRunRoot 'must-not-delete.txt'))) {
    throw 'State-backed cleanup deleted the state RunId run root while refusing a selected RunId mismatch.'
  }
  Remove-Item -LiteralPath $stateCleanupRoot -Recurse -Force -ErrorAction SilentlyContinue

  Restore-WorkingZip -Reason "FailureGates_AfterMissingPackageCleanup"
  $invalidStart = Invoke-CollectorStep -StepName "99_TargetedInvalidWindowStart" -CollectorArgs @("-Quick","collect-targeted-popup","-Target","User reported popup around 2026-04-08T09:00Z","-WindowStart","not-a-date","-WindowEnd","2026-04-08T09:15:00Z")
  Assert-CollectorStepDegradedPartial -StepName "99_TargetedInvalidWindowStart" -CollectorStep $invalidStart -ExpectedPatterns @("Invalid WindowStart value [not-a-date]; falling back to hour-window behavior.")
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedInvalidWindowStartValidation" -CollectStep $invalidStart -ExpectedExplicitEventWindow $false
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "99_CleanupAfterInvalidWindowStart" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "FailureGates_TargetedInvalidWindowEnd"
  $invalidEnd = Invoke-CollectorStep -StepName "100_TargetedInvalidWindowEnd" -CollectorArgs @("-Quick","collect-targeted-popup","-Target","User reported popup around 2026-04-08T09:00Z","-WindowStart","2026-04-08T08:45:00Z","-WindowEnd","not-a-date")
  Assert-CollectorStepDegradedPartial -StepName "100_TargetedInvalidWindowEnd" -CollectorStep $invalidEnd -ExpectedPatterns @("Invalid WindowEnd value [not-a-date]; falling back to hour-window behavior.")
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedInvalidWindowEndValidation" -CollectStep $invalidEnd -ExpectedExplicitEventWindow $false
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "100_CleanupAfterInvalidWindowEnd" -CollectorArgs @("-Quick","cleanup")) }

  Restore-WorkingZip -Reason "FailureGates_TargetedInvertedWindow"
  $invertedWindow = Invoke-CollectorStep -StepName "101_TargetedInvertedWindow" -CollectorArgs @("-Quick","collect-targeted-popup","-Target","User reported popup around 2026-04-08T09:00Z","-WindowStart","2026-04-08T09:15:00Z","-WindowEnd","2026-04-08T08:45:00Z")
  Assert-CollectorStepDegradedPartial -StepName "101_TargetedInvertedWindow" -CollectorStep $invertedWindow -ExpectedPatterns @("is earlier than WindowStart")
  Invoke-TargetedCollectionVerification -StepName "ZZ_TargetedInvertedWindowValidation" -CollectStep $invertedWindow -ExpectedExplicitEventWindow $false
  if (-not $SkipCleanup) { [void](Invoke-CollectorStep -StepName "101_CleanupAfterInvertedWindow" -CollectorArgs @("-Quick","cleanup")) }
}
