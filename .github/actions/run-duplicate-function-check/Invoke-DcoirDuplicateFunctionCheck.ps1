$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd([char]'\', [char]'/') + [System.IO.Path]::DirectorySeparatorChar
function Get-RepoRelativePath([string]$fullPath) {
  $normalized = [System.IO.Path]::GetFullPath($fullPath)
  if ($normalized.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $normalized.Substring($repoRoot.Length).Replace('\', '/')
  }
  return $fullPath.Replace('\', '/')
}

function ConvertTo-MarkdownTableCell([object]$value) {
  if ($null -eq $value) {
    return ''
  }
  $text = [string]$value
  $text = $text -replace "`r?`n", ' '
  $text = $text.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
  $text = $text.Replace('|', '&#124;').Replace('`', '&#96;')
  return $text
}

function Resolve-CollectorReportPath([string]$pathValue, [string]$label, [string]$expectedSuffix) {
  if ([string]::IsNullOrWhiteSpace($pathValue)) {
    throw "$label output path is required."
  }
  $rawNormalized = $pathValue.Replace('\', '/')
  if ($rawNormalized -match '[\x00-\x1F\x7F]') {
    throw "$label output path must not contain control characters: $pathValue"
  }
  $normalized = $rawNormalized.Trim()
  if ($normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:') {
    throw "$label output path must be repo-relative: $pathValue"
  }
  if ($normalized -match '(^|/)\.\.($|/)') {
    throw "$label output path must not contain traversal: $pathValue"
  }
  if (-not $normalized.StartsWith('project_sources/collector/', [System.StringComparison]::Ordinal)) {
    throw "$label output path must stay under project_sources/collector/: $pathValue"
  }
  if (-not $normalized.EndsWith($expectedSuffix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$label output path must end with ${expectedSuffix}: $pathValue"
  }
  $resolved = [System.IO.Path]::GetFullPath((Join-Path -Path (Get-Location).Path -ChildPath $normalized))
  if (-not $resolved.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$label output path resolves outside the repository: $pathValue"
  }
  return [pscustomobject]@{
    FullPath     = $resolved
    RelativePath = $normalized
  }
}

$jsonOutput = Resolve-CollectorReportPath $env:DUPLICATE_FUNCTION_OUTPUT_JSON 'JSON' '.json'
$markdownOutput = Resolve-CollectorReportPath $env:DUPLICATE_FUNCTION_OUTPUT_MARKDOWN 'Markdown' '.md'
if ($jsonOutput.RelativePath -eq $markdownOutput.RelativePath) {
  throw 'Duplicate-function JSON and Markdown outputs must be different paths.'
}

# Discover collector PS1 source files (same set as PSScriptAnalyzer).
$sourceFiles = [System.Collections.Generic.List[string]]::new()
$collectorPs1 = 'project_sources/collector/source/DCOIR_Collector.ps1'
if (Test-Path -LiteralPath $collectorPs1) {
  $sourceFiles.Add((Resolve-Path -LiteralPath $collectorPs1).Path)
}
$partsDir = 'project_sources/collector/source/parts'
if (Test-Path -LiteralPath $partsDir -PathType Container) {
  foreach ($f in Get-ChildItem -LiteralPath $partsDir -Filter '*.ps1' -Recurse) {
    $sourceFiles.Add($f.FullName)
  }
}
$sourceFiles = @($sourceFiles | Select-Object -Unique)
if ($sourceFiles.Count -eq 0) {
  throw 'No collector PS1 source files found for duplicate function check.'
}

# Collect all function definitions using the PowerShell AST.
# Key: lowercase function name. Value: list of {file, line} tuples.
$functionMap = @{}
$parseFailures = [System.Collections.Generic.List[object]]::new()

foreach ($filePath in $sourceFiles) {
  $tokens = $null
  $errors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseFile($filePath, [ref]$tokens, [ref]$errors)

  if ($errors.Count -gt 0) {
    $relPath = Get-RepoRelativePath $filePath
    foreach ($parseError in $errors) {
      $parseFailures.Add([pscustomobject]@{
        path    = $relPath
        line    = [int]$parseError.Extent.StartLineNumber
        column  = [int]$parseError.Extent.StartColumnNumber
        message = [string]$parseError.Message
      })
    }
  }

  $funcDefs = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
  foreach ($fn in $funcDefs) {
    $key = $fn.Name.ToLowerInvariant()
    if (-not $functionMap.ContainsKey($key)) {
      $functionMap[$key] = [System.Collections.Generic.List[object]]::new()
    }
    $functionMap[$key].Add([pscustomobject]@{
      name = [string]$fn.Name
      path = Get-RepoRelativePath $filePath
      line = [int]$fn.Extent.StartLineNumber
    })
  }
}

$duplicates = @($functionMap.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 } | Sort-Object Key)
$duplicateRecords = @(
  foreach ($entry in $duplicates) {
    [ordered]@{
      function_name    = [string]$entry.Value[0].name
      normalized_name  = [string]$entry.Key
      occurrence_count = [int]$entry.Value.Count
      occurrences      = @(
        foreach ($loc in $entry.Value) {
          [ordered]@{
            path = [string]$loc.path
            line = [int]$loc.line
          }
        }
      )
    }
  }
)
$parseFailureRecords = @(
  foreach ($failure in $parseFailures) {
    [ordered]@{
      path    = [string]$failure.path
      line    = [int]$failure.line
      column  = [int]$failure.column
      message = [string]$failure.message
    }
  }
)
$repoRelTargets = @($sourceFiles | ForEach-Object { Get-RepoRelativePath $_ })

$report = [ordered]@{
  schema_version    = 'dcoir_powershell_duplicate_function_report_v1'
  validation        = [ordered]@{
    success  = ($parseFailures.Count -eq 0)
    errors   = @(
      $parseFailureRecords | ForEach-Object { "$($_.path):$($_.line):$($_.column) $($_.message)" }
    )
    warnings = @()
  }
  summary           = [ordered]@{
    file_count               = [int]$sourceFiles.Count
    function_name_count      = [int]$functionMap.Count
    duplicate_function_count = [int]$duplicates.Count
    parse_failure_count      = [int]$parseFailures.Count
  }
  duplicates        = @($duplicateRecords)
  parse_failures    = @($parseFailureRecords)
  targets           = @($repoRelTargets)
  artifact_contract = [ordered]@{
    local_artifacts   = [ordered]@{
      json     = $jsonOutput.RelativePath
      markdown = $markdownOutput.RelativePath
    }
    workflow_behavior = 'caller_uploaded_artifact'
    retention_scope   = 'workflow-generated report artifacts uploaded by the caller workflow'
  }
}

$jsonDir = Split-Path -Parent $jsonOutput.FullPath
if ($jsonDir -and -not (Test-Path -LiteralPath $jsonDir)) {
  New-Item -ItemType Directory -Force -Path $jsonDir | Out-Null
}
$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonOutput.FullPath -Encoding utf8

$markdownLines = [System.Collections.Generic.List[string]]::new()
$markdownLines.Add('# PowerShell Duplicate Function Report')
$markdownLines.Add('')
$markdownLines.Add('## Summary')
$markdownLines.Add('')
$markdownLines.Add("- Files scanned: $($sourceFiles.Count)")
$markdownLines.Add("- Unique function names: $($functionMap.Count)")
$markdownLines.Add("- Duplicate function names: $($duplicates.Count)")
$markdownLines.Add("- Parse failures: $($parseFailures.Count)")
$markdownLines.Add('- Workflow behavior: `caller_uploaded_artifact`')
$markdownLines.Add('- JSON: `' + $jsonOutput.RelativePath + '`')
$markdownLines.Add('- Markdown: `' + $markdownOutput.RelativePath + '`')
$markdownLines.Add('')

if ($parseFailures.Count -gt 0) {
  $markdownLines.Add('## Parse Failures')
  $markdownLines.Add('')
  $markdownLines.Add('| Path | Line | Column | Message |')
  $markdownLines.Add('| --- | ---: | ---: | --- |')
  foreach ($failure in $parseFailures) {
    $path = ConvertTo-MarkdownTableCell $failure.path
    $message = ConvertTo-MarkdownTableCell $failure.message
    $markdownLines.Add("| $path | $($failure.line) | $($failure.column) | $message |")
  }
  $markdownLines.Add('')
}

if ($duplicates.Count -gt 0) {
  $markdownLines.Add('## Duplicate Function Definitions')
  $markdownLines.Add('')
  foreach ($entry in $duplicates) {
    $functionName = ConvertTo-MarkdownTableCell $entry.Value[0].name
    $markdownLines.Add("### ``$functionName``")
    $markdownLines.Add('')
    $markdownLines.Add('| Path | Line |')
    $markdownLines.Add('| --- | ---: |')
    foreach ($loc in $entry.Value) {
      $locPath = ConvertTo-MarkdownTableCell $loc.path
      $markdownLines.Add("| ``$locPath`` | $($loc.line) |")
    }
    $markdownLines.Add('')
  }
} else {
  $markdownLines.Add('## Duplicate Function Definitions')
  $markdownLines.Add('')
  $markdownLines.Add('No duplicate function definitions found.')
  $markdownLines.Add('')
}

$markdownDir = Split-Path -Parent $markdownOutput.FullPath
if ($markdownDir -and -not (Test-Path -LiteralPath $markdownDir)) {
  New-Item -ItemType Directory -Force -Path $markdownDir | Out-Null
}
($markdownLines -join [Environment]::NewLine) + [Environment]::NewLine |
  Set-Content -LiteralPath $markdownOutput.FullPath -Encoding utf8

Write-Host "Duplicate-function JSON report written to: $($jsonOutput.RelativePath)"
Write-Host "Duplicate-function Markdown report written to: $($markdownOutput.RelativePath)"
Write-Host "Scanned $($sourceFiles.Count) file(s); found $($functionMap.Count) unique function name(s)."

if ($parseFailures.Count -gt 0) {
  Write-Host ""
  Write-Host 'POWERSHELL PARSE ERRORS DETECTED'
  Write-Host '================================='
  Write-Host 'Duplicate-function validation cannot be trusted until every collector PS1 source file parses cleanly.'
  Write-Host ""
  foreach ($failure in $parseFailures) {
    Write-Host "  - $($failure.path):$($failure.line):$($failure.column) $($failure.message)"
  }
  throw "Duplicate function check failed because $($parseFailures.Count) PowerShell parse error(s) were found."
}

if ($duplicates.Count -eq 0) {
  Write-Host 'PASS: No duplicate function definitions found across collector source.'
  exit 0
}

Write-Host ""
Write-Host 'DUPLICATE FUNCTION DEFINITIONS DETECTED'
Write-Host '======================================='
Write-Host 'The following function names are defined in more than one source file.'
Write-Host 'When dot-sourced together, the last loaded definition silently wins.'
Write-Host ""

foreach ($entry in $duplicates) {
  Write-Host "Function: $($entry.Value[0].name)"
  foreach ($loc in $entry.Value) {
    Write-Host "  - $($loc.path):$($loc.line)"
  }
  Write-Host ""
}

Write-Host "$($duplicates.Count) duplicate function name(s) found across $($sourceFiles.Count) file(s)."

if ($env:FAIL_ON_DUPLICATES -ne 'false') {
  Write-Error 'Duplicate function definitions found. Resolve overrides before merging.'
  exit 1
} else {
  Write-Warning 'Duplicate function definitions found (fail-on-duplicates=false; not blocking).'
  exit 0
}
