<#
.SYNOPSIS
Verifies the open enrich-session output contract fields.

.DESCRIPTION
Checks that an enrich-start style step emitted the expected open-session contract values
such as RUN_ID, ENRICH_SESSION_ID, NEXT_OPTIONS, and the delete-script command.

.FUNCTION NAME
Invoke-EnrichOpenOutputContractVerification

.INPUTS
StepName string and EnrichStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when the contract is incomplete.
#>
function Invoke-EnrichOpenOutputContractVerification {
  param([string]$StepName,[object]$EnrichStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "RUN_ID=$($EnrichStep.RunId)",
    "ENRICH_SESSION_ID=$($EnrichStep.EnrichSessionId)",
    "NEXT_OPTIONS=$($EnrichStep.NextOptions)",
    "DELETE_SCRIPT_COMMAND=$($EnrichStep.DeleteScriptCommand)",
    "HAS_QUICK_COMMANDS=$($EnrichStep.HasQuickCommands)"
  )

  $missing = New-Object System.Collections.ArrayList
  if ([string]::IsNullOrWhiteSpace($EnrichStep.RunId)) { [void]$missing.Add('RUN_ID missing') }
  if ([string]::IsNullOrWhiteSpace($EnrichStep.EnrichSessionId)) { [void]$missing.Add('ENRICH_SESSION_ID missing') }
  if ([string]::IsNullOrWhiteSpace($EnrichStep.NextOptions)) { [void]$missing.Add('NEXT_OPTIONS missing') }
  if ([string]::IsNullOrWhiteSpace($EnrichStep.DeleteScriptCommand)) { [void]$missing.Add('DELETE_SCRIPT_COMMAND missing') }

  if (@($missing).Count -eq 0) {
    $status = 'PASS'
    $message = 'Open enrich-session output contract fields were emitted.'
  } else {
    $message = (@($missing) -join '; ')
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $EnrichStep.RunId -EnrichSessionId $EnrichStep.EnrichSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies the finalized enrich-session output contract fields.

.DESCRIPTION
Checks that an enrich-finalize step emitted the expected finalized-session contract
values such as RUN_ID, ENRICH_SESSION_ID, NEXT_GET_FILE, and the delete-script command.

.FUNCTION NAME
Invoke-EnrichFinalizedOutputContractVerification

.INPUTS
StepName string and EnrichStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when the contract is incomplete.
#>
function Invoke-EnrichFinalizedOutputContractVerification {
  param([string]$StepName,[object]$EnrichStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "RUN_ID=$($EnrichStep.RunId)",
    "ENRICH_SESSION_ID=$($EnrichStep.EnrichSessionId)",
    "NEXT_GET_FILE=$($EnrichStep.NextGetFile)",
    "DELETE_SCRIPT_COMMAND=$($EnrichStep.DeleteScriptCommand)",
    "HAS_QUICK_COMMANDS=$($EnrichStep.HasQuickCommands)"
  )

  $missing = New-Object System.Collections.ArrayList
  if ([string]::IsNullOrWhiteSpace($EnrichStep.RunId)) { [void]$missing.Add('RUN_ID missing') }
  if ([string]::IsNullOrWhiteSpace($EnrichStep.EnrichSessionId)) { [void]$missing.Add('ENRICH_SESSION_ID missing') }
  if ([string]::IsNullOrWhiteSpace($EnrichStep.NextGetFile)) { [void]$missing.Add('NEXT_GET_FILE missing') }
  if ([string]::IsNullOrWhiteSpace($EnrichStep.DeleteScriptCommand)) { [void]$missing.Add('DELETE_SCRIPT_COMMAND missing') }

  if (@($missing).Count -eq 0) {
    $status = 'PASS'
    $message = 'Finalized enrich-session output contract fields were emitted.'
  } else {
    $message = (@($missing) -join '; ')
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $EnrichStep.RunId -EnrichSessionId $EnrichStep.EnrichSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies the cleanup output contract fields.

.DESCRIPTION
Checks that the cleanup step emitted RUN_ID, a COMPLETE cleanup status, and the
delete-script command.

.FUNCTION NAME
Invoke-CleanupOutputContractVerification

.INPUTS
StepName string and CleanupStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when the contract is incomplete.
#>
function Invoke-CleanupOutputContractVerification {
  param([string]$StepName,[object]$CleanupStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "RUN_ID=$($CleanupStep.RunId)",
    "CLEANUP_STATUS=$($CleanupStep.CleanupStatus)",
    "DELETE_SCRIPT_COMMAND=$($CleanupStep.DeleteScriptCommand)",
    "HAS_QUICK_COMMANDS=$($CleanupStep.HasQuickCommands)"
  )

  $missing = New-Object System.Collections.ArrayList
  if ([string]::IsNullOrWhiteSpace($CleanupStep.RunId)) { [void]$missing.Add('RUN_ID missing') }
  if ($CleanupStep.CleanupStatus -ne 'COMPLETE') { [void]$missing.Add('CLEANUP_STATUS missing or not COMPLETE') }
  if ([string]::IsNullOrWhiteSpace($CleanupStep.DeleteScriptCommand)) { [void]$missing.Add('DELETE_SCRIPT_COMMAND missing') }

  if (@($missing).Count -eq 0) {
    $status = 'PASS'
    $message = 'Cleanup output contract fields were emitted.'
  } else {
    $message = (@($missing) -join '; ')
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $CleanupStep.RunId -EnrichSessionId $CleanupStep.EnrichSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies the attachment-budget manifest against the harness thresholds.

.DESCRIPTION
Reads the attachment-budget manifest, checks per-file and total-size values against the
