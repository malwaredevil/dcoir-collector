$ErrorActionPreference = 'Stop'

$outputJson = $env:PSSCRIPTANALYZER_OUTPUT_JSON
if ([string]::IsNullOrWhiteSpace($outputJson)) {
  throw 'PSSCRIPTANALYZER_OUTPUT_JSON is required.'
}
$normalized = $outputJson.Replace('\', '/').Trim()
if ($normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:') {
  throw "Output path must be repo-relative: $outputJson"
}
if ($normalized -match '(^|/)\.\.($|/)') {
  throw "Output path must not contain traversal: $outputJson"
}
if (-not $normalized.StartsWith('project_sources/collector/', [System.StringComparison]::Ordinal)) {
  throw "Output path must remain under project_sources/collector/: $outputJson"
}
$repoRoot = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd([char]'\', [char]'/') + [System.IO.Path]::DirectorySeparatorChar
$resolvedOutputJson = [System.IO.Path]::GetFullPath((Join-Path -Path (Get-Location).Path -ChildPath $normalized))
if (-not $resolvedOutputJson.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Output path resolves outside the repository: $outputJson"
}

# Install PSScriptAnalyzer if not already present.
if (-not (Get-Module -ListAvailable -Name PSScriptAnalyzer)) {
  Write-Host 'PSScriptAnalyzer not found; installing...'
  Install-Module -Name PSScriptAnalyzer -Force -SkipPublisherCheck -Scope CurrentUser -ErrorAction Stop
  Write-Host 'PSScriptAnalyzer installed.'
}
Import-Module PSScriptAnalyzer -Force

$analyzerVersion = (Get-Module PSScriptAnalyzer).Version.ToString()
$psVersion       = $PSVersionTable.PSVersion.ToString()
$psEditionStr       = [string]($PSVersionTable.PSEdition)

# Discover collector PS1 source files.
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
  throw 'No collector PS1 source files found for PSScriptAnalyzer.'
}
Write-Host "PSScriptAnalyzer targets: $($sourceFiles.Count) file(s)"

function Get-RepoRelativePath([string]$fullPath) {
  $normalized = [System.IO.Path]::GetFullPath($fullPath)
  if ($normalized.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $normalized.Substring($repoRoot.Length).Replace('\', '/')
  }
  return $fullPath.Replace('\', '/')
}

# Hardened rule set: run all built-in rules (PSScriptAnalyzer default) plus
# explicitly enable the correctness/security rules that are Warning-or-lower
# by default so they appear in the report with their natural severity.
# Rules we care most about for a security collector:
#   PSAvoidGlobalVars                         - global state leaks across sessions
#   PSAvoidUsingConvertToSecureStringWithPlainText - plaintext credential handling
#   PSAvoidUsingPlainTextForPassword           - plaintext password params
#   PSReviewUnusedParameter                   - dead function interface
#   PSUseDeclaredVarsMoreThanAssignments       - dead locals / copy-paste bugs
#   PSAvoidShouldContinueWithoutForce         - interactive prompt in automation
# All of the above are included in the PSScriptAnalyzer built-in rule set.
# Running without -IncludeRule/-ExcludeRule executes all built-in rules.

# Run analysis across all source files.
$allFindings = [System.Collections.Generic.List[object]]::new()
$analysisErrors = [System.Collections.Generic.List[object]]::new()
foreach ($file in $sourceFiles) {
  $repoRelFilePath = Get-RepoRelativePath $file
  try {
    $results = @(
      Invoke-ScriptAnalyzer `
        -Path $file `
        -Recurse:$false `
        -ErrorAction Stop
    )
  } catch {
    $analysisErrors.Add([ordered]@{
      path    = $repoRelFilePath
      message = [string]$_.Exception.Message
    })
    continue
  }
  foreach ($r in $results) {
    $repoRelPath = Get-RepoRelativePath $r.ScriptPath

    $fix = "See PSScriptAnalyzer documentation for rule: $($r.RuleName)"
    if ($r.SuggestedCorrections -and $r.SuggestedCorrections.Count -gt 0) {
      $c = $r.SuggestedCorrections[0]
      if (-not [string]::IsNullOrWhiteSpace($c.Description)) { $fix = $c.Description.Trim() }
      if (-not [string]::IsNullOrWhiteSpace($c.Text))        { $fix = $c.Text.Trim() }
    }

    $allFindings.Add([ordered]@{
      path             = $repoRelPath
      line             = [int]$r.Line
      column           = [int]$r.Column
      rule_name        = [string]$r.RuleName
      severity         = [string]$r.Severity
      observed_problem = [string]$r.Message
      recommended_fix  = $fix
    })
  }
}

$errorFindings   = @($allFindings | Where-Object { $_.severity -eq 'Error' })
$warningFindings = @($allFindings | Where-Object { $_.severity -eq 'Warning' })
$infoFindings    = @($allFindings | Where-Object { $_.severity -eq 'Information' })

Write-Host ""
Write-Host "PSScriptAnalyzer complete: $($allFindings.Count) finding(s) across $($sourceFiles.Count) file(s)"
Write-Host "  Error:       $($errorFindings.Count)"
Write-Host "  Warning:     $($warningFindings.Count)"
Write-Host "  Information: $($infoFindings.Count)"
Write-Host ""
$allFindings | ForEach-Object { Write-Host "  [$($_.severity.ToUpper())] $($_.rule_name) at $($_.path):$($_.line)" }

# Build repo-relative target list.
$repoRelTargets = @($sourceFiles | ForEach-Object { Get-RepoRelativePath $_ })

$report = [ordered]@{
  schema_version   = 'dcoir_powershell_analyzer_report_v1'
  validation       = [ordered]@{
    success  = ($analysisErrors.Count -eq 0)
    errors   = @(
      $analysisErrors | ForEach-Object { "$($_.path): $($_.message)" }
    )
    warnings = @()
  }
  summary          = [ordered]@{
    file_count         = [int]$sourceFiles.Count
    finding_count      = [int]$allFindings.Count
    error_count        = [int]$errorFindings.Count
    warning_count      = [int]$warningFindings.Count
    information_count  = [int]$infoFindings.Count
    skipped_count      = [int]$analysisErrors.Count
  }
  findings         = @($allFindings)
  targets          = @($repoRelTargets)
  skipped_surfaces = @($analysisErrors)
  analyzer         = [ordered]@{
    name    = 'PSScriptAnalyzer'
    version = $analyzerVersion
  }
  powershell       = [ordered]@{
    version = $psVersion
    edition = $psEditionStr
  }
  settings         = [ordered]@{
    ruleset              = 'all-builtin'
    excluded_rules       = @()
    fail_on_error        = ($env:FAIL_ON_ERROR_SEVERITY -ne 'false')
  }
  inventory        = [ordered]@{
    source_root = 'project_sources/collector/source'
    part_count  = [int]([Math]::Max(0, $sourceFiles.Count - 1))
  }
  baseline         = [ordered]@{
    comparison = 'none'
  }
  outputs          = [ordered]@{
    json = $normalized
  }
}

$outputDir = Split-Path -Parent $resolvedOutputJson
if ($outputDir -and -not (Test-Path -LiteralPath $outputDir)) {
  New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}
$report | ConvertTo-Json -Depth 10 | Set-Content `
  -LiteralPath $resolvedOutputJson `
  -Encoding utf8
Write-Host "PSScriptAnalyzer report written to: $normalized"

if ($analysisErrors.Count -gt 0) {
  Write-Error (
    "PSScriptAnalyzer failed while analyzing " +
    "$($analysisErrors.Count) file(s):"
  )
  foreach ($analysisError in $analysisErrors) {
    Write-Error "- $($analysisError.path): $($analysisError.message)"
  }
  throw (
    "PSScriptAnalyzer invocation failed for " +
    "$($analysisErrors.Count) file(s)."
  )
}

# Severity gate
# Fail on any Error-severity finding.  Warnings are reported but non-blocking
# for now; promote to blocking once the current Warning backlog is triaged.
if ($env:FAIL_ON_ERROR_SEVERITY -ne 'false' -and $errorFindings.Count -gt 0) {
  Write-Host ""
  Write-Host "SEVERITY GATE FAILED - $($errorFindings.Count) Error-severity finding(s):"
  foreach ($f in $errorFindings) {
    Write-Host "  [ERROR] $($f.rule_name) at $($f.path):$($f.line)"
    Write-Host "          $($f.observed_problem)"
  }
  throw "PSScriptAnalyzer found $($errorFindings.Count) Error-severity violation(s). Fix before merging."
}

if ($allFindings.Count -eq 0) {
  Write-Host "PASS: PSScriptAnalyzer found no findings."
} else {
  Write-Host "PASS (gate): 0 Error-severity findings. $($warningFindings.Count) Warning(s) and $($infoFindings.Count) Information finding(s) noted above - not blocking."
}
