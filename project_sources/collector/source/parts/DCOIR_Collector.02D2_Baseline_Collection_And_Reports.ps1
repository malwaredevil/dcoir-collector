<#
.SYNOPSIS
DCOIR collector metadata and report-file writers.

.DESCRIPTION
Builds the post-collect metadata report and writes collector report text to disk.

.FILE NAME
DCOIR_Collector.02D2_Baseline_Collection_And_Reports.ps1

.INPUTS
Collector state, tool-map data, notes, errors, recommendations, runtime settings, and report text.

.OUTPUTS
Metadata report text and written report-file paths.
#>

<#
.SYNOPSIS
Builds the metadata report for a collect run.

.DESCRIPTION
Creates the post-collect metadata report with run-summary paths, tool availability,
notes, errors, recommendations, and analyst workflow guidance.

.FUNCTION NAME
New-MetadataReport

.INPUTS
Collector state hashtable and ToolMap hashtable.

.OUTPUTS
String containing the metadata report text.
#>
function New-MetadataReport {
  param([hashtable]$State,[hashtable]$ToolMap)

  $sb = New-Object System.Text.StringBuilder
  Add-Section -Builder $sb -Name "RUN_SUMMARY" -Text (
    @(
      "CollectorVersion=$ScriptVersion"
      "Mode=Collect"
      "Tier=$Tier"
      "Hours=$Hours"
      "Host=$env:COMPUTERNAME"
      "RunId=$($State.RunId)"
      "TimeLocal=$(Get-Date -Format o)"
      "TimeUTC=$((Get-Date).ToUniversalTime().ToString('o'))"
      "RunRoot=$($State.RunRoot)"
      "BaselineReport=$($State.BaselineReportPath)"
      "MetadataReport=$($State.MetadataReportPath)"
      "ExecutionContext=$($State.ExecutionContextPath)"
      "SecurityAuditPolicy=$($State.SecurityAuditPolicyPath)"
      "AuditPolicyAccessStatus=$($State.AuditPolicyAccessStatus)"
      "SecurityFiltered=$($State.SecurityFilteredPath)"
      "SecurityHighSignalSummary=$($State.SecurityHighSignalSummaryPath)"
      "NetstatOwnerAwareStatus=$($State.NetstatOwnerAwareStatus)"
      "NetstatPidOnlyPath=$($State.NetstatPidOnlyPath)"
      "CollectBundle=$($State.CollectBundlePath)"
      "UploadSummary=$($State.UploadSummaryPath)"
      "AttachmentBudgetManifest=$($State.UploadBudgetManifestPath)"
      "DefaultGeminiUploadSetStatus=$($State.DefaultGeminiUploadSetStatus)"
    ) -join [Environment]::NewLine
  )

  Add-Section -Builder $sb -Name "TOOL_AVAILABILITY" -Text (Get-CommandAvailabilityTable -ToolMap $ToolMap)

  $notesText = @(
    "Cleanup removes the selected run folder and the package zip.",
    "Artifact retrieval is a separate get-file step.",
    "A new Collect run purges prior DCOIR runs before starting.",
    "Follow-on Enrich sessions do not purge the current run.",
    "For Gemini uploads in the current office environment, prefer the upload summary plus representative artifacts over the monolithic baseline report."
  )
  if (@($Global:CollectorNotes).Count -gt 0) {
    $notesText += ""
    $notesText += "Notes:"
    $notesText += $Global:CollectorNotes
  }
  Add-Section -Builder $sb -Name "NOTES" -Text ($notesText -join [Environment]::NewLine)

  $errorsText = if (@($Global:CollectorErrors).Count -gt 0) { $Global:CollectorErrors -join [Environment]::NewLine } else { "No collection errors were recorded." }
  Add-Section -Builder $sb -Name "ERRORS" -Text $errorsText

  $recsText = if (@($Global:RecommendedActions).Count -gt 0) { $Global:RecommendedActions -join [Environment]::NewLine } else { "No enrichment recommendations were generated." }
  Add-Section -Builder $sb -Name "RECOMMENDED_ENRICHMENT_ACTIONS" -Text $recsText

  $workflowText = @(
    "1. Retrieve the collect bundle with get-file.",
    "2. For Gemini uploads, prefer the upload summary, metadata report, manifest, logs, and representative final_artifacts slices.",
    "3. Review the merged baseline locally when the full monolithic report is needed.",
    "4. Run one enrichment action at a time.",
    "5. Continue the same enrichment session or finalize it for ZIP retrieval.",
    "6. Keep the current run until Cleanup is explicitly run."
  ) -join [Environment]::NewLine
  Add-Section -Builder $sb -Name "WORKFLOW" -Text $workflowText

  return $sb.ToString()
}

<#
.SYNOPSIS
Writes one report file to disk.

.DESCRIPTION
Writes the supplied text to the target report path using UTF-8 encoding.

.FUNCTION NAME
Write-ReportFile

.INPUTS
Path string for the output file and Text string to write.

.OUTPUTS
No direct output. Writes the report file as a side effect.
#>
function Write-ReportFile {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([string]$Path,[string]$Text)
  if ($PSCmdlet.ShouldProcess($Path, 'Write collector report file')) {
    Set-Content -Path $Path -Value $Text -Encoding UTF8 -ErrorAction Stop
    return $Path
  }
  return $null
}
