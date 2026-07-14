[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$HarnessOutputRoot,

  [Parameter(Mandatory = $true)]
  [string]$SelectedSuite,

  [string]$SummaryJsonPath,

  [string]$JsonOutputPath,

  [string]$MarkdownOutputPath
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Write-OptionalFile {
  param(
    [string]$Path,
    [string[]]$Lines
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return
  }

  $parent = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
  }

  Set-Content -LiteralPath $Path -Value $Lines -Encoding utf8
}

if ($SelectedSuite -ne 'FullRegression') {
  $skipLines = @(
    '# DCOIR Collector Mission Readiness Gate',
    '',
    ('Status: skipped'),
    ('Selected suite: {0}' -f $SelectedSuite),
    '',
    'The mission-readiness gate only applies when the selected suite is FullRegression.'
  )
  Write-OptionalFile -Path $MarkdownOutputPath -Lines $skipLines
  if (-not [string]::IsNullOrWhiteSpace($JsonOutputPath)) {
    $skipObject = [pscustomobject]@{
      schema_version = 'dcoir_collector_mission_readiness_gate_v1'
      status = 'skipped'
      selected_suite = $SelectedSuite
      reason = 'selected_suite_is_not_fullregression'
    }
    $skipParent = Split-Path -Parent $JsonOutputPath
    if (-not [string]::IsNullOrWhiteSpace($skipParent) -and -not (Test-Path -LiteralPath $skipParent)) {
      New-Item -ItemType Directory -Force -Path $skipParent | Out-Null
    }
    $skipObject | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $JsonOutputPath -Encoding utf8
  }
  Write-Host 'DCOIR_COLLECTOR_MISSION_READY_GATE=SKIPPED'
  exit 0
}

$resolvedHarnessOutputRoot = (Resolve-Path -LiteralPath $HarnessOutputRoot).Path
$resolvedSummaryJsonPath = $null

if (-not [string]::IsNullOrWhiteSpace($SummaryJsonPath)) {
  $resolvedSummaryJsonPath = (Resolve-Path -LiteralPath $SummaryJsonPath).Path
} else {
  $summaryCandidates = @(
    Get-ChildItem -LiteralPath $resolvedHarnessOutputRoot -Recurse -File -Filter 'summary.json' -ErrorAction Stop |
      Sort-Object LastWriteTimeUtc -Descending
  )
  if (@($summaryCandidates).Count -eq 0) {
    throw "No harness summary.json files were found under: $resolvedHarnessOutputRoot"
  }
  $resolvedSummaryJsonPath = $summaryCandidates[0].FullName
}

$summary = Get-Content -LiteralPath $resolvedSummaryJsonPath -Raw | ConvertFrom-Json
$summarySuite = [string]$summary.Suite
if ($summarySuite -ne 'FullRegression') {
  throw "Mission-readiness gate requires a FullRegression harness summary, but summary suite was: $summarySuite"
}

$coverageRows = @($summary.CapabilityCoverage)
if (@($coverageRows).Count -eq 0) {
  throw "Harness summary did not contain CapabilityCoverage rows: $resolvedSummaryJsonPath"
}

$ignoredCapabilityIds = @(
  'collector.knowledge.operator_contract_alignment'
)

$failingRows = New-Object System.Collections.ArrayList
$checkedCount = 0

foreach ($row in $coverageRows) {
  $capabilityId = [string]$row.capability_id
  if ($ignoredCapabilityIds -contains $capabilityId) {
    continue
  }

  $checkedCount += 1
  $coverageClass = [string]$row.coverage_class
  $status = [string]$row.status
  $remainingGap = [string]$row.remaining_gap

  if ($coverageClass -eq 'out_of_scope_with_reason') {
    continue
  }

  $failureReasons = New-Object System.Collections.ArrayList
  if ($status -ne 'covered') {
    [void]$failureReasons.Add(("status={0}" -f $status))
  }
  if ($coverageClass -eq 'partial') {
    [void]$failureReasons.Add('coverage_class=partial')
  }
  if (-not [string]::IsNullOrWhiteSpace($remainingGap)) {
    [void]$failureReasons.Add('remaining_gap_present')
  }

  if (@($failureReasons).Count -gt 0) {
    [void]$failingRows.Add([pscustomobject]@{
        capability_id = $capabilityId
        coverage_class = $coverageClass
        status = $status
        failure_reasons = @($failureReasons)
        remaining_gap = $remainingGap
      })
  }
}

$gateStatus = if (@($failingRows).Count -eq 0) { 'passed' } else { 'failed' }
$reportObject = [pscustomobject]@{
  schema_version = 'dcoir_collector_mission_readiness_gate_v1'
  status = $gateStatus
  selected_suite = $SelectedSuite
  summary_suite = $summarySuite
  harness_output_root = $resolvedHarnessOutputRoot
  harness_summary_json_path = $resolvedSummaryJsonPath
  ignored_capability_ids = @($ignoredCapabilityIds)
  checked_capability_count = $checkedCount
  failing_capability_count = @($failingRows).Count
  failing_capabilities = @($failingRows)
}

if (-not [string]::IsNullOrWhiteSpace($JsonOutputPath)) {
  $jsonParent = Split-Path -Parent $JsonOutputPath
  if (-not [string]::IsNullOrWhiteSpace($jsonParent) -and -not (Test-Path -LiteralPath $jsonParent)) {
    New-Item -ItemType Directory -Force -Path $jsonParent | Out-Null
  }
  $reportObject | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $JsonOutputPath -Encoding utf8
}

$reportLines = @(
  '# DCOIR Collector Mission Readiness Gate',
  '',
  ('Status: {0}' -f $gateStatus),
  ('Selected suite: {0}' -f $SelectedSuite),
  ('Harness summary: {0}' -f $resolvedSummaryJsonPath),
  ('Checked capability rows: {0}' -f $checkedCount),
  ('Ignored capability rows: {0}' -f (@($ignoredCapabilityIds).Count)),
  ('Failing capability rows: {0}' -f @($failingRows).Count),
  '',
  'This gate treats mission readiness as unmet when a checked FullRegression capability row is not covered, remains partial, or still carries a declared remaining gap.',
  ''
)

if (@($failingRows).Count -eq 0) {
  $reportLines += 'All checked FullRegression capability rows satisfied the mission-readiness gate.'
} else {
  $reportLines += '## Failing capability rows'
  $reportLines += ''
  foreach ($row in @($failingRows)) {
    $reportLines += ('- `{0}` | class=`{1}` | status=`{2}` | reasons=`{3}`' -f $row.capability_id, $row.coverage_class, $row.status, (@($row.failure_reasons) -join ', '))
    if (-not [string]::IsNullOrWhiteSpace([string]$row.remaining_gap)) {
      $reportLines += ('  - Remaining gap: {0}' -f [string]$row.remaining_gap)
    }
  }
}

Write-OptionalFile -Path $MarkdownOutputPath -Lines $reportLines

Write-Host ('DCOIR_COLLECTOR_MISSION_READY_GATE={0}' -f $gateStatus.ToUpperInvariant())
Write-Host ('DCOIR_COLLECTOR_MISSION_READY_GATE_SUMMARY={0}' -f $resolvedSummaryJsonPath)
Write-Host ('DCOIR_COLLECTOR_MISSION_READY_GATE_FAILING_COUNT={0}' -f @($failingRows).Count)

if (@($failingRows).Count -gt 0) {
  foreach ($row in @($failingRows)) {
    Write-Host ('MISSION_READY_FAILURE capability={0} class={1} status={2} reasons={3}' -f $row.capability_id, $row.coverage_class, $row.status, (@($row.failure_reasons) -join ','))
    if (-not [string]::IsNullOrWhiteSpace([string]$row.remaining_gap)) {
      Write-Host ('MISSION_READY_FAILURE_GAP capability={0} gap={1}' -f $row.capability_id, [string]$row.remaining_gap)
    }
  }
  throw ('FullRegression mission-readiness gate failed for {0} capability row(s).' -f @($failingRows).Count)
}
