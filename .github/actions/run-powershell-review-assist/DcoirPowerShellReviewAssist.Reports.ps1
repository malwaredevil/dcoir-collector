$ErrorActionPreference = 'Stop'

function Invoke-FunctionReachabilityReviewAssistGate {
  param(
    [Parameter(Mandatory = $true)][string] $CommittedJson,
    [Parameter(Mandatory = $true)][string] $CommittedMarkdown,
    [Parameter(Mandatory = $true)][string] $GeneratedJson,
    [Parameter(Mandatory = $true)][string] $GeneratedMarkdown
  )

  & python project_sources/collector/tools/run_powershell_function_reachability_report.py --repo-root . --no-powershell --json-output $GeneratedJson --markdown-output $GeneratedMarkdown
  $functionExitCode = $LASTEXITCODE
  if (-not (Test-Path -LiteralPath $GeneratedJson)) {
    throw "PowerShell function reachability JSON report was not produced: $GeneratedJson"
  }
  if (-not (Test-Path -LiteralPath $GeneratedMarkdown)) {
    throw "PowerShell function reachability Markdown report was not produced: $GeneratedMarkdown"
  }
  if ($functionExitCode -ne 0) {
    throw "PowerShell function reachability report generation failed with exit code $functionExitCode."
  }
  $functionReport = Get-Content -LiteralPath $GeneratedJson -Raw | ConvertFrom-Json
  $functionClassificationCounts = $functionReport.summary.classification_counts | ConvertTo-Json -Compress
  Write-Host "function-reachability-committed-json: $CommittedJson"
  Write-Host "function-reachability-committed-markdown: $CommittedMarkdown"
  Write-Host "function-reachability-generated-json: $GeneratedJson"
  Write-Host "function-reachability-generated-markdown: $GeneratedMarkdown"
  Write-Host "function-reachability-validation-success: $($functionReport.validation.success)"
  Write-Host "function-reachability-functions: $($functionReport.summary.function_count)"
  Write-Host "function-reachability-parser-mode: $($functionReport.summary.parser_mode)"
  Write-Host "function-reachability-classification-counts: $functionClassificationCounts"
  Write-Host "function-reachability-dynamic-invocation-sites: $($functionReport.summary.dynamic_invocation_site_count)"
  Write-Host "function-reachability-coverage-state: $($functionReport.summary.coverage_state)"
  if ($functionReport.validation.success -ne $true) {
    throw 'PowerShell function reachability report validation did not report success.'
  }
  if ($functionReport.summary.parser_mode -ne 'python_lexical_fallback') {
    throw 'PowerShell function reachability report must use python_lexical_fallback parser mode in the review-assist gate.'
  }
  if ($functionReport.summary.coverage_state -ne 'not_collected') {
    throw 'PowerShell function reachability report must not claim runtime-lane coverage.'
  }

  & python project_sources/collector/tools/validate_powershell_function_reachability_report.py --generated-json $GeneratedJson --committed-json $CommittedJson
  $functionCompareExitCode = $LASTEXITCODE
  if ($functionCompareExitCode -ne 0) {
    throw "PowerShell function reachability committed-report parity check failed with exit code $functionCompareExitCode."
  }
  Remove-Item -LiteralPath $GeneratedJson -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $GeneratedMarkdown -Force -ErrorAction SilentlyContinue
}

function Invoke-PowerShellReviewAssistReportGate {
  param(
    [Parameter(Mandatory = $true)][string] $GeneratedJson,
    [Parameter(Mandatory = $true)][string] $GeneratedMarkdown,
    [Parameter(Mandatory = $true)][string] $ReviewAssistJson,
    [Parameter(Mandatory = $true)][string] $ReviewAssistMarkdown,
    [Parameter(Mandatory = $true)][string] $MetadataWrapperScript
  )

  if (-not (Test-Path -LiteralPath $MetadataWrapperScript)) {
    throw "PowerShell review-assist metadata wrapper script was not found: $MetadataWrapperScript"
  }

  & python project_sources/collector/tools/run_powershell_review_assist_report.py --repo-root . --json-output $GeneratedJson --markdown-output $GeneratedMarkdown
  $exitCode = $LASTEXITCODE

  if (-not (Test-Path -LiteralPath $GeneratedJson)) {
    throw "PowerShell review-assist JSON report was not produced: $GeneratedJson"
  }
  if (-not (Test-Path -LiteralPath $GeneratedMarkdown)) {
    throw "PowerShell review-assist Markdown report was not produced: $GeneratedMarkdown"
  }

  $env:REVIEW_ASSIST_GENERATED_JSON = $GeneratedJson
  $env:REVIEW_ASSIST_TARGET_JSON = $ReviewAssistJson
  $env:REVIEW_ASSIST_TARGET_MARKDOWN = $ReviewAssistMarkdown
  & python $MetadataWrapperScript
  $wrapExitCode = $LASTEXITCODE
  if ($wrapExitCode -ne 0) {
    throw "PowerShell review-assist workflow metadata wrapping failed with exit code $wrapExitCode."
  }
  Remove-Item -LiteralPath $GeneratedJson -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $GeneratedMarkdown -Force -ErrorAction SilentlyContinue

  if (-not (Test-Path -LiteralPath $ReviewAssistJson)) {
    throw "PowerShell review-assist JSON report was not produced: $ReviewAssistJson"
  }
  if (-not (Test-Path -LiteralPath $ReviewAssistMarkdown)) {
    throw "PowerShell review-assist Markdown report was not produced: $ReviewAssistMarkdown"
  }

  $report = Get-Content -LiteralPath $ReviewAssistJson -Raw | ConvertFrom-Json
  Write-Host "review-assist-generated-json: $GeneratedJson"
  Write-Host "review-assist-generated-markdown: $GeneratedMarkdown"
  Write-Host "review-assist-json: $ReviewAssistJson"
  Write-Host "review-assist-markdown: $ReviewAssistMarkdown"
  Write-Host "review-assist-workflow-behavior: $($report.artifact_contract.workflow_behavior)"
  Write-Host "review-assist-validation-success: $($report.validation.success)"
  Write-Host "review-assist-normalized-findings: $($report.summary.normalized_finding_count)"
  Write-Host "review-assist-optional-analyzer-state: $($report.evidence_channels.analyzer.state)"

  if ($exitCode -ne 0) {
    throw "PowerShell review-assist report generation failed with exit code $exitCode."
  }
  if ($report.validation.success -ne $true) {
    throw 'PowerShell review-assist report validation did not report success.'
  }
  if ($report.artifact_contract.workflow_behavior -ne 'caller_uploaded_artifact') {
    throw 'PowerShell review-assist report did not record workflow artifact behavior.'
  }
  if ($report.artifact_contract.local_artifacts.json -ne $ReviewAssistJson) {
    throw 'PowerShell review-assist JSON artifact path metadata did not match the uploaded JSON path.'
  }
  if ($report.artifact_contract.local_artifacts.markdown -ne $ReviewAssistMarkdown) {
    throw 'PowerShell review-assist Markdown artifact path metadata did not match the uploaded Markdown path.'
  }

  $markdownText = Get-Content -LiteralPath $ReviewAssistMarkdown -Raw
  $expectedMarkdownFragments = @(
    'Workflow behavior: `caller_uploaded_artifact`',
    ('- JSON: `{0}`' -f $ReviewAssistJson),
    ('- Markdown: `{0}`' -f $ReviewAssistMarkdown),
    $report.artifact_contract.retention_scope
  )
  foreach ($fragment in $expectedMarkdownFragments) {
    if (-not $markdownText.Contains($fragment)) {
      throw "PowerShell review-assist Markdown artifact metadata missing expected fragment: $fragment"
    }
  }
}
