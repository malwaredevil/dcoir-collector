<#
.SYNOPSIS
DCOIR collector baseline report writer.

.DESCRIPTION
Builds the main baseline artifact set, analyst follow-up queue, and baseline report structures.

.FILE NAME
DCOIR_Collector.02D1B_Baseline_Collection_And_Reports.ps1

.INPUTS
Collector state, tool-map data, baseline artifact paths, notes, errors, recommendations, and runtime settings.

.OUTPUTS
Baseline report structures and artifact path/map structures.
#>

<#
.SYNOPSIS
Builds the baseline report and baseline artifact set.

.DESCRIPTION
Collects the baseline artifact families, writes them to disk, appends them into the
main baseline report, emits analyst follow-up recommendations, and returns the report
builder plus artifact path and map structures.

.FUNCTION NAME
New-BaselineReport

.INPUTS
Collector state hashtable and ToolMap hashtable.

.OUTPUTS
Hashtable containing ReportBuilder, ReportText, ArtifactPaths, and ArtifactMap.
#>
function New-BaselineReport {
  [CmdletBinding()]
  param([hashtable]$State,[hashtable]$ToolMap)

  $artifactPaths = New-Object System.Collections.ArrayList
  $artifactMap = @{}
  $sb = New-Object System.Text.StringBuilder
  $isElevated = Test-CollectorIsElevated

  Add-BaselineCollectionContext -State $State -ArtifactPaths $artifactPaths -ArtifactMap $artifactMap -Builder $sb -IsElevated $isElevated


  $timeHostText = Get-CmdText -Command 'date /t & time /t & hostname & ver' -StepName "HOST_DATE_TIME_HOSTNAME"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "HOST_BASELINE" -Name "time_host.txt" -Text $timeHostText
  [void]$artifactPaths.Add($p); $artifactMap['time_host'] = $p
  $systemInfoText = Get-CmdText -Command 'systeminfo' -StepName "HOST_SYSTEMINFO"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "HOST_BASELINE" -Name "systeminfo.txt" -Text $systemInfoText
  [void]$artifactPaths.Add($p); $artifactMap['systeminfo'] = $p
  Add-Section -Builder $sb -Name "HOST_BASELINE" -Text (@($timeHostText, "", $systemInfoText) -join [Environment]::NewLine)

  $whoamiText = Get-CmdText -Command 'whoami /all' -StepName "IDENTITY_WHOAMI_ALL"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "IDENTITY_AND_SESSION_CONTEXT" -Name "whoami_all.txt" -Text $whoamiText
  [void]$artifactPaths.Add($p); $artifactMap['whoami_all'] = $p
  $sessionsText = Get-CmdText -Command 'query user & qwinsta' -StepName "IDENTITY_QUERY_USER_QWINSTA"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "IDENTITY_AND_SESSION_CONTEXT" -Name "sessions.txt" -Text $sessionsText
  [void]$artifactPaths.Add($p); $artifactMap['sessions'] = $p
  $logonSessionsWmiText = Get-LogonSessionsWmiText
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "IDENTITY_AND_SESSION_CONTEXT" -Name "logon_sessions_wmi.txt" -Text $logonSessionsWmiText
  [void]$artifactPaths.Add($p); $artifactMap['logon_sessions_wmi'] = $p
  Add-Section -Builder $sb -Name "IDENTITY_AND_SESSION_CONTEXT" -Text (@($whoamiText, "", $sessionsText, "", $logonSessionsWmiText) -join [Environment]::NewLine)

  $procInventory = Get-ProcessInventory
  $excludedPids = @([int]$PID)
  try {
    $selfProc = Get-CimInstance -ClassName Win32_Process -Filter ("ProcessId={0}" -f $PID) -ErrorAction Stop
    if ($selfProc.ParentProcessId) { $excludedPids += [int]$selfProc.ParentProcessId }
  } catch { }
  $procInventoryText = Convert-ToTextBlock -InputObject ($procInventory | Select-Object ProcessId, ParentProcessId, ParentProcessName, Name, Owner, ExecutablePath, CreationTime, CommandLine)
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PROCESS_EXECUTION_CONTEXT" -Name "process_inventory.txt" -Text $procInventoryText
  [void]$artifactPaths.Add($p); $artifactMap['process_inventory'] = $p
  $procParts = @($procInventoryText)
  if ($ToolMap['pslist']) {
    $pslistText = Invoke-ToolToText -ToolPath $ToolMap['pslist'] -Arguments @('-accepteula','-nobanner','-t') -StepName "SYSINTERNALS_PSLIST"
    $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PROCESS_EXECUTION_CONTEXT" -Name "pslist.txt" -Text $pslistText
    [void]$artifactPaths.Add($p); $artifactMap['pslist'] = $p
    $procParts += ""
    $procParts += $pslistText
  }
  Add-Section -Builder $sb -Name "PROCESS_EXECUTION_CONTEXT" -Text ($procParts -join [Environment]::NewLine)

  $ipconfigText = Get-CmdText -Command 'ipconfig /all' -StepName "NETWORK_IPCONFIG"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "ipconfig_all.txt" -Text $ipconfigText
  [void]$artifactPaths.Add($p); $artifactMap['ipconfig_all'] = $p
  $netstatBundle = Get-NetstatCaptureBundle -IsElevated $isElevated
  $netstatText = $netstatBundle.OwnerAwareText
  $State.NetstatOwnerAwareStatus = $netstatBundle.OwnerAwareStatus
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "netstat_abno.txt" -Text $netstatText
  [void]$artifactPaths.Add($p); $artifactMap['netstat_abno'] = $p
  $structuredNetText = Get-BaselineNetText
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "structured_net.txt" -Text $structuredNetText
  [void]$artifactPaths.Add($p); $artifactMap['structured_net'] = $p
  $dnsText = Get-CmdText -Command 'ipconfig /displaydns' -StepName "NETWORK_DNS_CACHE"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "dns_cache.txt" -Text $dnsText
  [void]$artifactPaths.Add($p); $artifactMap['dns_cache'] = $p
  $routeText = Get-CmdText -Command 'route print' -StepName "NETWORK_ROUTE_PRINT"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "route_print.txt" -Text $routeText
  [void]$artifactPaths.Add($p); $artifactMap['route_print'] = $p
  $arpText = Get-CmdText -Command 'arp -a' -StepName "NETWORK_ARP_A"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "arp_a.txt" -Text $arpText
  [void]$artifactPaths.Add($p); $artifactMap['arp_a'] = $p
  $networkParts = @($ipconfigText, "", $netstatText, "", $structuredNetText, "", $dnsText, "", $routeText, "", $arpText)
  if ($netstatBundle.PidOnlyText) {
    $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "netstat_ano_supplemental.txt" -Text $netstatBundle.PidOnlyText
    [void]$artifactPaths.Add($p); $artifactMap['netstat_ano_supplemental'] = $p; $State.NetstatPidOnlyPath = $p
    $networkParts += ""
    $networkParts += $netstatBundle.PidOnlyText
  }
  if ($ToolMap['tcpvcon']) {
    $tcpvconText = Invoke-ToolToText -ToolPath $ToolMap['tcpvcon'] -Arguments @('-accepteula','-nobanner') -StepName "SYSINTERNALS_TCPVCON"
    $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "tcpvcon.txt" -Text $tcpvconText
    [void]$artifactPaths.Add($p); $artifactMap['tcpvcon'] = $p
    $networkParts += ""
    $networkParts += $tcpvconText
  }
  if ($ToolMap['pipelist']) {
    $pipelistText = Invoke-ToolToText -ToolPath $ToolMap['pipelist'] -Arguments @('-accepteula','-nobanner') -StepName "SYSINTERNALS_PIPELIST"
    $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "NETWORK_STATE" -Name "pipelist.txt" -Text $pipelistText
    [void]$artifactPaths.Add($p); $artifactMap['pipelist'] = $p
    $networkParts += ""
    $networkParts += $pipelistText
  }
  Add-Section -Builder $sb -Name "NETWORK_STATE" -Text ($networkParts -join [Environment]::NewLine)

  $servicesText = Get-CmdText -Command 'sc queryex type= service state= all' -StepName "PERSISTENCE_SERVICES"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PERSISTENCE_AND_AUTOSTARTS" -Name "services.txt" -Text $servicesText
  [void]$artifactPaths.Add($p); $artifactMap['services'] = $p
  $tasksText = Get-CmdText -Command 'schtasks /query /fo LIST /v' -StepName "PERSISTENCE_SCHEDULED_TASKS"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PERSISTENCE_AND_AUTOSTARTS" -Name "scheduled_tasks.txt" -Text $tasksText
  [void]$artifactPaths.Add($p); $artifactMap['scheduled_tasks'] = $p
  $hklmRunText = Get-RegistryQueryText -RegistryPath 'HKLM\Software\Microsoft\Windows\CurrentVersion\Run' -StepName "PERSISTENCE_HKLM_RUN"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PERSISTENCE_AND_AUTOSTARTS" -Name "run_hklm.txt" -Text $hklmRunText
  [void]$artifactPaths.Add($p); $artifactMap['run_hklm'] = $p
  $hkuRunText = Get-LoadedUserRunKeysText
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PERSISTENCE_AND_AUTOSTARTS" -Name "run_hku_loaded_users.txt" -Text $hkuRunText
  [void]$artifactPaths.Add($p); $artifactMap['run_hku_loaded_users'] = $p
  $persistenceParts = @($servicesText, "", $tasksText, "", $hklmRunText, "", $hkuRunText)
  if ($ToolMap['autorunsc']) {
    $autorunsText = Invoke-ToolToText -ToolPath $ToolMap['autorunsc'] -Arguments @('-accepteula','-nobanner','-a','*','-c','-h','-s','*') -StepName "SYSINTERNALS_AUTORUNSC"
    $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "PERSISTENCE_AND_AUTOSTARTS" -Name "autorunsc.csv.txt" -Text $autorunsText
    [void]$artifactPaths.Add($p); $artifactMap['autorunsc'] = $p
    $persistenceParts += ""
    $persistenceParts += $autorunsText
  }
  Add-Section -Builder $sb -Name "PERSISTENCE_AND_AUTOSTARTS" -Text ($persistenceParts -join [Environment]::NewLine)

  $defenderText = Get-DefenderStatusText
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "SECURITY_POSTURE_AND_DEFENSIVE_STATE" -Name "defender_status.txt" -Text $defenderText
  [void]$artifactPaths.Add($p); $artifactMap['defender_status'] = $p
  $firewallText = Get-CmdText -Command 'netsh advfirewall show allprofiles' -StepName "SECURITY_FIREWALL_PROFILES"
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "SECURITY_POSTURE_AND_DEFENSIVE_STATE" -Name "firewall_profiles.txt" -Text $firewallText
  [void]$artifactPaths.Add($p); $artifactMap['firewall_profiles'] = $p
  Add-Section -Builder $sb -Name "SECURITY_POSTURE_AND_DEFENSIVE_STATE" -Text (@($defenderText, "", $firewallText) -join [Environment]::NewLine)

  $securityIds = @(4624,4625,4634,4647,4648,4672,4688,4697,4698)
  $securityText = Get-EventText -Channel "Security" -WindowHours $Hours -Ids $securityIds -Take $MaxEvents
  $securityText += Get-TestTextPaddingFromEnvironment -Name 'DCOIR_TEST_SECURITY_FILTERED_OVERSIZE_KB'
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "EVENT_TIMELINE_TEXT" -Name "security_filtered.txt" -Text $securityText
  [void]$artifactPaths.Add($p); $artifactMap['security_filtered'] = $p; $State.SecurityFilteredPath = $p
  $securityHighSignalText = Get-SecurityHighSignalSummaryText -WindowHours $Hours -Take ([Math]::Min($MaxEvents, 200))
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "EVENT_TIMELINE_TEXT" -Name "security_high_signal_summary.txt" -Text $securityHighSignalText
  [void]$artifactPaths.Add($p); $artifactMap['security_high_signal_summary'] = $p; $State.SecurityHighSignalSummaryPath = $p
  $psOpText = Get-EventText -Channel "Microsoft-Windows-PowerShell/Operational" -WindowHours $Hours -Take $MaxEvents
  $psOpText += Get-TestTextPaddingFromEnvironment -Name 'DCOIR_TEST_POWERSHELL_OPERATIONAL_OVERSIZE_KB'
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "EVENT_TIMELINE_TEXT" -Name "powershell_operational_filtered.txt" -Text $psOpText
  [void]$artifactPaths.Add($p); $artifactMap['powershell_operational_filtered'] = $p
  $taskOpText = Get-EventText -Channel "Microsoft-Windows-TaskScheduler/Operational" -WindowHours $Hours -Take $MaxEvents
  $taskOpText += Get-TestTextPaddingFromEnvironment -Name 'DCOIR_TEST_TASKSCHEDULER_OPERATIONAL_OVERSIZE_KB'
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "EVENT_TIMELINE_TEXT" -Name "taskscheduler_operational_filtered.txt" -Text $taskOpText
  [void]$artifactPaths.Add($p); $artifactMap['taskscheduler_operational_filtered'] = $p
  Add-Section -Builder $sb -Name "EVENT_TIMELINE_TEXT_HIGH_SIGNAL" -Text $securityHighSignalText
  Add-Section -Builder $sb -Name "EVENT_TIMELINE_TEXT" -Text (@($securityText, "", $psOpText, "", $taskOpText) -join [Environment]::NewLine)

  if ($Tier -eq "T2") {
    Add-Section -Builder $sb -Name "TIER2_DEEP_CHECKS" -Text (Get-Tier2PersistenceText -State $State -ToolMap $ToolMap)
  }

  Add-BaselineSuspiciousProcessRecommendations -State $State -OutRoot $OutRoot -Processes $procInventory -ExcludedPids $excludedPids

  $followUpText = ($Global:RecommendedActions -join [Environment]::NewLine)
  $p = Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section "ANALYST_FOLLOW_UP_QUEUE" -Name "analyst_follow_up_queue.txt" -Text $followUpText
  [void]$artifactPaths.Add($p); $artifactMap['analyst_follow_up_queue'] = $p
  Add-Section -Builder $sb -Name "ANALYST_FOLLOW_UP_QUEUE" -Text $followUpText

  return @{
    ReportBuilder = $sb
    ReportText = $sb.ToString()
    ArtifactPaths = $artifactPaths
    ArtifactMap = $artifactMap
  }
}
