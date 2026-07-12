<#
.SYNOPSIS
DCOIR collector targeted-collection and feature-wave helper functions.

.DESCRIPTION
Builds the targeted-collection scope and analyst plan artifacts, emits the bounded
parallelism assessment, and creates synthetic chunk-validation artifacts used by the
feature-wave collection and upload-surface regression paths.

.FILE NAME
DCOIR_Collector.04B1_Feature_Wave_Targeted_Collection.ps1

.INPUTS
Collector state and baseline hashtables, targeted-collection globals such as
WindowStart, WindowEnd, FocusProcess, FocusPath, FocusIndicator, UserReport,
IncludeArtifactCategory, Hours, and validation-specific synthetic chunking settings.

.OUTPUTS
Ordered scope objects, analyst-facing text artifacts, chunk-manifest data, and updates
to the baseline artifact map and report builder.
#>

<#
.SYNOPSIS
Builds the targeted collection scope text artifact.

.DESCRIPTION
Converts the normalized targeted scope object into an analyst-facing text artifact.

.FUNCTION NAME
Get-TargetedCollectionScopeText

.INPUTS
Scope hashtable.

.OUTPUTS
String targeted collection scope text.
#>
function Get-TargetedCollectionScopeText {
  param([hashtable]$Scope)

  $lines = @()
  $lines += "TARGETED_COLLECTION_SCOPE"
  $lines += ("TARGETED_MODE_ENABLED={0}" -f $Scope.targeted_mode_enabled)
  $lines += ("TARGET_PROFILE={0}" -f $Scope.target_profile)
  $lines += ("HAS_EXPLICIT_TIME_WINDOW={0}" -f $Scope.has_explicit_time_window)
  $lines += ("WINDOW_START={0}" -f $Scope.window_start)
  $lines += ("WINDOW_END={0}" -f $Scope.window_end)
  $lines += ("REQUESTED_HOURS={0}" -f $Scope.requested_hours)
  $lines += ("FOCUS_PROCESS={0}" -f $Scope.focus_process)
  $lines += ("FOCUS_PATH={0}" -f $Scope.focus_path)
  $lines += ("FOCUS_INDICATOR={0}" -f $Scope.focus_indicator)
  $lines += ("FOCUS_INDICATOR_TYPE={0}" -f $Scope.focus_indicator_type)
  $lines += ("USER_REPORT={0}" -f $Scope.user_report)
  $lines += ("INCLUDED_ARTIFACT_CATEGORIES={0}" -f (($Scope.included_artifact_categories | ForEach-Object { $_ }) -join ', '))
  $lines += ""
  $lines += "IMPLEMENTATION_BOUNDARY"
  $lines += $Scope.implementation_boundary
  return ($lines -join [Environment]::NewLine)
}

<#
.SYNOPSIS
Builds the targeted collection plan text artifact.

.DESCRIPTION
Returns the analyst-facing plan that prioritizes evidence and review order for the
current targeted profile and focus context.

.FUNCTION NAME
Get-TargetedCollectionPlanText

.INPUTS
Scope hashtable.

.OUTPUTS
String targeted collection plan text.
#>
function Get-TargetedCollectionPlanText {
  param([hashtable]$Scope)

  $lines = @()
  $lines += "TARGETED_COLLECTION_PLAN"
  $lines += ("PROFILE={0}" -f $Scope.target_profile)
  $lines += ""
  $lines += "INTENDED USE"
  $lines += "- This report turns the targeted collection request into explicit analyst-facing scoping guidance."
  $lines += "- It is intended to explain what the collector should emphasize, what the analyst should upload first, and which evidence families should be treated as highest value."
  $lines += "- It is intentionally explicit because narrow incidents such as a user-reported popup, a suspected script execution, or a suspicious process often need a smaller and more explainable collection path than a generic broad baseline."
  $lines += ""
  $lines += "PRIORITIZED EVIDENCE"
  switch ($Scope.target_profile) {
    "PopupWindow" {
      $lines += "1. Security high-signal events around the reported time window."
      $lines += "2. Process inventory and likely user-context process chains."
      $lines += "3. PowerShell operational events and scheduled task activity."
      $lines += "4. Representative artifacts tied to likely GUI-launching processes, startup points, or scripts."
    }
    "ScriptExecution" {
      $lines += "1. PowerShell operational events and Security 4688 process creation records."
      $lines += "2. Process inventory entries with suspicious command lines or user-writable execution paths."
      $lines += "3. Pulled script, config, or suspicious file artifacts if specific paths are known."
      $lines += "4. Strings, streams, or signature enrichment on the focal script or binary path."
    }
    "PersistenceFollowUp" {
      $lines += "1. Services, scheduled tasks, Run keys, and autoruns."
      $lines += "2. WMI persistence text and service binary follow-up."
      $lines += "3. Registry, service ACL, and task XML follow-up actions."
      $lines += "4. Representative retrieved artifacts for persistence evidence."
    }
    "NetworkOnly" {
      $lines += "1. Structured network state, netstat, tcpvcon, dns cache, route, and arp."
      $lines += "2. Security events that establish the launching process or account context."
      $lines += "3. Follow-up TCP refresh enrichment."
      $lines += "4. Representative network-facing process inventory slices."
    }
    "ProcessAndPowerShell" {
      $lines += "1. Process inventory, pslist, Security 4688, and PowerShell operational records."
      $lines += "2. Signature, strings, and stream checks for focal binaries or scripts."
      $lines += "3. Retrieval of suspicious script or config paths when known."
      $lines += "4. Repeatable enrichment of process-centric context in one bounded session."
    }
    default {
      $lines += "1. Metadata, upload summary, analyst follow-up queue, and security high-signal summary."
      $lines += "2. One or more focal process, script, or network artifacts if a likely target is known."
      $lines += "3. Narrow enrichment tied to the strongest current lead."
      $lines += "4. Avoid defaulting to oversized merged review artifacts when smaller decisive artifacts are sufficient."
    }
  }
  $lines += ""
  $lines += "ANALYST NOTES"
  if (-not [string]::IsNullOrWhiteSpace($Scope.user_report)) {
    $lines += ("- User report: {0}" -f $Scope.user_report)
  } else {
    $lines += "- No free-text user report was supplied."
  }
  if ($Scope.has_explicit_time_window) {
    $lines += ("- Explicit time window requested: {0} to {1}" -f $Scope.window_start, $Scope.window_end)
  } else {
    $lines += "- No explicit start-end time window was supplied. The collector remains hour-window based in this version."
  }
  if ($Scope.has_focus_context) {
    $lines += "- Focus context was supplied and should influence the first analyst review pass."
  } else {
    $lines += "- No narrow focal artifact was supplied; use the target profile plus the analyst follow-up queue to choose the first review artifact."
  }
  return ($lines -join [Environment]::NewLine)
}

<#
.SYNOPSIS
Builds the bounded parallelism assessment text.

.DESCRIPTION
Returns the analyst-facing explanation of the currently implemented bounded runtime
parallelism posture and its validation expectations.

.FUNCTION NAME
Get-CollectorParallelismAssessmentText

.INPUTS
No direct parameters.

.OUTPUTS
String parallelism assessment text.
#>
function Get-CollectorParallelismAssessmentText {
  $lines = @()
  $lines += "COLLECTOR_PARALLELISM_ASSESSMENT"
  $lines += "STATUS=BOUNDED_RUNTIME_IMPLEMENTED"
  $lines += ""
  $lines += "CURRENT POSITION"
  $lines += "- The collector now performs bounded PowerShell 5.1-safe parallel runtime execution for selected read-only baseline worker groups."
  $lines += "- The implemented worker set is intentionally narrow and preserves deterministic final report assembly."
  $lines += "- The collector still emits a durable parallel execution proof surface so overlap and worker completion can be validated on a real Collect run."
  $lines += ""
  $lines += "IMPLEMENTED WORKER GROUPS"
  $lines += "1. Host baseline worker for time/hostname/version and systeminfo capture."
  $lines += "2. Identity context worker for whoami and interactive session capture."
  $lines += "3. Network light worker for ipconfig, DNS cache, route, and ARP capture."
  $lines += "4. Security posture worker for firewall profile capture."
  $lines += ""
  $lines += "SAFETY GUARDRAILS"
  $lines += "1. Each worker writes its own durable artifact under final_artifacts\parallel_workers."
  $lines += "2. The parent waits for all workers to finish before continuing deterministic report assembly."
  $lines += "3. Steps not successfully cached by a worker fall back to serial execution when needed."
  $lines += ""
  $lines += "STILL SERIAL"
  $lines += "- Process inventory, event timeline collection, persistence sections, Sysinternals-enriched captures, and bundle/manifest finalization remain serial in this bounded implementation slice."
  $lines += ""
  $lines += "VALIDATION EXPECTATION"
  $lines += "- Use the emitted parallel execution proof artifact and worker files to verify overlapping runtime and deterministic output before claiming the broader issue closed."
  return ($lines -join [Environment]::NewLine)
}

<#
.SYNOPSIS
Builds the analyst overview artifact.

.DESCRIPTION
Writes the analyst-first overview artifact that points review toward metadata, upload
summary, high-signal artifacts, and any targeted plan emitted for the run.

.FUNCTION NAME
New-AnalystOverviewArtifact

.INPUTS
State hashtable and Baseline hashtable.

.OUTPUTS
String analyst overview artifact path.
#>
function New-AnalystOverviewArtifact {
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
    [void]$lines.Add("4. This run recorded degraded or partial conditions. Review errors.log and the affected truth surfaces before treating the overview as complete.")
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
    if ($pair.Path -and (Test-Path -LiteralPath $pair.Path)) {
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
