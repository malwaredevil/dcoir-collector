$ErrorActionPreference = 'Stop'

function Assert-ReviewAssistOutputPath {
  param(
    [Parameter(Mandatory = $true)][string] $PathValue,
    [Parameter(Mandatory = $true)][string] $ExpectedSuffix,
    [Parameter(Mandatory = $true)][string] $Label
  )

  if ([string]::IsNullOrWhiteSpace($PathValue)) {
    throw "$Label output path is required."
  }
  $normalized = $PathValue.Replace([string][char]92, '/').Trim()
  if ($normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:') {
    throw "$Label output path must be repo-relative: $PathValue"
  }
  if ($normalized -match '(^|/)[.][.]($|/)') {
    throw "$Label output path must not contain traversal: $PathValue"
  }
  if (-not $normalized.StartsWith('project_sources/collector/')) {
    throw "$Label output path must stay under project_sources/collector: $PathValue"
  }
  if (-not $normalized.EndsWith($ExpectedSuffix)) {
    throw "${Label} output path must end with ${ExpectedSuffix}: $PathValue"
  }
  $repoPathInfo = Get-Location -PSProvider FileSystem
  if ($null -eq $repoPathInfo -or [string]::IsNullOrWhiteSpace($repoPathInfo.ProviderPath)) {
    throw 'Repository root must be a FileSystem provider path.'
  }
  $repoRoot = [System.IO.Path]::GetFullPath($repoPathInfo.ProviderPath)
  $collectorRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'project_sources/collector'))
  $candidateFullPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $normalized))
  $separatorChars = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $repoPrefix = $repoRoot.TrimEnd($separatorChars) + [System.IO.Path]::DirectorySeparatorChar
  $collectorPrefix = $collectorRoot.TrimEnd($separatorChars) + [System.IO.Path]::DirectorySeparatorChar
  if (-not $candidateFullPath.StartsWith($collectorPrefix, [System.StringComparison]::Ordinal)) {
    throw "$Label output path must resolve under project_sources/collector: $PathValue"
  }
  if (-not $candidateFullPath.StartsWith($repoPrefix, [System.StringComparison]::Ordinal)) {
    throw "$Label output path must resolve under the repository root: $PathValue"
  }
  $resolvedRelative = $candidateFullPath.Substring($repoPrefix.Length).Replace([string][char]92, '/')
  if ($resolvedRelative -match '(^|/)[.][.]($|/)') {
    throw "$Label output path must not contain traversal after resolution: $PathValue"
  }
  if ($resolvedRelative -ne $normalized) {
    Write-Host "$Label output path normalized to resolved repo-relative path: $resolvedRelative"
  }
  return $resolvedRelative
}

function Assert-ReviewAssistFixedOutputPath {
  param(
    [Parameter(Mandatory = $true)][string] $PathValue,
    [Parameter(Mandatory = $true)][string] $ExpectedPath,
    [Parameter(Mandatory = $true)][string] $ExpectedSuffix,
    [Parameter(Mandatory = $true)][string] $Label
  )

  $resolvedPath = Assert-ReviewAssistOutputPath -PathValue $PathValue -ExpectedSuffix $ExpectedSuffix -Label $Label
  if ($resolvedPath -ne $ExpectedPath) {
    throw "$Label output path must be the fixed workflow path ${ExpectedPath}: $PathValue"
  }
  return $resolvedPath
}

function Resolve-ReviewAssistWorkflowPaths {
  param(
    [Parameter(Mandatory = $true)][string] $ReviewAssistJsonOutput,
    [Parameter(Mandatory = $true)][string] $ReviewAssistMarkdownOutput
  )

  $paths = [pscustomobject]@{
    FunctionReachabilityJson = 'project_sources/collector/powershell_function_reachability_report.json'
    FunctionReachabilityMarkdown = 'project_sources/collector/powershell_function_reachability_report.md'
    FunctionGeneratedJson = Assert-ReviewAssistFixedOutputPath -PathValue 'project_sources/collector/powershell_function_reachability_workflow_report.json' -ExpectedPath 'project_sources/collector/powershell_function_reachability_workflow_report.json' -ExpectedSuffix '.json' -Label 'Function reachability generated JSON'
    FunctionGeneratedMarkdown = Assert-ReviewAssistFixedOutputPath -PathValue 'project_sources/collector/powershell_function_reachability_workflow_report.md' -ExpectedPath 'project_sources/collector/powershell_function_reachability_workflow_report.md' -ExpectedSuffix '.md' -Label 'Function reachability generated Markdown'
    GeneratedJson = Assert-ReviewAssistFixedOutputPath -PathValue 'project_sources/collector/powershell_review_assist_workflow_source_report.json' -ExpectedPath 'project_sources/collector/powershell_review_assist_workflow_source_report.json' -ExpectedSuffix '.json' -Label 'Review-assist generated JSON'
    GeneratedMarkdown = Assert-ReviewAssistFixedOutputPath -PathValue 'project_sources/collector/powershell_review_assist_workflow_source_report.md' -ExpectedPath 'project_sources/collector/powershell_review_assist_workflow_source_report.md' -ExpectedSuffix '.md' -Label 'Review-assist generated Markdown'
    ReviewAssistJson = Assert-ReviewAssistOutputPath -PathValue $ReviewAssistJsonOutput -ExpectedSuffix '.json' -Label 'JSON'
    ReviewAssistMarkdown = Assert-ReviewAssistOutputPath -PathValue $ReviewAssistMarkdownOutput -ExpectedSuffix '.md' -Label 'Markdown'
  }

  if ($paths.ReviewAssistJson -eq $paths.ReviewAssistMarkdown) {
    throw 'PowerShell review-assist JSON and Markdown outputs must be different paths.'
  }
  if ($paths.FunctionGeneratedJson -eq $paths.FunctionGeneratedMarkdown) {
    throw 'PowerShell function reachability generated JSON and Markdown outputs must be different paths.'
  }
  if ($paths.GeneratedJson -eq $paths.GeneratedMarkdown) {
    throw 'PowerShell review-assist generated JSON and Markdown outputs must be different paths.'
  }
  if (-not (Test-Path -LiteralPath $paths.FunctionReachabilityJson)) {
    throw "Committed PowerShell function reachability JSON report is required before regeneration: $($paths.FunctionReachabilityJson)"
  }
  if (-not (Test-Path -LiteralPath $paths.FunctionReachabilityMarkdown)) {
    throw "Committed PowerShell function reachability Markdown report is required before regeneration: $($paths.FunctionReachabilityMarkdown)"
  }
  return $paths
}

function Clear-ReviewAssistWorkflowOutputs {
  param(
    [Parameter(Mandatory = $true)] $Paths
  )

  $outputPaths = @(
    $Paths.FunctionGeneratedJson,
    $Paths.FunctionGeneratedMarkdown,
    $Paths.GeneratedJson,
    $Paths.GeneratedMarkdown,
    $Paths.ReviewAssistJson,
    $Paths.ReviewAssistMarkdown
  )
  foreach ($path in $outputPaths) {
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
  }
}
