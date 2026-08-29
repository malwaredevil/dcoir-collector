<#
.SYNOPSIS
DCOIR collector late-bound metadata analyst overview helper for issue #212.

.DESCRIPTION
Builds the analyst overview artifact while allowing the final metadata report path to
be populated before the report content itself is finalized.

.FILE NAME
DCOIR_Collector.04H3_PR212_Metadata_Finalization_Fixes.ps1

.INPUTS
Collector state and baseline hashtables.

.OUTPUTS
Analyst overview artifact path.
#>

<#
.SYNOPSIS
Builds the analyst overview while allowing the metadata report path to be late-bound.

.DESCRIPTION
Writes the analyst-first overview artifact and includes METADATA_REPORT_PATH even when
final metadata content has not yet been written, because collect finalization writes that
report immediately after upload and overview paths are populated.

.FUNCTION NAME
New-AnalystOverviewArtifactWithLateMetadataReport

.INPUTS
State hashtable and Baseline hashtable.

.OUTPUTS
String analyst overview artifact path.
#>
function New-AnalystOverviewArtifactWithLateMetadataReport {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([hashtable]$State,[hashtable]$Baseline)

  $artifactMap = $Baseline.ArtifactMap
  $overviewPath = Join-Path $State.ReportsDir ("DCOIR_ANALYST_OVERVIEW_{0}_{1}.txt" -f $env:COMPUTERNAME, $State.RunId)
  $lines = New-Object System.Collections.ArrayList

  [void]$lines.Add("DCOIR_ANALYST_OVERVIEW")
  [void]$lines.Add(("CollectorVersion={0}" -f $ScriptVersion))
  [void]$lines.Add(("RunId={0}" -f $State.RunId))
  [void]$lines.Add("WorkflowPhase=CollectBaseline")
  [void]$lines.Add("PrimaryReviewPosture=SmallerSurfaceFirst")
  [void]$lines.Add("DoNotAssumeMonolithicBaselineUpload=true")
  [void]$lines.Add("MergedBaselineReportEmitted=false")
  [void]$lines.Add(("DefaultGeminiUploadSetStatus={0}" -f $State.DefaultGeminiUploadSetStatus))
  [void]$lines.Add(("CollectTier={0}" -f $Tier))
  $collectorErrorCount = @($Global:CollectorErrors).Count
  [void]$lines.Add(("CollectorObservedErrorCount={0}" -f $collectorErrorCount))
  if ($collectorErrorCount -gt 0) {
    [void]$lines.Add('RunHealth=DEGRADED_OR_PARTIAL_REVIEW_REQUIRED')
  } else {
    [void]$lines.Add('RunHealth=NO_DEGRADED_STATE_OBSERVED_DURING_COLLECTION')
  }
  [void]$lines.Add("")
  [void]$lines.Add("WHAT_TO_REVIEW_FIRST")
  [void]$lines.Add("1. Start with this overview, the upload summary, and the metadata report.")
  [void]$lines.Add("2. Use the analyst follow-up queue and security high-signal summary as the first decisive triage surface.")
  [void]$lines.Add("3. Use representative process, network, and defender artifacts before expanding into broader local review.")
  if ($collectorErrorCount -gt 0) {
    [void]$lines.Add("4. This run recorded collector errors during collection. Review errors.log and the affected truth surfaces before treating the overview as complete.")
  }
  if ($State.TargetedCollectionPlanPath) {
    [void]$lines.Add("4. A targeted collection plan was emitted for this run; review it first when the incident is narrow.")
  }
  [void]$lines.Add("")
  [void]$lines.Add("REVIEW_FIRST_PATHS")
  foreach ($pair in @(
    @{ Label = 'ANALYST_OVERVIEW_PATH'; Path = $overviewPath },
    @{ Label = 'UPLOAD_SUMMARY_PATH'; Path = $State.UploadSummaryPath },
    @{ Label = 'METADATA_REPORT_PATH'; Path = $State.MetadataReportPath },
    @{ Label = 'ATTACHMENT_BUDGET_MANIFEST_PATH'; Path = $State.UploadBudgetManifestPath },
    @{ Label = 'COLLECTION_SCOPE_PATH'; Path = $State.CollectionScopePath },
    @{ Label = 'TARGETED_COLLECTION_PLAN_PATH'; Path = $State.TargetedCollectionPlanPath },
    @{ Label = 'ANALYST_FOLLOW_UP_QUEUE_PATH'; Path = $artifactMap['analyst_follow_up_queue'] },
    @{ Label = 'SECURITY_HIGH_SIGNAL_SUMMARY_PATH'; Path = $artifactMap['security_high_signal_summary'] },
    @{ Label = 'PROCESS_INVENTORY_PATH'; Path = $artifactMap['process_inventory'] },
    @{ Label = 'STRUCTURED_NET_PATH'; Path = $artifactMap['structured_net'] },
    @{ Label = 'DEFENDER_STATUS_PATH'; Path = $artifactMap['defender_status'] }
  )) {
    $includePath = $false
    if ($pair.Path) {
      $includePath = (($pair.Label -eq 'METADATA_REPORT_PATH') -or (Test-Path -LiteralPath $pair.Path))
    }
    if ($includePath) {
      [void]$lines.Add(("{0}={1}" -f $pair.Label, $pair.Path))
    }
  }
  [void]$lines.Add("")
  if ($collectorErrorCount -gt 0) {
    [void]$lines.Add("DEGRADED_REVIEW_NOTE")
    [void]$lines.Add("This run emitted collector errors during collection. Use errors.log plus the specific affected artifacts as the truth surface for degraded lanes.")
    [void]$lines.Add("")
  }
  [void]$lines.Add("NO_MERGED_BASELINE_REPORT")
  [void]$lines.Add("No merged baseline report is emitted in this build. Use metadata plus representative artifacts for broader local review.")

  if ($PSCmdlet.ShouldProcess($overviewPath, 'Write analyst overview artifact')) {
    Set-Content -Path $overviewPath -Value $lines -Encoding UTF8 -ErrorAction Stop
    return $overviewPath
  }
  return $null
}
