$ErrorActionPreference = 'Stop'
$sourceInnerScript = '.github/chatgpt_staging/exec_scripts/exec-20260626-dcoir-review-hybrid-main-003.ps1'
$tempInnerScript = Join-Path $env:RUNNER_TEMP 'exec-20260626-dcoir-review-hybrid-main-008-inner.ps1'
$trackedPaths = @(
  '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py',
  '.github/dcoir_review/openrouter-pr-review-pareto.yml',
  '.github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py',
  '.github/ops/requests/apply_patch/README.md',
  '.github/ops/requests/apply_patch/20260626-dcoir-review-script-budget-001'
)
$summaryPath = '.github/chatgpt_staging/status_reports/chatgpt-exec/exec-20260626-dcoir-review-hybrid-main-008/diagnostic-summary.md'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $summaryPath) | Out-Null

$innerText = Get-Content -LiteralPath $sourceInnerScript -Raw -Encoding UTF8
$innerText = $innerText.Replace('is outside the added changed lines for this PR', 'is not an added changed line for this PR')
$innerText = $innerText.Replace("review_script_path.write_text(review_text, encoding='utf-8')", "review_script_path.write_text(review_text, encoding='utf-8', newline='\n')")
$innerText = $innerText.Replace("config_path.write_text(config_text, encoding='utf-8')", "config_path.write_text(config_text, encoding='utf-8', newline='\n')")
$innerText = $innerText.Replace("selftest_path.write_text(selftest_text, encoding='utf-8')", "selftest_path.write_text(selftest_text, encoding='utf-8', newline='\n')")
$innerText = $innerText.Replace("readme_path.write_text(readme_text, encoding='utf-8')", "readme_path.write_text(readme_text, encoding='utf-8', newline='\n')")
$diffCheckPattern = "git diff --check\r?\nif \(\`$LASTEXITCODE -ne 0\) \{ throw 'git diff --check failed' \}"
$diffCheckReplacement = "git diff --check -- .github/dcoir_review/scripts/openrouter_pr_review_pareto_context.py .github/dcoir_review/scripts/openrouter_pr_review_pareto_context_selftest.py .github/dcoir_review/openrouter-pr-review-pareto.yml .github/ops/requests/apply_patch/README.md`nif (`$LASTEXITCODE -ne 0) { throw 'git diff --check failed' }"
$innerText = [regex]::Replace($innerText, $diffCheckPattern, $diffCheckReplacement)
Set-Content -LiteralPath $tempInnerScript -Value $innerText -Encoding UTF8

try {
  & $tempInnerScript
  if ($LASTEXITCODE -ne 0) {
    throw "inner script exited with code $LASTEXITCODE"
  }
  @(
    '# DCOIR Review hybrid exec 008 diagnostic summary',
    '',
    '- result: success',
    '- inner_script: exec-20260626-dcoir-review-hybrid-main-003.ps1 with LF source writes, unanchored reason wording preserved, and source-scoped diff check',
    '- note: inner script completed and pushed its source commit.'
  ) | Out-File -FilePath $summaryPath -Encoding utf8
} catch {
  $failure = $_.Exception.Message
  Write-Host "DCOIR review hybrid direct update failed: $failure"
  Write-Host '--- git status before cleanup ---'
  $before = git status --short
  $before | ForEach-Object { Write-Host $_ }
  @(
    '# DCOIR Review hybrid exec 008 diagnostic summary',
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
