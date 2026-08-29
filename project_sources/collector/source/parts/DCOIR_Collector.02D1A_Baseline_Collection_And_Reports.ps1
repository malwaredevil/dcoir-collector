<#
.SYNOPSIS
DCOIR collector baseline report follow-up recommendation helpers.

.DESCRIPTION
Adds suspicious-process follow-up guidance for the baseline report while keeping the
main baseline report writer compact enough for GitHub connector-safe updates.

.FILE NAME
DCOIR_Collector.02D1A_Baseline_Collection_And_Reports.ps1

.INPUTS
Collector state, output root, process inventory, and excluded process IDs.

.OUTPUTS
No direct output. Updates the global recommended-action queue.
#>

<#
.SYNOPSIS
Adds suspicious-process follow-up recommendations for baseline collection.

.DESCRIPTION
Runs suspicious-process heuristics, records triage recommendations, and emits suggested
enrichment commands for executable paths that warrant analyst follow-up.

.FUNCTION NAME
Add-BaselineSuspiciousProcessRecommendations

.INPUTS
Collector State hashtable, OutRoot string, Processes array, and ExcludedPids array.

.OUTPUTS
No direct output. Updates global recommendation state.
#>
function Add-BaselineSuspiciousProcessRecommendations {
  [CmdletBinding()]
  param(
    [hashtable]$State,
    [string]$OutRoot,
    [object[]]$Processes,
    [int[]]$ExcludedPids
  )

  $findings = Get-SuspiciousProcessFindings -Processes $Processes -ExcludedPids $ExcludedPids
  $collectorCommandBase = Get-CollectorPowerShellCommandBase
  if (@($findings).Count -gt 0) {
    Add-Recommendation 'The following process review candidates were selected by baseline heuristics. Treat them as triage prompts for analyst validation, not proof of malicious activity.'
    foreach ($finding in ($findings | Select-Object -First 10)) {
      $parentLabel = ""
      if ($null -ne $finding.ParentProcessId -or -not [string]::IsNullOrWhiteSpace([string]$finding.ParentProcessName)) {
        $parentName = if (-not [string]::IsNullOrWhiteSpace([string]$finding.ParentProcessName)) { [string]$finding.ParentProcessName } else { "unknown" }
        $parentPid = if ($null -ne $finding.ParentProcessId) { [string]$finding.ParentProcessId } else { "unknown" }
        $parentLabel = " parent={0} ({1})" -f $parentName, $parentPid
      }
      Add-Recommendation ("Process review candidate PID {0} ({1}){2} :: heuristic flags: {3}" -f $finding.ProcessId, $finding.Name, $parentLabel, $finding.Reasons)
      if ($finding.ExecutablePath) {
        $safePath = $finding.ExecutablePath
        Add-Recommendation ('Suggested next action if analyst review warrants deeper validation: {0} -Mode Enrich -RunId {1} -Action SigcheckPath -Path "{2}" -OutRoot "{3}"' -f $collectorCommandBase, $State.RunId, $safePath, $OutRoot)
        Add-Recommendation ('Suggested next action if analyst review warrants deeper validation: {0} -Mode Enrich -RunId {1} -Action StringsPath -Path "{2}" -OutRoot "{3}"' -f $collectorCommandBase, $State.RunId, $safePath, $OutRoot)
        Add-Recommendation ('Suggested next action if analyst review warrants file retrieval: {0} -Mode Enrich -RunId {1} -Action PullSuspiciousFile -Path "{2}" -OutRoot "{3}"' -f $collectorCommandBase, $State.RunId, $safePath, $OutRoot)
      }
    }
  } else {
    Add-Recommendation 'No heuristic-driven process review candidates were generated from baseline collection.'
  }
}
