$ErrorActionPreference = 'Stop'
$sourceInnerScript = '.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-003.ps1'
$tempInnerScript = Join-Path $env:RUNNER_TEMP 'exec-20260626-dcoir-review-hybrid-main-006-inner.ps1'
$trackedPaths = @(
  '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py',
  '.github/dcoir_review/openrouter-pr-review-pareto.yml',
  '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
  '.github/ops/requests/apply_patch/README.md',
  '.github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001'
)
$summaryPath = '.github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-006/diagnostic-summary.md'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $summaryPath) | Out-Null

$innerText = Get-Content -LiteralPath $sourceInnerScript -Raw -Encoding UTF8
$innerText = $innerText.Replace('is outside the added changed lines for this PR', 'is not an added changed line for this PR')
Set-Content -LiteralPath $tempInnerScript -Value $innerText -Encoding UTF8

try {
  & $tempInnerScript
  if ($LASTEXITCODE -ne 0) {
    throw "inner script exited with code $LASTEXITCODE"
  }
  @(
    '# DCOIR Review hybrid exec 006 diagnostic summary',
    '',
    '- result: success',
    '- inner_script: exec-20260626-dcoir-review-hybrid-main-003.ps1 with unanchored reason wording preserved',
    '- note: inner script completed and pushed its source commit.'
  ) | Out-File -FilePath $summaryPath -Encoding utf8
} catch {
  $failure = $_.Exception.Message
  Write-Host "DCOIR review hybrid direct update failed: $failure"
  Write-Host '--- git status before cleanup ---'
  $before = git status --short
  $before | ForEach-Object { Write-Host $_ }
  @(
    '# DCOIR Review hybrid exec 006 diagnostic summary',
    '',
    '- result: failure',
    "- failure: $failure",
    '',
    '## Git status before cleanup',
    '```text',
    ($before -join "`n"),
    '```'
  ) | Out-File -FilePath $summaryPath -Encoding utf8
  Write-Host '--- restoring tracked source/staging paths so chatgpt-exec can publish artifacts ---'
  git restore --staged --worktree -- $trackedPaths
  Write-Host '--- git status after cleanup ---'
  $after = git status --short
  $after | ForEach-Object { Write-Host $_ }
  @(
    '',
    '## Git status after cleanup',
    '```text',
    ($after -join "`n"),
    '```'
  ) | Out-File -FilePath $summaryPath -Encoding utf8 -Append
  exit 1
}
