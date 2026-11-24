$ErrorActionPreference = 'Stop'
$actionRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path -Path $actionRoot -ChildPath 'DcoirPowerShellReviewAssist.Paths.ps1')
. (Join-Path -Path $actionRoot -ChildPath 'DcoirPowerShellReviewAssist.Reports.ps1')

$paths = Resolve-ReviewAssistWorkflowPaths `
  -ReviewAssistJsonOutput $env:REVIEW_ASSIST_JSON_OUTPUT `
  -ReviewAssistMarkdownOutput $env:REVIEW_ASSIST_MARKDOWN_OUTPUT
Clear-ReviewAssistWorkflowOutputs -Paths $paths

Invoke-FunctionReachabilityReviewAssistGate `
  -CommittedJson $paths.FunctionReachabilityJson `
  -CommittedMarkdown $paths.FunctionReachabilityMarkdown `
  -GeneratedJson $paths.FunctionGeneratedJson `
  -GeneratedMarkdown $paths.FunctionGeneratedMarkdown

Invoke-PowerShellReviewAssistReportGate `
  -ReviewAssistJson $paths.ReviewAssistJson `
  -ReviewAssistMarkdown $paths.ReviewAssistMarkdown
