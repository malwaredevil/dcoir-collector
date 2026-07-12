<#
.SYNOPSIS
DCOIR collector main entry dispatcher.

.DESCRIPTION
Applies quick shortcuts, handles help/version requests, resolves safe package and run identifiers, initializes the output root, and dispatches to the collect, enrich, or cleanup entry helper loaded immediately before this file.

.FILE NAME
DCOIR_Collector.05_Main_Entry.ps1

.INPUTS
Collector command-line parameters and script-scoped runtime state initialized by the wrapper.

.OUTPUTS
Mode-specific status output from the invoked entry helper, or error status output when dispatch fails.
#>

Apply-QuickShortcut

if ($ShowVersion) {
  Write-Output (Get-CollectorVersionText)
  return
}

if ($ShowHelp) {
  Write-Output (Get-CollectorHelpText -Topic $script:ContextualHelpTopic)
  return
}

try {
  $PackageName = Resolve-DCOIRPackageName -CurrentPackageName $PackageName
  $RunId = Resolve-DCOIRRunId -CurrentRunId $RunId -GenerateIfBlank:($Mode -eq "Collect") -RejectBlank:$script:DCOIRRunIdParameterWasBound
  $Global:CurrentPackageName = $PackageName

  if (-not $WhatIfPreference) {
    Ensure-Directory -Path $OutRoot
  }

  switch ($Mode) {
    "Collect" {
      Invoke-DCOIRCollectMode
      return
    }

    "Enrich" {
      Invoke-DCOIREnrichMode
      return
    }

    "Cleanup" {
      Invoke-DCOIRCleanupMode
      return
    }
  }
} catch {
  Add-CollectorError $_.Exception.Message
  Write-Output ("STATUS=ERROR")
  Write-Output ("MESSAGE={0}" -f $_.Exception.Message)
  exit 1
}
