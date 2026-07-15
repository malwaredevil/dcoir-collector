Checks that the collect step emitted the required post-run contract fields such as
RUN_ID, NEXT_GET_FILE, cleanup command, delete-script command, and Gemini upload
guidance.

.FUNCTION NAME
Invoke-CollectOutputContractVerification

.INPUTS
StepName string and CollectStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when the contract is incomplete.
#>
function Invoke-CollectOutputContractVerification {
  param([string]$StepName,[object]$CollectStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "RUN_ID=$($CollectStep.RunId)",
    "NEXT_GET_FILE=$($CollectStep.NextGetFile)",
    "CLEANUP_COMMAND=$($CollectStep.CleanupCommand)",
    "DELETE_SCRIPT_COMMAND=$($CollectStep.DeleteScriptCommand)",
    "GEMINI_UPLOAD_GUIDANCE=$($CollectStep.GeminiUploadGuidance)",
    "HAS_QUICK_COMMANDS=$($CollectStep.HasQuickCommands)"
  )

  $missing = New-Object System.Collections.ArrayList
  if ([string]::IsNullOrWhiteSpace($CollectStep.RunId)) { [void]$missing.Add('RUN_ID missing') }
  if ([string]::IsNullOrWhiteSpace($CollectStep.NextGetFile)) { [void]$missing.Add('NEXT_GET_FILE missing') }
  if ([string]::IsNullOrWhiteSpace($CollectStep.CleanupCommand)) { [void]$missing.Add('CLEANUP_COMMAND missing') }
  if ([string]::IsNullOrWhiteSpace($CollectStep.DeleteScriptCommand)) { [void]$missing.Add('DELETE_SCRIPT_COMMAND missing') }
  if ([string]::IsNullOrWhiteSpace($CollectStep.GeminiUploadGuidance)) { [void]$missing.Add('GEMINI_UPLOAD_GUIDANCE missing') }

  if (@($missing).Count -eq 0) {
    $status = 'PASS'
    $message = 'Collect output contract fields were emitted.'
  } else {
    $message = (@($missing) -join '; ')
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $CollectStep.RunId -EnrichSessionId $CollectStep.EnrichSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies that the collect ZIP contains the exact on-disk collect manifest.

.DESCRIPTION
Resolves the generated collect bundle, locates the run-root manifest_collect.json,
finds the single bundled manifest_collect.json entry, compares both byte arrays, and
retains bounded evidence so workflow artifacts can prove the comparison without runner
transient paths.

.FUNCTION NAME
Invoke-CollectManifestBundleComparison

.INPUTS
StepName string and CollectStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when manifest evidence is absent or mismatched.
#>
function Invoke-CollectManifestBundleComparison {
  param([string]$StepName,[object]$CollectStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $missing = New-Object System.Collections.ArrayList
  $manifestMatches = $false
  $diskManifestPath = $null
  $bundledManifestEvidencePath = $null
  $manifestEvidencePath = $null
  $bundledManifestEntryName = $null
  $diskManifestByteCount = $null
  $bundledManifestByteCount = $null
  $zipPath = $CollectStep.CollectBundlePath
  if ([string]::IsNullOrWhiteSpace($zipPath) -and -not [string]::IsNullOrWhiteSpace($CollectStep.NextGetFile)) {
    $m = [regex]::Match($CollectStep.NextGetFile, '--path\s+"([^"]+)"')
    if ($m.Success) { $zipPath = $m.Groups[1].Value }
  }

  if ([string]::IsNullOrWhiteSpace($zipPath) -or -not (Test-Path -LiteralPath $zipPath)) {
    [void]$missing.Add('collect bundle path missing or not found')
  } else {
    $bundleDir = Split-Path -Parent $zipPath
    $runRoot = if ([string]::IsNullOrWhiteSpace($bundleDir)) { $null } else { Split-Path -Parent $bundleDir }
    if (-not [string]::IsNullOrWhiteSpace($runRoot)) {
      $candidateManifest = Join-Path $runRoot 'manifest_collect.json'
      if (Test-Path -LiteralPath $candidateManifest) { $diskManifestPath = $candidateManifest }
    }
    if ([string]::IsNullOrWhiteSpace($diskManifestPath)) {
      [void]$missing.Add('on-disk manifest_collect.json missing')
    }

    if ([string]::IsNullOrWhiteSpace($diskManifestPath)) {
      $diskBytes = $null
    } else {
      $diskBytes = [System.IO.File]::ReadAllBytes($diskManifestPath)
      $diskManifestByteCount = $diskBytes.Length
      $manifestEvidencePath = Add-HarnessEvidenceFile -StepName $StepName -Path $diskManifestPath -Label 'on_disk_manifest_collect'
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
    $archive = $null
    try {
      $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
      $manifestEntries = @($archive.Entries | Where-Object { (($_.FullName -replace '\\','/') -split '/')[-1] -eq 'manifest_collect.json' })
      if (@($manifestEntries).Count -ne 1) {
        [void]$missing.Add(('expected exactly one bundled manifest_collect.json; found {0}' -f @($manifestEntries).Count))
      } else {
        $entry = $manifestEntries[0]
        $bundledManifestEntryName = $entry.FullName
        $stream = $entry.Open()
        $memory = New-Object System.IO.MemoryStream
        try {
          $stream.CopyTo($memory)
          $bundledBytes = $memory.ToArray()
          $bundledManifestByteCount = $bundledBytes.Length
        } finally {
          $memory.Dispose()
          $stream.Dispose()
        }

        Ensure-Directory -Path $EvidenceRoot
        $safeStep = ($StepName -replace '[\\/:*?"<>| ]','_')
        $stepDir = Join-Path $EvidenceRoot $safeStep
        Ensure-Directory -Path $stepDir
        $bundledManifestEvidencePath = Join-Path $stepDir 'bundled_manifest_collect.json'
        [System.IO.File]::WriteAllBytes($bundledManifestEvidencePath, $bundledBytes)

        if ($null -ne $diskBytes) {
          if ($diskBytes.Length -eq $bundledBytes.Length) {
            $manifestMatches = $true
            for ($i = 0; $i -lt $diskBytes.Length; $i++) {
              if ($diskBytes[$i] -ne $bundledBytes[$i]) {
                $manifestMatches = $false
                break
              }
            }
          }
          if (-not $manifestMatches) { [void]$missing.Add('bundled manifest_collect.json bytes differ from on-disk manifest_collect.json') }
        }
      }
    } finally {
      if ($null -ne $archive) { $archive.Dispose() }
    }
  }

  if (@($missing).Count -eq 0) {
    $status = 'PASS'
    $message = 'Bundled manifest_collect.json matches on-disk manifest_collect.json byte-for-byte.'
  } else {
    $message = (@($missing) -join '; ')
  }

  $lines = @(
    "STEP=$StepName",
    "RUN_ID=$($CollectStep.RunId)",
    "COLLECT_BUNDLE_PATH=$zipPath",
    "ON_DISK_MANIFEST_PATH=$diskManifestPath",
    "ON_DISK_MANIFEST_EVIDENCE_PATH=$manifestEvidencePath",
    "BUNDLED_MANIFEST_ENTRY=$bundledManifestEntryName",
    "BUNDLED_MANIFEST_EVIDENCE_PATH=$bundledManifestEvidencePath",
    "ON_DISK_MANIFEST_BYTE_COUNT=$diskManifestByteCount",
    "BUNDLED_MANIFEST_BYTE_COUNT=$bundledManifestByteCount",
    "MANIFEST_BYTE_MATCH=$manifestMatches",
    "STATUS=$status",
    "MESSAGE=$message"
  )
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $CollectStep.RunId -EnrichSessionId $CollectStep.EnrichSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}
