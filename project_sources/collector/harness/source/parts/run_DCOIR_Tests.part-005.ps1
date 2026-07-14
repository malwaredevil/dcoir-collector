
<#
.SYNOPSIS
Verifies Tier 2-specific bounded collect output.

.DESCRIPTION
Checks the collect bundle for Tier 2 deep-check artifacts and confirms the run metadata
records the bounded collection window used by the harness.

.FUNCTION NAME
Invoke-Tier2CollectVerification

.INPUTS
StepName string, CollectStep result object, expected Hours, and expected MaxEvents.

.OUTPUTS
No direct return value beyond harness logging; throws when Tier 2 evidence is absent.
#>
function Invoke-Tier2CollectVerification {
  param([string]$StepName,[object]$CollectStep,[int]$ExpectedHours = 1,[int]$ExpectedMaxEvents = 100)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $zipPath = $CollectStep.CollectBundlePath
  if ([string]::IsNullOrWhiteSpace($zipPath) -and -not [string]::IsNullOrWhiteSpace($CollectStep.NextGetFile)) {
    $m = [regex]::Match($CollectStep.NextGetFile, '--path\s+"([^"]+)"')
    if ($m.Success) { $zipPath = $m.Groups[1].Value }
  }

  $requiredEntries = [ordered]@{
    tier2_reg_ifeo = 'TIER2_DEEP_CHECKS/.*tier2_reg_ifeo\.txt$'
    tier2_reg_winlogon = 'TIER2_DEEP_CHECKS/.*tier2_reg_winlogon\.txt$'
    tier2_reg_lsa = 'TIER2_DEEP_CHECKS/.*tier2_reg_lsa\.txt$'
    tier2_wmi_persistence = 'TIER2_DEEP_CHECKS/.*tier2_wmi_persistence\.txt$'
    tier2_net_share = 'TIER2_DEEP_CHECKS/.*tier2_net_share\.txt$'
    tier2_net_session = 'TIER2_DEEP_CHECKS/.*tier2_net_session\.txt$'
    tier2_firewall_profiles = 'TIER2_DEEP_CHECKS/.*tier2_firewall_profiles\.txt$'
  }
  $missing = New-Object System.Collections.ArrayList
  $found = New-Object System.Collections.ArrayList
  $metadataText = ''

  if ([string]::IsNullOrWhiteSpace($zipPath) -or -not (Test-Path -LiteralPath $zipPath)) {
    [void]$missing.Add('collect bundle path missing or not found')
  } else {
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
      $entryNames = @($archive.Entries | ForEach-Object { $_.FullName -replace '\\','/' })
      foreach ($key in $requiredEntries.Keys) {
        $pattern = $requiredEntries[$key]
        if (@($entryNames | Where-Object { $_ -match $pattern }).Count -gt 0) {
          [void]$found.Add($key)
        } else {
          [void]$missing.Add("missing $key artifact")
        }
      }

      $metadataEntry = @($archive.Entries | Where-Object { ($_.FullName -replace '\\','/') -match 'COLLECTION_METADATA/.*collection_metadata\.txt$' } | Select-Object -First 1)
      if (@($metadataEntry).Count -eq 0) {
        [void]$missing.Add('collection metadata artifact missing')
      } else {
        $reader = New-Object System.IO.StreamReader($metadataEntry[0].Open())
        try { $metadataText = $reader.ReadToEnd() } finally { $reader.Dispose() }
        if ($metadataText -notmatch '(?m)^Tier=T2$') { [void]$missing.Add('metadata Tier=T2 missing') }
        if ($metadataText -notmatch ('(?m)^Hours={0}$' -f [regex]::Escape([string]$ExpectedHours))) { [void]$missing.Add("metadata Hours=$ExpectedHours missing") }
        if ($metadataText -notmatch ('(?m)^MaxEvents={0}$' -f [regex]::Escape([string]$ExpectedMaxEvents))) { [void]$missing.Add("metadata MaxEvents=$ExpectedMaxEvents missing") }
      }
    } finally {
      $archive.Dispose()
    }
  }

  if (@($missing).Count -eq 0) {
    $status = 'PASS'
    $message = 'Tier 2 bounded collect artifacts and metadata were emitted.'
  } else {
    $message = (@($missing) -join '; ')
  }

  $lines = @(
    "STEP=$StepName",
    "RUN_ID=$($CollectStep.RunId)",
    "COLLECT_BUNDLE_PATH=$zipPath",
    "EXPECTED_TIER=T2",
    "EXPECTED_HOURS=$ExpectedHours",
    "EXPECTED_MAX_EVENTS=$ExpectedMaxEvents",
    "FOUND_TIER2_ARTIFACTS=$(@($found) -join ',')",
    "STATUS=$status",
    "MESSAGE=$message"
  )
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $CollectStep.RunId -EnrichSessionId $CollectStep.EnrichSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

