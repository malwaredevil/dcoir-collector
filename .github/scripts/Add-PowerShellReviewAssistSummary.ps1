[CmdletBinding()]
param(
  [string]$ReportPath = 'project_sources/collector/powershell_review_assist_workflow_report.md',
  [string]$SummaryPath = $env:GITHUB_STEP_SUMMARY,
  [string]$RunNumber = $env:GITHUB_RUN_NUMBER
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ReportPath)) {
  Write-Host 'Review-assist report not found; skipping job summary.'
  return
}

if ([string]::IsNullOrWhiteSpace($SummaryPath)) {
  Write-Host 'GITHUB_STEP_SUMMARY is not set; skipping review-assist job summary append.'
  return
}

$content = Get-Content -LiteralPath $ReportPath -Raw
$header = "## PowerShell Review-Assist Report - Run #$RunNumber`n`n"
($header + $content) | Out-File -Append -FilePath $SummaryPath -Encoding utf8
Write-Host 'Review-assist report written to job summary.'
