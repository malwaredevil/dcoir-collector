<#
.SYNOPSIS
DCOIR collector suspicious-process and baseline text utility helpers.

.DESCRIPTION
Provides suspicious-process heuristics, structured network baseline text, Defender
status text, and registry query text helpers used by baseline collection surfaces.

.FILE NAME
DCOIR_Collector.01D2_Process_Event_And_Baseline_Utilities.ps1

.INPUTS
Process inventory rows, registry paths, and collector runtime state.

.OUTPUTS
Suspicious-process finding rows, network/Defender/registry baseline text, and collector
notes/errors.
#>
<#
.SYNOPSIS
Returns suspicious-process heuristic findings from the process inventory.

.DESCRIPTION
Applies command-line, path, and LOLBin heuristics to the process inventory while using
parent-process context to reduce low-confidence name-only LOLBin noise. Suspicious
command-line and path indicators still produce findings.

.FUNCTION NAME
Get-SuspiciousProcessFindings

.INPUTS
Processes array and ExcludedPids integer array.

.OUTPUTS
ArrayList of suspicious process finding objects.
#>
function Get-SuspiciousProcessFindings {
  param([object[]]$Processes,[int[]]$ExcludedPids)

  $findings = New-Object System.Collections.ArrayList
  foreach ($proc in $Processes) {
    if (@($ExcludedPids) -contains [int]$proc.ProcessId) { continue }

    $reasons = New-Object System.Collections.ArrayList
    $cmd = [string]$proc.CommandLine
    $pathValue = [string]$proc.ExecutablePath
    $nameValue = [string]$proc.Name
    $parentNameValue = [string]$proc.ParentProcessName
    $nameOnlyLolbinPattern = '^(powershell|pwsh|rundll32|regsvr32|mshta|wscript|cscript|cmd|certutil|bitsadmin|wmic|psexec)(\.exe)?$'
    $benignNameOnlyLolbinPattern = '^(powershell|pwsh|cmd|wmic)(\.exe)?$'
    $knownBenignLolbinParentPattern = '^(svchost|services|trustedinstaller|tiworker|wuauclt|msiexec)(\.exe)?$'
    $isKnownBenignNameOnlyLolbin = ($nameValue -match $benignNameOnlyLolbinPattern) -and ($parentNameValue -match $knownBenignLolbinParentPattern)

    $isCollectorSelfRun = ($cmd -match '(?i)DCOIR_Collector\.ps1') -and ($nameValue -match '^(powershell|pwsh|cmd)(\.exe)?$')
    $isDefenderDlpUserAgent = ($nameValue -match '^(DlpUserAgent)(\.exe)?$') -and ($pathValue -match '(?i)\\ProgramData\\Microsoft\\Windows Defender\\Platform\\[^\\]+\\DlpUserAgent\.exe$')
    if ($isCollectorSelfRun -or $isDefenderDlpUserAgent) { continue }

    if ($cmd -match '(?i)(-enc\b|-encodedcommand\b|downloadstring|frombase64string|iex\b|invoke-expression\b|-w\s+hidden|-nop\b|-noni\b)') {
      [void]$reasons.Add("suspicious PowerShell style command line")
    }
    if ($cmd -match '(?i)(mshta\.exe.*http|regsvr32\.exe.*(http|scrobj)|rundll32\.exe.*(appdata|temp|programdata)|wscript\.exe|cscript\.exe|wmic(?:\.exe)?["\s]+.*(process\s+call\s+create|/node:))') {
      [void]$reasons.Add("suspicious LOLBin usage")
    }
    if ($pathValue -match '(?i)\\AppData\\|\\Temp\\|\\ProgramData\\') {
      [void]$reasons.Add("process running from high-risk path")
    }
    if ($nameValue -match $nameOnlyLolbinPattern) {
      if (-not $isKnownBenignNameOnlyLolbin -or @($reasons).Count -gt 0) {
        [void]$reasons.Add("living-off-the-land process")
      }
    }

    if (@($reasons).Count -gt 0) {
      [void]$findings.Add([pscustomobject]@{
        ProcessId = $proc.ProcessId
        ParentProcessId = $proc.ParentProcessId
        ParentProcessName = $proc.ParentProcessName
        Name = $proc.Name
        ExecutablePath = $proc.ExecutablePath
        CommandLine = $proc.CommandLine
        Reasons = ($reasons -join '; ')
      })
    }
  }
  return $findings
}

<#
.SYNOPSIS
Builds the structured TCP and UDP baseline text surface.

.DESCRIPTION
Queries Get-NetTCPConnection and Get-NetUDPEndpoint, formats both views, and returns the
combined text block.

.FUNCTION NAME
Get-BaselineNetText

.INPUTS
No direct parameters.

.OUTPUTS
String containing structured TCP and UDP text or an error message.
#>
function Get-BaselineNetText {
  try {
    $tcp = Get-NetTCPConnection -ErrorAction Stop |
      Sort-Object State, OwningProcess, LocalAddress, LocalPort |
      Select-Object State, LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess
    $udp = Get-NetUDPEndpoint -ErrorAction Stop |
      Sort-Object OwningProcess, LocalAddress, LocalPort |
      Select-Object LocalAddress, LocalPort, OwningProcess
    $text = @()
    $text += "TCP CONNECTIONS"
    $text += ($tcp | Format-Table -AutoSize | Out-String -Width 500)
    $text += ""
    $text += "UDP ENDPOINTS"
    $text += ($udp | Format-Table -AutoSize | Out-String -Width 500)
    return ($text -join [Environment]::NewLine)
  } catch {
    Add-CollectorError "Failed to collect structured TCP/UDP data: $($_.Exception.Message)"
    return "ERROR: $($_.Exception.Message)"
  }
}

<#
.SYNOPSIS
Collects Microsoft Defender status text.

.DESCRIPTION
Uses Get-MpComputerStatus when available and returns a formatted Defender status block,
or a bounded explanatory/error message when unavailable.

.FUNCTION NAME
Get-DefenderStatusText

.INPUTS
No direct parameters.

.OUTPUTS
String containing Defender status text or an explanatory/error message.
#>
function Get-DefenderStatusText {
  try {
    if (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue) {
      return ((Get-MpComputerStatus | Format-List * | Out-String -Width 500).TrimEnd())
    }
    return "Get-MpComputerStatus is not available on this endpoint."
  } catch {
    Add-CollectorError "Failed to collect Defender status: $($_.Exception.Message)"
    return "ERROR: $($_.Exception.Message)"
  }
}

<#
.SYNOPSIS
Collects registry-query text with bounded absent-key handling.

.DESCRIPTION
Runs reg query for the requested registry path, returns a bounded absent-key text block
for exit code 1, and otherwise returns the combined command output text.

.FUNCTION NAME
Get-RegistryQueryText

.INPUTS
RegistryPath string and StepName string.

.OUTPUTS
String containing registry-query output or a bounded absent-key explanation.
#>
function Get-RegistryQueryText {
  param([string]$RegistryPath,[string]$StepName)

  $cmd = ('reg query "{0}"' -f $RegistryPath)
  $result = Invoke-CmdCapture -Command $cmd -StepName $StepName -AllowedExitCodes @(0,1)
  if ($result.ExitCode -eq 1) {
    $message = "Registry key absent or not readable: $RegistryPath"
    Add-CollectorNote $message
    return (@(
      "COMMAND=reg query `"$RegistryPath`""
      "EXIT_CODE=1"
      ""
      "STDOUT:"
      ""
      ""
      "STDERR:"
      $message
    ) -join [Environment]::NewLine)
  }
  return (Get-CombinedProcessOutput -Result $result)
}
