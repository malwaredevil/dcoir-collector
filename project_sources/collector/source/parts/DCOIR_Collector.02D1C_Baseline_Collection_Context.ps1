<#
.SYNOPSIS
DCOIR baseline collection context and limitation reporting.

.DESCRIPTION
Writes collection metadata, execution context, audit policy, and analyst-facing limitation artifacts before baseline evidence collection begins.

.FILE NAME
DCOIR_Collector.02D1C_Baseline_Collection_Context.ps1
#>

function Add-BaselineCollectionContext {
  [CmdletBinding()]
  param(
    [hashtable]$State,
    [System.Collections.ArrayList]$ArtifactPaths,
    [hashtable]$ArtifactMap,
    [System.Text.StringBuilder]$Builder,
    [bool]$IsElevated
  )

  $sb = $Builder
  $isElevated = $IsElevated
  if (-not $isElevated) {
    Add-CollectorNote 'Collector is running in a non-elevated context. Owner-aware netstat capture and Security log visibility may be restricted on this host.'
  }

  $metaText = @(
    "CollectorVersion=$ScriptVersion"
    "Mode=Collect"
    "Tier=$Tier"
    "Hours=$Hours"
    "MaxEvents=$MaxEvents"
    "Host=$env:COMPUTERNAME"
    "RunId=$($State.RunId)"
    "UserContext=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
    "IsElevated=$isElevated"
    "TimeLocal=$(Get-Date -Format o)"
    "TimeUTC=$((Get-Date).ToUniversalTime().ToString('o'))"
    "RunRoot=$($State.RunRoot)"
    "ReportsDir=$($State.ReportsDir)"
    "ArtifactsDir=$($State.ArtifactsDir)"
    "EnrichSessionsDir=$($State.EnrichSessionsDir)"
  ) -join [Environment]::NewLine
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "COLLECTION_METADATA" -Name "collection_metadata.txt" -Text $metaText
  [void]$artifactPaths.Add($p); $artifactMap['collection_metadata'] = $p
  Add-Section -Builder $sb -Name "COLLECTION_METADATA" -Text $metaText

  $executionContextText = Get-CollectorExecutionContextText
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "COLLECTION_METADATA" -Name "execution_context.txt" -Text $executionContextText
  [void]$artifactPaths.Add($p); $artifactMap['execution_context'] = $p; $State.ExecutionContextPath = $p; $State.IsElevated = $isElevated

  $script:CollectorAuditPolicyAccessStatus = 'UNKNOWN'
  $auditPolicyText = Get-SecurityAuditPolicyText
  $State.AuditPolicyAccessStatus = if ($script:CollectorAuditPolicyAccessStatus) { [string]$script:CollectorAuditPolicyAccessStatus } else { 'UNKNOWN' }
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "COLLECTION_METADATA" -Name "security_audit_policy.txt" -Text $auditPolicyText
  [void]$artifactPaths.Add($p); $artifactMap['security_audit_policy'] = $p; $State.SecurityAuditPolicyPath = $p
  Add-Section -Builder $sb -Name "EXECUTION_CONTEXT_AND_AUDIT_POLICY" -Text (@($executionContextText, '', ('AUDIT_POLICY_ACCESS_STATUS={0}' -f $State.AuditPolicyAccessStatus), '', $auditPolicyText) -join [Environment]::NewLine)

  $limitationLines = @(
    "Offline profile hives were not loaded by design.",
    "Only loaded HKU user Run keys were collected.",
    "Raw EVTX files are not part of baseline collection. Log text is exported for baseline review.",
    "Current run files remain in place until Cleanup runs.",
    "A new Collect run purges prior DCOIR run folders and the prior package zip.",
    "The merged baseline report remains useful for local analyst review, but it is no longer the default Gemini-facing upload surface. Prefer the upload summary and representative artifacts."
  )
  if (@($Global:CollectorNotes).Count -gt 0) {
    $limitationLines += ""
    $limitationLines += "Collection notes:"
    $limitationLines += $Global:CollectorNotes
  }
  if (@($Global:CollectorErrors).Count -gt 0) {
    $limitationLines += ""
    $limitationLines += "Collection errors seen so far:"
    $limitationLines += $Global:CollectorErrors
  }
  $limitationText = ($limitationLines -join [Environment]::NewLine)
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "COLLECTION_NOTES_AND_LIMITATIONS" -Name "collection_notes_and_limitations.txt" -Text $limitationText
  [void]$artifactPaths.Add($p); $artifactMap['collection_notes_and_limitations'] = $p
  Add-Section -Builder $sb -Name "COLLECTION_NOTES_AND_LIMITATIONS" -Text $limitationText
}
# DCOIR_REVIEW_AUDIT_BATCH_2B_MARKER
