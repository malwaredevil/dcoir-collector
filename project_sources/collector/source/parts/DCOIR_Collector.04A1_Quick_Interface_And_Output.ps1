<#
.SYNOPSIS
DCOIR collector quick-interface, help-text, and cleanup helpers.

.DESCRIPTION
Builds the operator-facing quick-command examples and help text, translates supported
-Quick shortcuts into full collector parameter sets, prints next-step guidance after
major phases, and removes run/package artifacts during cleanup.

.FILE NAME
DCOIR_Collector.04A1_Quick_Interface_And_Output.ps1

.INPUTS
Collector runtime globals such as Quick, Target, Target2, Hours, and the current state
object passed to cleanup.

.OUTPUTS
Strings for help/usage and next-step guidance, updated collector runtime parameters for
quick shortcuts, and cleanup side effects on package/run paths.
#>

<#
.SYNOPSIS
Builds the short quick-command usage text.

.DESCRIPTION
Returns the operator-facing quick-command examples used by the collector help surface.

.FUNCTION NAME
Get-QuickUsageText

.INPUTS
No direct parameters.

.OUTPUTS
String containing newline-joined quick-command examples.
#>
function Get-QuickUsageText {
  $cmd = Get-CollectorPowerShellCommandBase
  return @(
    "Quick command examples:",
    "  $cmd -Quick collect-t1",
    "  $cmd -Quick collect-t2",
    '  $cmd -Quick collect-targeted-popup -Target "User reported popup around 2026-04-08T09:00Z"',
    '  $cmd -Quick collect-targeted-script -Target "Suspicious script execution follow-up" -Target2 "powershell.exe"',
    "  $cmd -Quick enrich-start-tcp",
    "  $cmd -Quick enrich-add-tcp",
    "  $cmd -Quick enrich-start-logtext -Target Security",
    "  $cmd -Quick enrich-add-logtext -Target Security",
    "  $cmd -Quick enrich-start-lograw -Target Security",
    "  $cmd -Quick enrich-add-lograw -Target Security",
    "  $cmd -Quick enrich-start-sigcheck -Target C:\Windows\System32\notepad.exe",
    "  $cmd -Quick enrich-add-sigcheck -Target C:\Windows\System32\notepad.exe",
    "  $cmd -Quick enrich-start-listdlls -Target 1234",
    "  $cmd -Quick enrich-add-listdlls -Target 1234",
    "  $cmd -Quick enrich-finalize",
    "  $cmd -Quick cleanup",
    "  $cmd -Quick help-collect",
    "  $cmd -Quick help-enrich",
    "  $cmd -Quick help-cleanup",
    "  $cmd -Quick help-targeted",
    "  $cmd -Quick help-version"
  ) -join [Environment]::NewLine
}

<#
.SYNOPSIS
Builds the collector build-identity string.

.DESCRIPTION
Returns the transport/runtime identity string used by version output and validation.

.FUNCTION NAME
Get-CollectorBuildIdentity

.INPUTS
Optional version string.

.OUTPUTS
String build identity.
#>
function Get-CollectorBuildIdentity {
  param([string]$Version = $ScriptVersion)
  return ("DCOIR_Collector.ps1/{0}" -f $Version)
}

<#
.SYNOPSIS
Builds the collector version text block.

.DESCRIPTION
Returns the collector version, build identity, runtime filename, package name, and
script path in key-value form.

.FUNCTION NAME
Get-CollectorVersionText

.INPUTS
No direct parameters.

.OUTPUTS
String containing newline-joined version/build metadata.
#>
function Get-CollectorVersionText {
  $scriptPath = Get-CollectorAbsolutePath
  $resolvedPackageName = if ([string]::IsNullOrWhiteSpace($PackageName)) { "DCOIR_Collector.zip" } else { $PackageName }
  return @(
    ("COLLECTOR_VERSION={0}" -f $ScriptVersion),
    ("COLLECTOR_BUILD_IDENTITY={0}" -f (Get-CollectorBuildIdentity)),
    "COLLECTOR_RUNTIME_FILENAME=DCOIR_Collector.ps1",
    ("EXPECTED_PACKAGE_NAME={0}" -f $resolvedPackageName),
    ("COLLECTOR_SCRIPT_PATH={0}" -f $scriptPath)
  ) -join [Environment]::NewLine
}

<#
.SYNOPSIS
Builds the delete-script command text.

.DESCRIPTION
Returns the response-action-safe literal-path script-removal command for the uploaded
collector file.

.FUNCTION NAME
Get-CollectorDeleteScriptCommandText

.INPUTS
No direct parameters.

.OUTPUTS
String delete-script command.
#>
function Get-CollectorDeleteScriptCommandText {
  $collectorPath = Get-CollectorAbsolutePath
  return ('execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command Remove-Item -LiteralPath ''{0}'' -Force" --comment "Remove uploaded DCOIR_Collector script"' -f $collectorPath)
}

<#
.SYNOPSIS
Builds contextual collector help for a specific workflow area.

.DESCRIPTION
Returns a narrower help block for collect, enrich, cleanup, targeted, or version guidance
when the operator asks for area-specific help.

.FUNCTION NAME
Get-CollectorContextualHelpText

.INPUTS
Optional topic string.

.OUTPUTS
String containing newline-joined contextual help text.
#>
function Get-CollectorContextualHelpText {
  param([string]$Topic)

  $cmd = Get-CollectorPowerShellCommandBase
  $responseCmd = Get-CollectorResponseActionCommandBase
  $topicKey = if ([string]::IsNullOrWhiteSpace($Topic)) { 'general' } else { $Topic.ToLowerInvariant() }
  $lines = @()

  switch ($topicKey) {
    'collect' {
      $lines += 'DCOIR Collector Contextual Help - Collect'
      $lines += ''
      $lines += 'Use this when you need a baseline collection bundle.'
      $lines += 'Recommended first commands:'
      $lines += "  $cmd -Quick collect-t1"
      $lines += "  $cmd -Quick collect-t2"
      $lines += ''
      $lines += 'Response-action-safe examples:'
      $lines += ('  execute --command "{0} -Quick collect-t1" --comment "Run DCOIR collect T1"' -f $responseCmd)
      $lines += ('  execute --command "{0} -Quick collect-t2" --comment "Run DCOIR collect T2"' -f $responseCmd)
      $lines += ''
      $lines += 'Use T1 when you want the smaller baseline-first path.'
      $lines += 'Use T2 when you need the deeper persistence and investigative path.'
      $lines += 'Run -Version first if you are validating a specific PS1/ZIP pair.'
    }
    'enrich' {
      $lines += 'DCOIR Collector Contextual Help - Enrich'
      $lines += ''
      $lines += 'Use this when you already have a run id and want targeted follow-up collection.'
      $lines += 'Session pattern:'
      $lines += "  $cmd -Quick enrich-start-tcp"
      $lines += "  $cmd -Quick enrich-add-lograw -Target Security"
      $lines += "  $cmd -Quick enrich-finalize"
      $lines += ''
      $lines += 'Response-action-safe examples:'
      $lines += ('  execute --command "{0} -Quick enrich-start-tcp" --comment "Run DCOIR TCP enrichment"' -f $responseCmd)
      $lines += ('  execute --command "{0} -Quick enrich-add-lograw -Target Security" --comment "Add raw Security log enrichment"' -f $responseCmd)
      $lines += ('  execute --command "{0} -Quick enrich-finalize" --comment "Finalize current DCOIR enrichment session"' -f $responseCmd)
      $lines += ''
      $lines += 'Start a session once, add related actions to the same session, then finalize before cleanup.'
    }
    'cleanup' {
      $lines += 'DCOIR Collector Contextual Help - Cleanup'
      $lines += ''
      $lines += 'Cleanup removes the run root and consumed package state.'
      $lines += 'If a collect run failed before state.json was saved, cleanup removes only the latest matching DCOIR_* orphan under the selected OutRoot and reports MISSING_STATE_ORPHAN_CLEANED.'
      $lines += 'Cleanup reports NO_TARGET_FOUND when no state-backed run or bounded orphan cleanup target exists.'
      $lines += 'Cleanup reports SKIPPED when WhatIf or confirmation handling leaves all state-backed targets in place.'
      $lines += 'Cleanup does not remove the uploaded collector script unless you run DELETE_SCRIPT_COMMAND explicitly.'
      $lines += ''
      $lines += 'Response-action-safe example:'
      $lines += ('  execute --command "{0} -Quick cleanup" --comment "Running Cleanup on DCOIR_Collector"' -f $responseCmd)
      $lines += ''
      $lines += 'If you plan another collect-style run in the response-action lane, restage the runtime zip first.'
    }
    'targeted' {
      $lines += 'DCOIR Collector Contextual Help - Targeted'
      $lines += ''
      $lines += 'Use targeted mode when the operator has a narrower event window, user report, process, path, or indicator.'
      $lines += 'Examples:'
      $lines += "  $cmd -Quick collect-targeted-popup -Target ""User reported popup around 2026-04-08T09:00Z"""
      $lines += "  $cmd -Quick collect-targeted-script -Target ""Suspicious script execution follow-up"" -Target2 ""powershell.exe"""
      $lines += ''
      $lines += 'Pair targeted mode with WindowStart/WindowEnd and the most specific focus fields you have.'
      $lines += 'Targeted mode narrows guidance and prioritization even when full exact-time filtering is not universal yet.'
    }
    'version' {
      $lines += 'DCOIR Collector Contextual Help - Version'
      $lines += ''
      $lines += 'Use version preflight before collect, enrich, cleanup, or package movement when you need to prove the runtime identity.'
      $lines += 'Examples:'
      $lines += "  $cmd -Version"
      $lines += ('  execute --command "{0} -Version" --comment "Get DCOIR collector version"' -f $responseCmd)
      $lines += ''
      $lines += 'Compare COLLECTOR_VERSION, COLLECTOR_BUILD_IDENTITY, and EXPECTED_PACKAGE_NAME before live validation.'
    }
    default {
      return $null
    }
  }

  return ($lines -join [Environment]::NewLine)
}

<#
.SYNOPSIS
Builds the full collector help text.

.DESCRIPTION
Returns the operator-facing help text including top-level usage, quick shortcuts,
version/build preflight guidance, targeted examples, and lane guidance.

.FUNCTION NAME
Get-CollectorHelpText

.INPUTS
Optional topic string.

.OUTPUTS
String containing newline-joined help text.
#>
function Get-CollectorHelpText {
  param([string]$Topic)

  $contextual = Get-CollectorContextualHelpText -Topic $Topic
  if (-not [string]::IsNullOrWhiteSpace($contextual)) {
    return $contextual
  }

  $cmd = Get-CollectorPowerShellCommandBase
  $responseCmd = Get-CollectorResponseActionCommandBase
  $lines = @()
  $lines += "DCOIR Collector Help"
  $lines += ""
  $lines += "Top-level usage:"
  $lines += "  $cmd -Help"
  $lines += "  $cmd -Version"
  $lines += "  $cmd -Mode Collect -Tier T1"
  $lines += "  $cmd -Mode Collect -Tier T2"
  $lines += "  $cmd -Mode Enrich -Action TcpvconRefresh -NewEnrichSession"
  $lines += "  $cmd -Mode Cleanup"
  $lines += ""
  $lines += "Quick usage:"
  $lines += (Get-QuickUsageText)
  $lines += ""
  $lines += "Contextual help shortcuts:"
  $lines += "  $cmd -Quick help-collect"
  $lines += "  $cmd -Quick help-enrich"
  $lines += "  $cmd -Quick help-cleanup"
  $lines += "  $cmd -Quick help-targeted"
  $lines += "  $cmd -Quick help-version"
  $lines += ""
  $lines += "Accepted top-level modes: Collect, Enrich, Cleanup"
  $lines += "Accepted tiers: T1, T2"
  $lines += "Accepted target profiles: Generic, PopupWindow, ScriptExecution, PersistenceFollowUp, NetworkOnly, ProcessAndPowerShell"
  $lines += ""
  $lines += "Version/build preflight:"
  $lines += "  - Run -Version before collect, enrich, cleanup, package movement, or other stateful test steps."
  $lines += "  - Compare COLLECTOR_VERSION and COLLECTOR_BUILD_IDENTITY to the PS1/ZIP you intended to validate before continuing."
  $lines += ('  - Response-action-safe example: execute --command "{0} -Version" --comment "Get DCOIR collector version"' -f $responseCmd)
  $lines += ""
  $lines += "Targeted usage examples:"
  $lines += '  $cmd -Targeted -TargetProfile PopupWindow -WindowStart "2026-04-08T09:00:00Z" -WindowEnd "2026-04-08T10:00:00Z" -UserReport "User reported popup"'
  $lines += '  $cmd -Targeted -TargetProfile ScriptExecution -WindowStart "2026-04-08T09:00:00Z" -WindowEnd "2026-04-08T10:00:00Z" -UserReport "Suspicious script execution" -FocusProcess "powershell.exe"'
  $lines += '  $cmd -Targeted -TargetProfile NetworkOnly -Hours 6 -FocusIndicator "198.51.100.25" -FocusIndicatorType "ip"'
  $lines += ""
  $lines += "Targeted guidance:"
  $lines += "  - Targeted mode currently narrows guidance, scope intent, artifact prioritization, and next actions."
  $lines += "  - It does not yet rewrite every baseline helper into exact start/end filtering across all artifact families."
  $lines += "  - Use -WindowStart and -WindowEnd to annotate explicit time windows for analyst guidance and follow-up."
  $lines += "  - Use -IncludeArtifactCategory, -FocusProcess, -FocusPath, -FocusIndicator, and -UserReport to make the request narrower and more explainable."
  $lines += ""
  $lines += "Accepted enrich actions:"
  $lines += "  SigcheckPath, ListDllsPid, AccessChkFile, AccessChkService, AccessChkReg, StringsPath, StreamsPath, TcpvconRefresh, LogText, LogRaw, PullSuspiciousFile, PullScriptOrConfig, PullTaskXml, PullServiceBinary, PullWmiReferencedFile"
  $lines += ""
  $lines += "Lane guidance:"
  $lines += "  - Endpoint response-console usage should wrap the PowerShell command in an Elastic response action."
  $lines += "  - Use the response-action-safe runtime pattern with doubled double quotes around .\DCOIR_Collector.ps1 inside the execute --command string."
  $lines += "  - Use the collector-emitted DELETE_SCRIPT_COMMAND literal-path form for script removal in the response-action lane."
  $lines += "  - Local workstation and regression usage should run the PowerShell command directly without the response-action wrapper."
  $lines += "  - Prefer PowerShell 5.1 syntax and the runtime filename DCOIR_Collector.ps1."
  return ($lines -join [Environment]::NewLine)
}
