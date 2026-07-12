<#
.SYNOPSIS
DCOIR collector baseline execution-context, network, and upload-summary helpers.

.DESCRIPTION
Builds safe JSON artifact text, determines elevation and execution context, captures netstat surfaces, and writes the collect upload summary plus attachment-budget manifest.

.FILE NAME
DCOIR_Collector.02B_Baseline_Collection_And_Reports.ps1

.INPUTS
Collector state, baseline artifact maps, tool output, and current runtime context.

.OUTPUTS
Execution-context, network-capture, upload-summary, and attachment-budget helper return values and artifacts.
#>

<#
.SYNOPSIS
Converts one object into safe JSON text for artifact writing.

.DESCRIPTION
Serializes the supplied object with a high JSON depth and appends a trailing newline so
artifact JSON text files remain stable and readable.

.FUNCTION NAME
Convert-ToSafeJsonText

.INPUTS
InputObject to serialize.

.OUTPUTS
String containing newline-terminated JSON text.
#>
function Convert-ToSafeJsonText {
  param([object]$InputObject)
  return (Convert-ToCollectorJsonText -InputObject $InputObject -Label 'safe JSON artifact' -AppendNewline -ThrowOnTruncation)
}

<#
.SYNOPSIS
Determines whether the current collector context is elevated.

.DESCRIPTION
Queries the current Windows identity and returns true when the current principal is in
the local Administrators role. Returns false on any lookup error.

.FUNCTION NAME
Test-CollectorIsElevated

.INPUTS
No direct parameters.

.OUTPUTS
Boolean indicating whether the current collector context is elevated.
#>
function Test-CollectorIsElevated {
  try {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
  } catch {
    return $false
  }
}

<#
.SYNOPSIS
Builds the execution-context text artifact.

.DESCRIPTION
Collects the current user, elevation state, host, process, PowerShell version, and
working-directory context, then adds a short diagnostic note describing the expected
visibility posture for elevated versus non-elevated collection.

.FUNCTION NAME
Get-CollectorExecutionContextText

.INPUTS
No direct parameters.

.OUTPUTS
String containing the execution-context text artifact.
#>
function Get-CollectorExecutionContextText {
  $isElevated = Test-CollectorIsElevated
  $identityName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $lines = @(
    'EXECUTION_CONTEXT',
    ("UserContext={0}" -f $identityName),
    ("IsElevated={0}" -f $isElevated),
    ("Host={0}" -f $env:COMPUTERNAME),
    ("ProcessId={0}" -f $PID),
    ("PowerShellVersion={0}" -f $PSVersionTable.PSVersion),
    ("CurrentDirectory={0}" -f (Get-Location).Path)
  )
  if ($isElevated) {
    $lines += 'DiagnosticContext=Elevated execution should allow owner-aware netstat capture and broader Security log visibility when audit policy supports it.'
  } else {
    $lines += 'DiagnosticContext=Non-elevated execution can restrict owner-aware netstat capture and Security log visibility on some hosts.'
  }
  return ($lines -join [Environment]::NewLine)
}

<#
.SYNOPSIS
Builds the netstat capture bundle for the current run.

.DESCRIPTION
Attempts owner-aware netstat capture first, classifies elevation-required or other
failure modes, optionally captures a PID-only supplemental netstat surface, and returns
both text surfaces plus the owner-aware capture status.

.FUNCTION NAME
Get-NetstatCaptureBundle

.INPUTS
IsElevated boolean describing the current collector context.

.OUTPUTS
Hashtable containing owner-aware text, owner-aware status, owner-aware exit code, and
optional PID-only text.
#>
function Get-NetstatCaptureBundle {
  param([bool]$IsElevated)

  $ownerAwareResult = Invoke-CmdCapture -Command 'netstat -abno' -StepName 'NETWORK_NETSTAT_OWNER_AWARE' -AllowedExitCodes @(0,1)
  $ownerAwareText = Get-CombinedProcessOutput -Result $ownerAwareResult
  $combinedOutput = (([string]$ownerAwareResult.StdOut) + ' ' + ([string]$ownerAwareResult.StdErr)).Trim()
  $requiresElevation = ($ownerAwareResult.ExitCode -ne 0) -and ($combinedOutput -match '(?i)requires elevation')

  $pidOnlyResult = $null
  $pidOnlyText = $null
  $status = 'OWNER_AWARE_OK'

  if ($requiresElevation) {
    $status = 'OWNER_AWARE_REQUIRES_ELEVATION'
    Add-CollectorNote 'Owner-aware netstat capture (netstat -abno) requires elevation in the current execution context. A supplemental PID-only netstat capture was collected separately, but executable ownership attribution remains unavailable until an elevated run.'
    $pidOnlyResult = Invoke-CmdCapture -Command 'netstat -ano' -StepName 'NETWORK_NETSTAT_PID_ONLY' -AllowedExitCodes @(0)
    $pidOnlyText = Get-CombinedProcessOutput -Result $pidOnlyResult
  } elseif ($ownerAwareResult.ExitCode -ne 0) {
    $status = 'OWNER_AWARE_FAILED'
    Add-CollectorError ('Owner-aware netstat capture (netstat -abno) failed for a reason other than missing elevation. Review the artifact for the exact command output. ExitCode={0}' -f $ownerAwareResult.ExitCode)
  }

  return @{
    OwnerAwareText = $ownerAwareText
    OwnerAwareStatus = $status
    OwnerAwareExitCode = [int]$ownerAwareResult.ExitCode
    PidOnlyText = $pidOnlyText
  }
}

<#
.SYNOPSIS
Creates the collect upload summary and attachment-budget manifest.

.DESCRIPTION
Selects the default analyst-first Gemini upload set, evaluates it against the safe and
hard environment budgets, writes the upload summary text and JSON manifest, and returns
the key status values to the caller.

.FUNCTION NAME
New-CollectUploadArtifacts

.INPUTS
Collector state hashtable and baseline result hashtable containing the artifact map.

.OUTPUTS
Hashtable containing upload-summary path, manifest path, default-set status, total KB,
and recommended file count.
#>
function New-CollectUploadArtifacts {
  [CmdletBinding(SupportsShouldProcess=$true)]
  param([hashtable]$State,[hashtable]$Baseline)

  $budget = Get-CollectorUploadBudget
  $artifactMap = $Baseline.ArtifactMap
  $chunkCompanions = New-ProductionUploadSafeChunkCompanions -State $State -ArtifactMap $artifactMap -Budget $budget
  $recommendedPaths = @()

  foreach ($key in @(
    'collection_metadata',
    'collection_notes_and_limitations',
    'security_high_signal_summary',
    'process_inventory',
    'structured_net',
    'defender_status',
    'analyst_follow_up_queue'
  )) {
    $candidatePath = if ($artifactMap.ContainsKey($key)) { [string]$artifactMap[$key] } else { $null }
    if (-not [string]::IsNullOrWhiteSpace($candidatePath) -and (Test-Path -LiteralPath $candidatePath)) {
      $recommendedPaths += $candidatePath
    }
  }

  if ($State.MetadataReportPath -and (Test-Path -LiteralPath $State.MetadataReportPath)) {
    $recommendedPaths = @($State.MetadataReportPath) + $recommendedPaths
  }

  $recommended = New-Object System.Collections.ArrayList
  $safeTotal = 0
  foreach ($path in $recommendedPaths) {
    $sizeKB = Get-FileSizeKB -Path $path
    $safeTotal += $sizeKB
    [void]$recommended.Add([ordered]@{
      path = $path
      relative_path = [string](Resolve-Path -LiteralPath $path | ForEach-Object { $_.Path.Replace($State.RunRoot + '\\', '') })
      size_kb = $sizeKB
      within_safe_per_file = ($sizeKB -le $budget.SafePerFileKB)
      within_hard_per_file = ($sizeKB -le $budget.HardPerFileKB)
    })
  }

  $setStatus = if (($safeTotal -le $budget.SafeTotalKB) -and (@($recommended | Where-Object { -not $_.within_safe_per_file }).Count -eq 0)) {
    'SAFE_DEFAULT_SET'
  } elseif (($safeTotal -le $budget.HardTotalKB) -and (@($recommended | Where-Object { -not $_.within_hard_per_file }).Count -eq 0)) {
    'HARD_LIMIT_ONLY'
  } else {
    'EXCEEDS_ENVIRONMENT_BUDGET'
  }

  $uploadSummaryPath = Join-Path $State.ReportsDir ("DCOIR_UPLOAD_SUMMARY_{0}_{1}.txt" -f $env:COMPUTERNAME, $State.RunId)
  $uploadManifestPath = Join-Path $State.ReportsDir ("DCOIR_ATTACHMENT_BUDGET_MANIFEST_{0}_{1}.json.txt" -f $env:COMPUTERNAME, $State.RunId)
  $chunkManifestPath = $null
  if (@($chunkCompanions).Count -gt 0) {
    $plannedChunkManifestPath = Join-Path $State.ReportsDir ("DCOIR_UPLOAD_SAFE_CHUNK_MANIFEST_{0}_{1}.json.txt" -f $env:COMPUTERNAME, $State.RunId)
    $chunkManifestObj = [ordered]@{
      run_id = $State.RunId
      origin = 'collector_production_upload_safe'
      budget = $budget
      chunked_artifact_count = @($chunkCompanions).Count
      chunked_artifacts = @($chunkCompanions)
    }
    if ($PSCmdlet.ShouldProcess($plannedChunkManifestPath, 'Write upload-safe chunk manifest')) {
      Set-Content -Path $plannedChunkManifestPath -Value (Convert-ToSafeJsonText -InputObject $chunkManifestObj) -Encoding UTF8 -ErrorAction Stop
      $chunkManifestPath = $plannedChunkManifestPath
      $State.UploadSafeChunkManifestPath = $chunkManifestPath
      $Baseline.ArtifactMap['upload_safe_chunk_manifest'] = $chunkManifestPath
      [void]$Baseline.ArtifactPaths.Add($chunkManifestPath)
      foreach ($chunkRow in @($chunkCompanions)) {
        foreach ($chunkPath in @($chunkRow.chunk_paths)) {
          [void]$Baseline.ArtifactPaths.Add($chunkPath)
        }
      }
    }
  }

  $summaryLines = @(
    "CollectorVersion=$ScriptVersion",
    "RunId=$($State.RunId)",
    "WorkflowPhase=CollectBaseline",
    "UploadModel=ChunkFirst",
    "DoNotAssumeMonolithicBaselineUpload=true",
    "HardPerFileKB=$($budget.HardPerFileKB)",
    "HardTotalKB=$($budget.HardTotalKB)",
    "SafePerFileKB=$($budget.SafePerFileKB)",
    "SafeTotalKB=$($budget.SafeTotalKB)",
    "DefaultSetStatus=$setStatus",
    "RecommendedUploadTotalKB=$safeTotal",
    "",
    "Recommended files for Gemini upload by default:"
  )
  foreach ($row in $recommended) {
    $summaryLines += ('- {0} [{1} KB]' -f $row.path, $row.size_kb)
  }
  $summaryLines += ""
  $summaryLines += "Default guidance:"
  $summaryLines += "- Prefer this upload summary, the metadata report, and the listed representative artifacts."
  $summaryLines += "- Do not assume the large merged baseline report is upload-safe in the office Gemini environment."
  $summaryLines += "- If this set must be trimmed further, keep metadata, follow-up queue, security high-signal summary, and one representative process/network artifact first."
  if (@($chunkCompanions).Count -gt 0) {
    $summaryLines += ""
    $summaryLines += "Upload-safe chunk companions:"
    if ($chunkManifestPath) {
      $summaryLines += ("- UPLOAD_SAFE_CHUNK_MANIFEST_PATH={0}" -f $chunkManifestPath)
    }
    foreach ($chunkRow in @($chunkCompanions)) {
      $summaryLines += ("- SourceKey={0} SourceSizeKB={1} ChunkCount={2} TargetChunkKB={3}" -f $chunkRow.source_artifact_key, $chunkRow.source_size_kb, $chunkRow.chunk_count, $chunkRow.target_chunk_kb)
      foreach ($chunkPath in @($chunkRow.chunk_paths)) {
        $summaryLines += ("  - {0}" -f $chunkPath)
      }
    }
    $summaryLines += "- Upload the high-signal summary first for triage; use full-fidelity chunk companions when the oversized source artifact is needed."
  }

  $uploadSummaryResultPath = $null
  if ($PSCmdlet.ShouldProcess($uploadSummaryPath, 'Write collect upload summary')) {
    Set-Content -Path $uploadSummaryPath -Value $summaryLines -Encoding UTF8 -ErrorAction Stop
    $uploadSummaryResultPath = $uploadSummaryPath
  }

  $manifestObj = [ordered]@{
    run_id = $State.RunId
    workflow_phase = 'collect_baseline'
    upload_model = 'chunk_first'
    budget = $budget
    default_set_status = $setStatus
    recommended_upload_total_kb = $safeTotal
    recommended_upload_files = @($recommended)
    upload_safe_chunk_manifest_path = $chunkManifestPath
    upload_safe_chunk_companions = @($chunkCompanions)
    baseline_report_path = $State.BaselineReportPath
    metadata_report_path = $State.MetadataReportPath
    note = 'The merged baseline report may be useful for local analyst review but is no longer the default Gemini-facing upload surface.'
  }
  $uploadManifestResultPath = $null
  if ($PSCmdlet.ShouldProcess($uploadManifestPath, 'Write attachment budget manifest')) {
    Set-Content -Path $uploadManifestPath -Value (Convert-ToSafeJsonText -InputObject $manifestObj) -Encoding UTF8 -ErrorAction Stop
    $uploadManifestResultPath = $uploadManifestPath
  }

  return @{
    UploadSummaryPath = $uploadSummaryResultPath
    UploadManifestPath = $uploadManifestResultPath
    DefaultSetStatus = $setStatus
    RecommendedUploadTotalKB = $safeTotal
    RecommendedUploadCount = @($recommended).Count
    UploadSafeChunkManifestPath = $chunkManifestPath
    UploadSafeChunkCompanionCount = @($chunkCompanions).Count
  }
}
