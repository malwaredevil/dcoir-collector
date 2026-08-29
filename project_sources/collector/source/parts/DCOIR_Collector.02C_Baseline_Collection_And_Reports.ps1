<#
.SYNOPSIS
DCOIR collector Tier 2 baseline persistence helpers.

.DESCRIPTION
Collects Tier 2 registry, WMI persistence, share, session, and firewall deep-check text surfaces for baseline report inclusion.

.FILE NAME
DCOIR_Collector.02C_Baseline_Collection_And_Reports.ps1

.INPUTS
Collector state, tool-map data, registry paths, and Tier 2 runtime context.

.OUTPUTS
Tier 2 persistence and deep-check text artifacts and combined report text.
#>

<#
.SYNOPSIS
Runs one Tier 2 registry query through direct reg.exe capture.

.DESCRIPTION
Invokes reg.exe directly for one Tier 2 deep-check registry path, preserves the bounded
captured output, and records a collector error when the query returns a non-zero exit
code so the artifact remains the truth surface instead of failing invisibly.

.FUNCTION NAME
Invoke-Tier2RegistryQueryText

.INPUTS
RegistryPath string, StepName string, and optional FailureLabel string.

.OUTPUTS
String containing the combined direct-process output for the Tier 2 registry query.
#>
function Invoke-Tier2RegistryQueryText {
  param(
    [Parameter(Mandatory=$true)][string]$RegistryPath,
    [Parameter(Mandatory=$true)][string]$StepName,
    [string]$FailureLabel = 'Tier 2 registry query'
  )

  $result = Invoke-ProcessCapture -FilePath 'reg.exe' -Arguments @('query', $RegistryPath, '/s') -StepName $StepName -AllowedExitCodes @(0,1)
  if ($result.ExitCode -ne 0) {
    Add-CollectorError ('{0} returned ExitCode={1} for path [{2}]. Review the artifact for the exact bounded output.' -f $FailureLabel, $result.ExitCode, $RegistryPath)
  }
  return (Get-CombinedProcessOutput -Result $result)
}

<#
.SYNOPSIS
Builds the Tier 2 WMI persistence text surface class by class.

.DESCRIPTION
Queries the root\subscription WMI classes one at a time so one failing class does not
break the whole Tier 2 WMI persistence surface. Each class writes either formatted
results, NO_RESULTS, or one bounded error line that is also added to the collector error
list.

.FUNCTION NAME
Get-Tier2WmiPersistenceText

.INPUTS
No direct parameters.

.OUTPUTS
String containing the combined Tier 2 WMI persistence text surface.
#>
function Get-Tier2WmiPersistenceText {
  $classNames = @(
    '__EventFilter',
    'CommandLineEventConsumer',
    'ActiveScriptEventConsumer',
    'FilterToConsumerBinding'
  )

  $sections = New-Object System.Collections.ArrayList
  foreach ($className in $classNames) {
    [void]$sections.Add(('WMI_CLASS={0}' -f $className))
    [void]$sections.Add('')
    try {
      $instances = @(Get-CimInstance -Namespace 'root\subscription' -ClassName $className -ErrorAction Stop)
      if (@($instances).Count -gt 0) {
        [void]$sections.Add((($instances | Format-List * | Out-String -Width 500).TrimEnd()))
      } else {
        [void]$sections.Add('NO_RESULTS')
      }
    } catch {
      $message = 'ERROR collecting WMI persistence class [{0}]: {1}' -f $className, $_.Exception.Message
      Add-CollectorError $message
      [void]$sections.Add($message)
    }
    [void]$sections.Add('')
    [void]$sections.Add(('—' * 80))
    [void]$sections.Add('')
  }

  return ($sections -join [Environment]::NewLine)
}

<#
.SYNOPSIS
Builds the Tier 2 persistence deep-check text surface.

.DESCRIPTION
Collects Tier 2-only registry, WMI persistence, share, session, and firewall text
artifacts, writes each one to disk, and returns the combined text surface for report
inclusion.

.FUNCTION NAME
Get-Tier2PersistenceText

.INPUTS
Collector state hashtable and ToolMap hashtable.

.OUTPUTS
String containing the combined Tier 2 persistence and deep-check text surface.
#>
function Get-Tier2PersistenceText {
  param([hashtable]$State,[hashtable]$ToolMap)

  $sb = New-Object System.Text.StringBuilder

  $regIfeo = Invoke-Tier2RegistryQueryText -RegistryPath 'HKLM\Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options' -StepName 'TIER2_REG_IFEO' -FailureLabel 'Tier 2 IFEO registry query'
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_reg_ifeo.txt' -Text $regIfeo)
  Add-Section -Builder $sb -Name 'TIER2_REG_IFEO' -Text $regIfeo

  $regWinlogon = Invoke-Tier2RegistryQueryText -RegistryPath 'HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon' -StepName 'TIER2_REG_WINLOGON' -FailureLabel 'Tier 2 Winlogon registry query'
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_reg_winlogon.txt' -Text $regWinlogon)
  Add-Section -Builder $sb -Name 'TIER2_REG_WINLOGON' -Text $regWinlogon

  $regLsa = Invoke-Tier2RegistryQueryText -RegistryPath 'HKLM\SYSTEM\CurrentControlSet\Control\Lsa' -StepName 'TIER2_REG_LSA' -FailureLabel 'Tier 2 LSA registry query'
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_reg_lsa.txt' -Text $regLsa)
  Add-Section -Builder $sb -Name 'TIER2_REG_LSA' -Text $regLsa

  $wmiText = Get-Tier2WmiPersistenceText
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_wmi_persistence.txt' -Text $wmiText)
  Add-Section -Builder $sb -Name 'TIER2_WMI_PERSISTENCE' -Text $wmiText

  $netShare = Get-CmdText -Command 'net share' -StepName 'TIER2_NET_SHARE'
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_net_share.txt' -Text $netShare)
  Add-Section -Builder $sb -Name 'TIER2_NET_SHARE' -Text $netShare

  $netSession = Get-CmdText -Command 'net session' -StepName 'TIER2_NET_SESSION' -AllowedExitCodes @(0,2)
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_net_session.txt' -Text $netSession)
  Add-Section -Builder $sb -Name 'TIER2_NET_SESSION' -Text $netSession

  $fw = Get-CmdText -Command 'netsh advfirewall show allprofiles' -StepName 'TIER2_FIREWALL_PROFILES'
  [void](Write-ArtifactText -ArtifactsDir $State.ArtifactsDir -Section 'TIER2_DEEP_CHECKS' -Name 'tier2_firewall_profiles.txt' -Text $fw)
  Add-Section -Builder $sb -Name 'TIER2_FIREWALL_PROFILES' -Text $fw

  return $sb.ToString()
}
