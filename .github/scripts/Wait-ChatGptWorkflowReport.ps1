param(
  [Parameter(Mandatory=$true)][string]$Workflow,
  [Parameter(Mandatory=$true)][string]$RequestId,
  [int]$MinimumSeconds = 100,
  [int]$MaximumSeconds = 300,
  [int]$PollSeconds = 10
)

$reportPath = ".github/chatgpt_staging/status_reports/$Workflow/$RequestId/workflow_report.md"
$deadline = (Get-Date).AddSeconds($MaximumSeconds)
$minimumUntil = (Get-Date).AddSeconds($MinimumSeconds)
$lastResult = 'missing'
$lastPhase = 'unknown'

while ((Get-Date) -lt $deadline) {
  if (Test-Path -LiteralPath $reportPath -PathType Leaf) {
    $content = Get-Content -LiteralPath $reportPath -Raw
    $resultMatch = [regex]::Match($content, '(?m)^- result: (?<v>.+)$')
    $phaseMatch = [regex]::Match($content, '(?m)^- phase: (?<v>.+)$')
    if ($resultMatch.Success) { $lastResult = $resultMatch.Groups['v'].Value.Trim() }
    if ($phaseMatch.Success) { $lastPhase = $phaseMatch.Groups['v'].Value.Trim() }
    Write-Host "workflow=$Workflow request_id=$RequestId report_path=$reportPath result=$lastResult phase=$lastPhase"
    if (($lastResult -eq 'success') -or ($lastResult -eq 'failure')) { exit 0 }
  } else {
    Write-Host "workflow=$Workflow request_id=$RequestId report_path=$reportPath result=missing phase=waiting"
  }
  Start-Sleep -Seconds $PollSeconds
}

Write-Warning "Timed out after $MaximumSeconds seconds. Last result=$lastResult phase=$lastPhase report_path=$reportPath"
exit 1
