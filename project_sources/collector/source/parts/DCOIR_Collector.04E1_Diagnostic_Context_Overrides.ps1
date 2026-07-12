<#
.SYNOPSIS
DCOIR collector diagnostic-context helpers.

.DESCRIPTION
Provides the elevated-context checks and diagnostic-friendly Security/event-log readers
used to classify audit-policy access, explain non-elevated Security visibility limits,
and emit Security text surfaces that preserve explicit-window behavior.

.FILE NAME
DCOIR_Collector.04E1_Diagnostic_Context_Overrides.ps1

.INPUTS
Current process security context, WindowHours values, explicit event-window globals,
channel names, optional event IDs, and Security high-signal summary settings.

.OUTPUTS
Boolean elevation state, diagnostic message text, audit-policy text, Security summary
text, and general event-log text.
#>

<#
.SYNOPSIS
Determines whether the current collector context is elevated.

.DESCRIPTION
Queries the current Windows identity and returns true when the current principal is in
the local Administrators role. Returns false on any lookup error.

.FUNCTION NAME
Test-DiagnosticCollectorIsElevated

.INPUTS
No direct parameters.

.OUTPUTS
Boolean indicating whether the current collector context is elevated.
#>
function Test-DiagnosticCollectorIsElevated {
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
Returns the standard non-elevated Security visibility explanation.

.DESCRIPTION
Provides one durable message used when Security-event queries return no visible results
in a non-elevated context and the operator should verify the same query from an elevated
shell before concluding the window is truly empty.

.FUNCTION NAME
Get-NonElevatedSecurityVisibilityMessage

.INPUTS
No direct parameters.

.OUTPUTS
String containing the standard non-elevated Security visibility message.
#>
function Get-NonElevatedSecurityVisibilityMessage {
  return 'Security event query returned no matching events in the current non-elevated collection context. Verify the same query in an elevated shell before concluding the window is empty.'
}

<#
.SYNOPSIS
Collects audit-policy text and classifies audit-policy access status.

.DESCRIPTION
Queries the key Security audit subcategories, captures their output, and classifies the
current audit-policy access state as OK, privilege-required in a non-elevated context,
or failed-other for incomplete capture paths.

.FUNCTION NAME
Get-SecurityAuditPolicyText

.INPUTS
No direct parameters.

.OUTPUTS
String containing the combined per-subcategory auditpol command output.
#>
function Get-SecurityAuditPolicyText {
  $subcategories = @('Logon','Logoff','Special Logon','Process Creation')
  $blocks = New-Object System.Collections.ArrayList
  $exitCodes = New-Object System.Collections.ArrayList
  $isElevated = Test-DiagnosticCollectorIsElevated

  foreach ($subcategory in $subcategories) {
    $stepName = ('SECURITY_AUDIT_POLICY_{0}' -f ($subcategory -replace '[^A-Za-z0-9]', '_').ToUpperInvariant())
    $result = Invoke-ProcessCapture -FilePath 'auditpol.exe' -Arguments @('/get', ('/subcategory:{0}' -f $subcategory)) -StepName $stepName -AllowedExitCodes @(0,1314)
    [void]$blocks.Add((Get-CombinedProcessOutput -Result $result))
    [void]$exitCodes.Add([int]$result.ExitCode)
  }

  $allOk = (@($exitCodes).Count -gt 0) -and (@($exitCodes | Where-Object { $_ -ne 0 }).Count -eq 0)
  $allPrivilegeRequired = (@($exitCodes).Count -gt 0) -and (@($exitCodes | Where-Object { $_ -ne 1314 }).Count -eq 0)

  if ($allOk) {
    $script:CollectorAuditPolicyAccessStatus = 'OK'
  } elseif ((-not $isElevated) -and $allPrivilegeRequired) {
    $script:CollectorAuditPolicyAccessStatus = 'PRIVILEGE_REQUIRED_NON_ELEVATED'
    Add-CollectorNote 'Security audit policy access requires elevation in the current non-elevated execution context. Review the recorded auditpol output and re-run from an elevated shell only if that deeper visibility is required.'
  } else {
    $script:CollectorAuditPolicyAccessStatus = 'FAILED_OTHER'
    Add-CollectorError 'Security audit policy capture is incomplete for a reason other than the expected non-elevated privilege boundary. Review the per-subcategory auditpol command outputs in the artifact.'
  }

  return ($blocks -join ([Environment]::NewLine + [Environment]::NewLine))
}

<#
.SYNOPSIS
Runs a bounded Get-WinEvent query for text-oriented event summaries.

.DESCRIPTION
Applies the event limit at the Get-WinEvent query with -MaxEvents, then performs any
TimeCreated ordering only on the bounded result set. This keeps operator-facing limits
from turning into full-window materialization before text shaping.

.FUNCTION NAME
Invoke-CollectorBoundedWinEventQuery

.INPUTS
Filter hashtable and maximum event count.

.OUTPUTS
Array of event records ordered newest first within the bounded result set.
#>
function Invoke-CollectorBoundedWinEventQuery {
  param(
    [Parameter(Mandatory=$true)][hashtable]$FilterHashtable,
    [int]$MaxEvents
  )

  if ($MaxEvents -lt 1) {
    return @()
  }

  $events = @(Get-WinEvent -FilterHashtable $FilterHashtable -MaxEvents $MaxEvents -ErrorAction Stop)
  return @($events | Sort-Object TimeCreated -Descending)
}
