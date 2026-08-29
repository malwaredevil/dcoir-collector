<#
.SYNOPSIS
DCOIR collector diagnostic-context event text helpers.

.DESCRIPTION
Provides Security high-signal summary and event-log text readers that preserve explicit
window behavior and report non-elevated Security visibility boundaries consistently.

.FILE NAME
DCOIR_Collector.04E2_Diagnostic_Context_Overrides.ps1

.INPUTS
WindowHours values, explicit event-window globals, channel names, optional event IDs,
and Security high-signal summary settings.

.OUTPUTS
Security summary text and general event-log text.
#>

<#
.SYNOPSIS
Builds a diagnostic-friendly Security high-signal summary.

.DESCRIPTION
Uses the effective event window to query key Security events, suppresses routine
service/machine noise and routine Microsoft-managed task/service churn, and returns
analyst-facing summary text while preserving the special non-elevated visibility
message when appropriate.

.FUNCTION NAME
Get-SecurityHighSignalSummaryText

.INPUTS
WindowHours integer and Take integer limiting the returned summary volume.

.OUTPUTS
String containing the Security high-signal summary or an explicit visibility/error
message.
#>
function Get-SecurityHighSignalSummaryText {
  param(
    [int]$WindowHours = 24,
    [int]$Take = 200
  )

  try {
    $ids = @(4624,4625,4648,4672,4688,4697,4698)
    $window = Get-CollectorEffectiveEventWindow -WindowHours $WindowHours
    $fh = @{
      LogName = 'Security'
      StartTime = $window.StartTime
      Id = $ids
    }
    if ($window.HasExplicitWindow -and $window.EndTime) {
      $fh.EndTime = $window.EndTime
    }

    $queryLimit = [Math]::Max(0, ($Take * 4))
    $events = @(Invoke-CollectorBoundedWinEventQuery -FilterHashtable $fh -MaxEvents $queryLimit)

    if (@($events).Count -eq 0) {
      $lines = New-Object System.Collections.ArrayList
      [void]$lines.Add('SECURITY_HIGH_SIGNAL_SUMMARY')
      foreach ($metadataLine in (Get-CollectorEventWindowMetadataLines -Window $window -Channel 'Security' -Ids $ids -Take $Take)) { [void]$lines.Add($metadataLine) }
      [void]$lines.Add('RAW_EVENT_COUNT=0')
      [void]$lines.Add('INTERESTING_EVENT_COUNT=0')
      [void]$lines.Add('SUPPRESSED_EVENT_COUNT=0')
      [void]$lines.Add('')
      if (-not (Test-DiagnosticCollectorIsElevated)) {
        $message = Get-NonElevatedSecurityVisibilityMessage
        Add-CollectorNote $message
        [void]$lines.Add($message)
        return ($lines -join [Environment]::NewLine)
      }
      $message = 'No high-signal Security events were found in the selected window.'
      Add-CollectorNote $message
      [void]$lines.Add($message)
      return ($lines -join [Environment]::NewLine)
    }

    $interesting = New-Object System.Collections.ArrayList
    $suppressed = New-Object System.Collections.ArrayList

    foreach ($ev in $events) {
      $m = Get-EventDataMap -EventRecord $ev

      $subjectUser = Get-EventMapValue -Map $m -Key 'SubjectUserName'
      $subjectDomain = Get-EventMapValue -Map $m -Key 'SubjectDomainName'
      $targetUser = Get-EventMapValue -Map $m -Key 'TargetUserName'
      $targetDomain = Get-EventMapValue -Map $m -Key 'TargetDomainName'
      $logonType = Get-EventMapValue -Map $m -Key 'LogonType'
      $taskName = Get-EventMapValue -Map $m -Key 'TaskName'
      $serviceName = Get-EventMapValue -Map $m -Key 'ServiceName'
      $serviceFileName = Get-EventMapValue -Map $m -Key 'ServiceFileName'

      $subjectIsMachine = ($subjectUser -like '*$')
      $targetIsMachine = ($targetUser -like '*$')
      $subjectIsBuiltinService = $subjectUser -in @('SYSTEM','LOCAL SERVICE','NETWORK SERVICE','ANONYMOUS LOGON')
      $targetIsBuiltinService = $targetUser -in @('SYSTEM','LOCAL SERVICE','NETWORK SERVICE','ANONYMOUS LOGON')
      $isServiceStyleLogon = $logonType -in @('0','5')
      $taskIsMicrosoftManaged = $taskName -like '\Microsoft\Windows\*'
      $taskIsKnownRoutineEnvironmentChurn = $taskName -match '(?i)^\\(UptimeCheck|UptimePopup|Deploy_Sysmon_Production|Cleanup Old PS Transcripts)$'
      $serviceFileIsWindowsManaged = $serviceFileName -match '^(?i)(%systemroot%|[A-Z]:\\Windows\\)'
      $serviceHostStyle = ($serviceFileName -match '(?i)\\svchost\.exe(\s|$)') -or ($serviceFileName -match '(?i)\\services\.exe(\s|$)')
      $serviceNameLooksPerUser = $serviceName -match '(?i)^(CDPUserSvc|OneSyncSvc|UnistoreSvc|UserDataSvc|WpnUserService|BcastDVRUserService|PimIndexMaintenanceSvc|PrintWorkflowUserSvc|UdkUserSvc|CaptureService|ConsentUxUserSvc|CredentialEnrollmentManagerUserSvc|DevicePickerUserSvc|DevicesFlowUserSvc)(_[0-9a-f]+)?$'

      $suppress = $false
      $suppressReason = $null

      switch ([int]$ev.Id) {
        4624 {
          if (($subjectIsMachine -or $targetIsMachine -or $subjectIsBuiltinService -or $targetIsBuiltinService) -and $isServiceStyleLogon) {
            $suppress = $true
            $suppressReason = 'routine successful service or machine logon'
          }
        }
        4672 {
          if ($subjectIsMachine -or $subjectIsBuiltinService) {
            $suppress = $true
            $suppressReason = 'routine special privileges assignment for service or machine account'
          }
        }
        4697 {
          if (($subjectIsMachine -or $subjectIsBuiltinService) -and $serviceFileIsWindowsManaged -and ($serviceHostStyle -or $serviceNameLooksPerUser)) {
            $suppress = $true
            $suppressReason = 'routine Windows-managed service registration or update'
          }
        }
        4698 {
          if (($subjectIsMachine -or $subjectIsBuiltinService) -and ($taskIsMicrosoftManaged -or $taskIsKnownRoutineEnvironmentChurn)) {
            $suppress = $true
            if ($taskIsMicrosoftManaged) {
              $suppressReason = 'routine Microsoft-managed scheduled task registration or update'
            } else {
              $suppressReason = 'routine environment-managed scheduled task registration or update'
            }
          }
        }
      }

      if ($suppress) {
        [void]$suppressed.Add([pscustomobject]@{
          Id = $ev.Id
          TimeCreated = $ev.TimeCreated
          Reason = $suppressReason
          Account = ("{0}\{1}" -f $subjectDomain, $subjectUser).Trim('\\')
          LogonType = $logonType
        })
      } else {
        [void]$interesting.Add([pscustomobject]@{
          EventRecord = $ev
          EventData = $m
        })
      }
    }

    $interesting = @($interesting | Sort-Object { $_.EventRecord.TimeCreated } -Descending | Select-Object -First $Take)

    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add('SECURITY_HIGH_SIGNAL_SUMMARY')
    foreach ($metadataLine in (Get-CollectorEventWindowMetadataLines -Window $window -Channel 'Security' -Ids $ids -Take $Take)) { [void]$lines.Add($metadataLine) }
    [void]$lines.Add(("RAW_EVENT_COUNT={0}" -f @($events).Count))
    [void]$lines.Add(("INTERESTING_EVENT_COUNT={0}" -f @($interesting).Count))
    [void]$lines.Add(("SUPPRESSED_EVENT_COUNT={0}" -f @($suppressed).Count))
    [void]$lines.Add('')

    $counts = $interesting | Group-Object { $_.EventRecord.Id } | Sort-Object Name
    [void]$lines.Add('INTERESTING_EVENT_COUNTS')
    if (@($counts).Count -eq 0) {
      [void]$lines.Add('Id=NONE Count=0')
    } else {
      foreach ($g in $counts) {
        [void]$lines.Add(("Id={0} Count={1}" -f $g.Name, $g.Count))
      }
    }

    if (@($suppressed).Count -gt 0) {
      [void]$lines.Add('')
      [void]$lines.Add('SUPPRESSED_EVENT_COUNTS')
      $suppressedCounts = $suppressed | Group-Object Id, Reason | Sort-Object Name
      foreach ($g in $suppressedCounts) {
        [void]$lines.Add(("{0} Count={1}" -f $g.Name, $g.Count))
      }
    }

    if (@($interesting).Count -eq 0) {
      [void]$lines.Add('')
      [void]$lines.Add('EVENT_SUMMARY')
      [void]$lines.Add('No analyst-facing high-signal Security events remained after routine Microsoft-managed task/service suppression in the selected window.')
      return ($lines -join [Environment]::NewLine)
    }

    [void]$lines.Add('')
    [void]$lines.Add('EVENT_SUMMARY')

    foreach ($item in $interesting) {
      $ev = $item.EventRecord
      $m = $item.EventData
      $summary = ''
      switch ([int]$ev.Id) {
        4624 {
          $summary = "Successful logon Target={0}\{1} LogonType={2} SourceIp={3} Workstation={4}" -f (Get-EventMapValue -Map $m -Key 'TargetDomainName'), (Get-EventMapValue -Map $m -Key 'TargetUserName'), (Get-EventMapValue -Map $m -Key 'LogonType'), (Get-EventMapValue -Map $m -Key 'IpAddress'), (Get-EventMapValue -Map $m -Key 'WorkstationName')
        }
        4625 {
          $summary = "Failed logon Target={0}\{1} LogonType={2} SourceIp={3} Status={4} SubStatus={5}" -f (Get-EventMapValue -Map $m -Key 'TargetDomainName'), (Get-EventMapValue -Map $m -Key 'TargetUserName'), (Get-EventMapValue -Map $m -Key 'LogonType'), (Get-EventMapValue -Map $m -Key 'IpAddress'), (Get-EventMapValue -Map $m -Key 'Status'), (Get-EventMapValue -Map $m -Key 'SubStatus')
        }
        4648 {
          $summary = "Explicit credentials Subject={0}\{1} TargetServer={2} Process={3} SourceIp={4}" -f (Get-EventMapValue -Map $m -Key 'SubjectDomainName'), (Get-EventMapValue -Map $m -Key 'SubjectUserName'), (Get-EventMapValue -Map $m -Key 'TargetServerName'), (Get-EventMapValue -Map $m -Key 'ProcessName'), (Get-EventMapValue -Map $m -Key 'IpAddress')
        }
        4672 {
          $summary = "Special privileges assigned Subject={0}\{1} Privileges={2}" -f (Get-EventMapValue -Map $m -Key 'SubjectDomainName'), (Get-EventMapValue -Map $m -Key 'SubjectUserName'), (Get-EventMapValue -Map $m -Key 'PrivilegeList')
        }
        4688 {
          $summary = "Process created NewProcess={0} ParentProcess={1} Subject={2}\{3} CommandLine={4}" -f (Get-EventMapValue -Map $m -Key 'NewProcessName'), (Get-EventMapValue -Map $m -Key 'ParentProcessName'), (Get-EventMapValue -Map $m -Key 'SubjectDomainName'), (Get-EventMapValue -Map $m -Key 'SubjectUserName'), (Get-EventMapValue -Map $m -Key 'CommandLine')
        }
        4697 {
          $summary = "Service installed Name={0} File={1} Subject={2}\{3}" -f (Get-EventMapValue -Map $m -Key 'ServiceName'), (Get-EventMapValue -Map $m -Key 'ServiceFileName'), (Get-EventMapValue -Map $m -Key 'SubjectDomainName'), (Get-EventMapValue -Map $m -Key 'SubjectUserName')
        }
        4698 {
          $summary = "Scheduled task created TaskName={0} Subject={1}\{2}" -f (Get-EventMapValue -Map $m -Key 'TaskName'), (Get-EventMapValue -Map $m -Key 'SubjectDomainName'), (Get-EventMapValue -Map $m -Key 'SubjectUserName')
        }
        default {
          $summary = ($ev.Message -replace "`r", '' -replace "`n", ' ')
        }
      }

      [void]$lines.Add(("[{0}] Id={1} {2}" -f $ev.TimeCreated.ToString('o'), $ev.Id, $summary.Trim()))
    }

    return ($lines -join [Environment]::NewLine)
  } catch {
    $msg = $_.Exception.Message
    if ($msg -match 'No events were found') {
      $window = Get-CollectorEffectiveEventWindow -WindowHours $WindowHours
      $lines = New-Object System.Collections.ArrayList
      [void]$lines.Add('SECURITY_HIGH_SIGNAL_SUMMARY')
      foreach ($metadataLine in (Get-CollectorEventWindowMetadataLines -Window $window -Channel 'Security' -Ids $ids -Take $Take)) { [void]$lines.Add($metadataLine) }
      [void]$lines.Add('RAW_EVENT_COUNT=0')
      [void]$lines.Add('INTERESTING_EVENT_COUNT=0')
      [void]$lines.Add('SUPPRESSED_EVENT_COUNT=0')
      [void]$lines.Add('')
      if (-not (Test-DiagnosticCollectorIsElevated)) {
        $message = Get-NonElevatedSecurityVisibilityMessage
        Add-CollectorNote $message
        [void]$lines.Add($message)
        return ($lines -join [Environment]::NewLine)
      }
      $message = 'No high-signal Security events were found in the selected window.'
      Add-CollectorNote $message
      [void]$lines.Add($message)
      return ($lines -join [Environment]::NewLine)
    }
    Add-CollectorError ("Failed to collect condensed Security summary: {0}" -f $msg)
    return ("ERROR collecting condensed Security summary: {0}" -f $msg)
  }
}
