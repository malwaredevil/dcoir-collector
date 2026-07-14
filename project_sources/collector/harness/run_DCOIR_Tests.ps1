<#
.SYNOPSIS
Compatibility launcher for the generated DCOIR collector harness.

.DESCRIPTION
Assembles the maintained harness source parts into run_DCOIR_Tests.generated.ps1 and then
invokes the generated harness with the caller's original arguments. The maintained harness
source is project_sources/collector/harness/source/parts/*.ps1; this file is intentionally
only a small launcher, not the monolithic harness source.

.FILE NAME
run_DCOIR_Tests.ps1

.INPUTS
Any argument accepted by run_DCOIR_Tests.generated.ps1.

.OUTPUTS
The generated harness output and exit behavior.
#>

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$HarnessRoot = if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
  Split-Path -Parent $PSCommandPath
} else {
  Split-Path -Parent $MyInvocation.MyCommand.Path
}

$AssemblerPath = Join-Path $HarnessRoot 'assemble_run_DCOIR_Tests.ps1'
$GeneratedHarnessPath = Join-Path $HarnessRoot 'run_DCOIR_Tests.generated.ps1'

if (-not (Test-Path -LiteralPath $AssemblerPath)) {
  throw "Harness assembler not found: $AssemblerPath"
}

& $AssemblerPath -OutputPath $GeneratedHarnessPath
if (-not (Test-Path -LiteralPath $GeneratedHarnessPath)) {
  throw "Generated harness not found: $GeneratedHarnessPath"
}

& $GeneratedHarnessPath @args
if (-not $?) {
  exit 1
}

exit 0
