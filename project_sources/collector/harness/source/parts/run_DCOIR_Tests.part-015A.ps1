<#
.SYNOPSIS
Validates literal-path handling for enrich session artifact filenames.

.DESCRIPTION
Runs a bounded collector flow with a bracket-bearing source path. The retrieval action
uses the source path as its session-artifact target label, so the resulting artifact
filename also contains square brackets. The regression verifies that the collector
returns an artifact path containing the brackets and that the file exists when tested
with literal-path semantics.

.FUNCTION NAME
Run-SessionArtifactLiteralPathRegression

.INPUTS
No direct parameters.

.OUTPUTS
No direct output. Executes collector steps and records a harness PASS/FAIL result.
#>
function Run-SessionArtifactLiteralPathRegression {
  Restore-WorkingZip -Reason "SessionArtifactLiteralPath"

  $collect = Invoke-CollectorStep -StepName "ZZ_LiteralPath_CollectT1" -CollectorArgs @("-Quick","collect-t1")
  Assert-CollectorStepSucceeded -StepName "ZZ_LiteralPath_CollectT1" -CollectorStep $collect

  $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("[dcoir_literal_{0}]" -f ([guid]::NewGuid().ToString("N").Substring(0,8)))
  $sourcePath = Join-Path $tempRoot "sample_[artifact].ps1"

  try {
    [void][System.IO.Directory]::CreateDirectory($tempRoot)
    [System.IO.File]::WriteAllText($sourcePath, "Write-Output 'literal path regression'", [System.Text.Encoding]::UTF8)

    $pullStep = Invoke-CollectorStep -StepName "ZZ_LiteralPath_PullScript" -CollectorArgs @(
      "-Mode","Enrich",
      "-RunId",$script:CollectorRunId,
      "-NewEnrichSession",
      "-Action","PullScriptOrConfig",
      "-Path",$sourcePath
    )
    Assert-CollectorStepSucceeded -StepName "ZZ_LiteralPath_PullScript" -CollectorStep $pullStep

    $verificationStep = "ZZ_SessionArtifactLiteralPath"
    $verificationStart = Get-Date
    $artifactPath = Parse-OutputValue -Text $pullStep.StdOut -Key "ACTION_ARTIFACT_PATH"
    $hasArtifactPath = -not [string]::IsNullOrWhiteSpace($artifactPath)
    $preservedBracket = $hasArtifactPath -and $artifactPath.Contains('[') -and $artifactPath.Contains(']')
    $artifactExists = $hasArtifactPath -and (Test-Path -LiteralPath $artifactPath)
    $status = if ($hasArtifactPath -and $preservedBracket -and $artifactExists) { "PASS" } else { "FAIL" }
    $verificationEnd = Get-Date
    $logPath = Write-HarnessLog -StepName $verificationStep -Lines @(
      "STEP=$verificationStep",
      "STATUS=$status",
      "SOURCE_PATH=$sourcePath",
      "ACTION_ARTIFACT_PATH=$artifactPath",
      "HAS_ARTIFACT_PATH=$hasArtifactPath",
      "PRESERVED_BRACKET=$preservedBracket",
      "ARTIFACT_EXISTS_LITERAL=$artifactExists"
    )
    Add-Result -StepName $verificationStep -Status $status -ExitCode $(if ($status -eq "PASS") { 0 } else { 1 }) -RunId $script:CollectorRunId -EnrichSessionId $pullStep.EnrichSessionId -CollectorReportedStatus $pullStep.CollectorReportedStatus -LogPath $logPath -Start $verificationStart -End $verificationEnd

    if ($status -ne "PASS") {
      throw ("Session artifact literal-path regression failed. ArtifactPath=[{0}] PreservedBracket={1} ExistsLiteral={2}" -f $artifactPath, $preservedBracket, $artifactExists)
    }

    $finalize = Invoke-CollectorStep -StepName "ZZ_LiteralPath_Finalize" -CollectorArgs @("-Quick","enrich-finalize")
    Assert-CollectorStepSucceeded -StepName "ZZ_LiteralPath_Finalize" -CollectorStep $finalize

    if (-not $SkipCleanup) {
      $cleanup = Invoke-CollectorStep -StepName "ZZ_LiteralPath_Cleanup" -CollectorArgs @("-Quick","cleanup")
      Assert-CollectorStepSucceeded -StepName "ZZ_LiteralPath_Cleanup" -CollectorStep $cleanup
    }
  } finally {
    if ([System.IO.Directory]::Exists($tempRoot)) {
      try { [System.IO.Directory]::Delete($tempRoot, $true) } catch { }
    }
  }
}
