  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $script:CollectorRunId -EnrichSessionId $script:CollectorSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies production upload-safe chunk manifest behavior.

.DESCRIPTION
Reads the production chunk manifest, verifies chunk size bounds, and reconstructs the
source artifact text from chunk_paths in order.

.FUNCTION NAME
Invoke-ProductionChunkingVerification

.INPUTS
StepName string and CollectStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when production chunking fails.
#>
function Invoke-ProductionChunkingVerification {
  param([string]$StepName,[object]$CollectStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "UPLOAD_SAFE_CHUNK_MANIFEST_PATH=$($CollectStep.UploadSafeChunkManifestPath)"
  )

  if ([string]::IsNullOrWhiteSpace([string]$CollectStep.UploadSafeChunkManifestPath) -or -not (Test-Path -LiteralPath $CollectStep.UploadSafeChunkManifestPath)) {
    $message = 'Production upload-safe chunk manifest path was not emitted by the collector.'
  } else {
    $manifest = Get-Content -LiteralPath $CollectStep.UploadSafeChunkManifestPath -Raw | ConvertFrom-Json
    $artifacts = @($manifest.chunked_artifacts)
    $violations = New-Object System.Collections.ArrayList
    if (@($artifacts).Count -lt 1) { [void]$violations.Add('No chunked_artifacts were recorded in the production chunk manifest.') }
    $expectedSourceKeys = @('security_filtered','powershell_operational_filtered','taskscheduler_operational_filtered')
    $observedSourceKeys = @($artifacts | ForEach-Object { [string]$_.source_artifact_key })
    foreach ($expectedSourceKey in $expectedSourceKeys) {
      if ($observedSourceKeys -notcontains $expectedSourceKey) {
        [void]$violations.Add(('Expected production chunk source artifact was not chunked: {0}' -f $expectedSourceKey))
      }
    }
    foreach ($artifact in $artifacts) {
      $sourcePath = [string]$artifact.source_path
      $sourceKey = [string]$artifact.source_artifact_key
      $chunkPaths = @($artifact.chunk_paths)
      $lines += ("SOURCE_KEY={0}" -f $sourceKey)
      $lines += ("SOURCE_PATH={0}" -f $sourcePath)
      [void](Add-HarnessEvidenceFile -StepName $StepName -Path $sourcePath -Label ("source_{0}" -f $sourceKey))
      if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath)) {
        [void]$violations.Add(('Missing source artifact for chunk row: {0}' -f $sourceKey))
        continue
      }
      if (@($chunkPaths).Count -lt 2) { [void]$violations.Add(('Chunk count was less than 2 for oversized source: {0}' -f $sourceKey)) }
      if ([int]$artifact.chunk_count -ne @($chunkPaths).Count) { [void]$violations.Add(('Manifest chunk_count did not match listed chunk paths for: {0}' -f $sourceKey)) }
      if ([string]::IsNullOrWhiteSpace([string]$artifact.source_sha256)) { [void]$violations.Add(('Manifest source_sha256 missing for: {0}' -f $sourceKey)) }
      $rebuilt = New-Object System.IO.MemoryStream
      $chunkSha256 = @($artifact.chunk_sha256)
      if (@($chunkSha256).Count -ne @($chunkPaths).Count) { [void]$violations.Add(('Manifest chunk_sha256 count did not match chunk paths for: {0}' -f $sourceKey)) }
      $chunkIndex = 0
      foreach ($chunkPath in $chunkPaths) {
        if (-not (Test-Path -LiteralPath $chunkPath)) {
          [void]$violations.Add(('Missing chunk path: {0}' -f $chunkPath))
          continue
        }
        [void](Add-HarnessEvidenceFile -StepName $StepName -Path $chunkPath -Label ("chunk_{0}_{1:000}" -f $sourceKey, ($chunkIndex + 1)))
        $chunkSizeKB = [int][Math]::Ceiling(((Get-Item -LiteralPath $chunkPath).Length) / 1KB)
        $lines += ('CHUNK={0} SIZE_KB={1}' -f $chunkPath, $chunkSizeKB)
        if ($chunkSizeKB -gt $SafePerFileKB) { [void]$violations.Add(('Chunk exceeded safe per-file budget: {0}' -f $chunkPath)) }
        $chunkBytes = [System.IO.File]::ReadAllBytes($chunkPath)
        $actualChunkHash = (Get-FileHash -LiteralPath $chunkPath -Algorithm SHA256).Hash
        if (@($chunkSha256).Count -le $chunkIndex -or [string]::IsNullOrWhiteSpace([string]$chunkSha256[$chunkIndex])) {
          [void]$violations.Add(('Chunk SHA256 missing from manifest for: {0}' -f $chunkPath))
        } elseif ($actualChunkHash -ne [string]$chunkSha256[$chunkIndex]) {
          [void]$violations.Add(('Chunk SHA256 did not match manifest for: {0}' -f $chunkPath))
        }
        $rebuilt.Write($chunkBytes, 0, $chunkBytes.Length)
        $chunkIndex += 1
      }
      $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
      $sha = [System.Security.Cryptography.SHA256]::Create()
      try {
        $rebuiltHashBytes = $sha.ComputeHash($rebuilt.ToArray())
      } finally {
        $sha.Dispose()
      }
      $rebuiltHash = (($rebuiltHashBytes | ForEach-Object { $_.ToString('x2') }) -join '').ToUpperInvariant()
      $lines += ('SOURCE_SHA256={0}' -f $sourceHash)
      $lines += ('REBUILT_SHA256={0}' -f $rebuiltHash)
      if ($rebuiltHash -ne $sourceHash) { [void]$violations.Add(('Chunk byte reconstruction hash did not match source artifact: {0}' -f $sourceKey)) }
      if ([string]::IsNullOrWhiteSpace([string]$artifact.source_sha256)) {
        [void]$violations.Add(('Manifest source SHA256 missing for source artifact: {0}' -f $sourceKey))
      } elseif ([string]$artifact.source_sha256 -ne $sourceHash) {
        [void]$violations.Add(('Manifest source SHA256 did not match source artifact: {0}' -f $sourceKey))
      }
    }
    if (@($violations).Count -eq 0) {
      $status = 'PASS'
      $message = 'Production upload-safe chunks stayed within size budget and reconstructed source artifacts exactly.'
    } else {
      $message = ($violations -join '; ')
    }
  }

  $lines += "STATUS=$status"
  $lines += "MESSAGE=$message"
  $end = Get-Date
  $logPath = Write-HarnessLog -StepName $StepName -Lines $lines
  Add-Result -StepName $StepName -Status $status -ExitCode ($(if($status -eq 'PASS'){0}else{1})) -RunId $script:CollectorRunId -EnrichSessionId $script:CollectorSessionId -CollectorReportedStatus $null -LogPath $logPath -Start $start -End $end
  if ($status -ne 'PASS' -and -not $ContinueOnError) { throw $message }
}

<#
.SYNOPSIS
Verifies oversized-artifact chunking behavior.

.DESCRIPTION
Checks that the synthetic oversized artifact exceeded the hard per-file threshold, was
split into multiple chunk files, and that each chunk stayed within the safe per-file
budget.

.FUNCTION NAME
Invoke-ChunkingOversizeVerification

.INPUTS
StepName string and CollectStep result object.

.OUTPUTS
No direct return value beyond harness logging; throws when chunking expectations fail.
#>
function Invoke-ChunkingOversizeVerification {
  param([string]$StepName,[object]$CollectStep)
  $start = Get-Date
  $status = 'FAIL'
  $message = ''
  $lines = @(
    "STEP=$StepName",
    "SYNTHETIC_OVERSIZE_SOURCE_PATH=$($CollectStep.SyntheticOversizeSourcePath)",
    "CHUNK_MANIFEST_PATH=$($CollectStep.ChunkManifestPath)"
  )

  if ([string]::IsNullOrWhiteSpace([string]$CollectStep.SyntheticOversizeSourcePath) -or -not (Test-Path -LiteralPath $CollectStep.SyntheticOversizeSourcePath)) {
    $message = 'Synthetic oversize source artifact was not emitted by the collector.'
  } elseif ([string]::IsNullOrWhiteSpace([string]$CollectStep.ChunkManifestPath) -or -not (Test-Path -LiteralPath $CollectStep.ChunkManifestPath)) {
    $message = 'Chunk manifest path was not emitted by the collector.'
  } else {
    $manifest = Get-Content -LiteralPath $CollectStep.ChunkManifestPath -Raw | ConvertFrom-Json
    $chunkPaths = @($manifest.chunk_paths)
    $sourceSizeKB = [int]$manifest.source_size_kb
    $chunkCount = [int]$manifest.chunk_count
    $violations = New-Object System.Collections.ArrayList
    if ($sourceSizeKB -le $HardPerFileKB) { [void]$violations.Add('Synthetic source artifact did not exceed the hard per-file budget.') }
    if ($chunkCount -lt 2) { [void]$violations.Add('Chunk count was less than 2 for the oversized artifact.') }
    foreach ($chunkPath in $chunkPaths) {
