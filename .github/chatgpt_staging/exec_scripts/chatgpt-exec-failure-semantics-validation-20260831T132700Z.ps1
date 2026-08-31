$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $env:GITHUB_WORKSPACE

& .\.github\operator_tools\github_desktop_lane\tests\Test-DcoirActionsExecFailureSemantics.ps1
if ($LASTEXITCODE -ne 0) {
    throw "Exec failure-semantics regression exited $LASTEXITCODE"
}

$processSource = Get-Content -LiteralPath '.github/operator_tools/github_desktop_lane/modules/Dcoir.ActionsExec/Private/10-Process.ps1' -Raw
if ($processSource -notmatch 'New-DcoirActionsExecPowerShellWrapper') {
    throw 'PowerShell process wrapper hardening is missing.'
}
if ($processSource -notmatch '\$global:LASTEXITCODE') {
    throw 'Native LASTEXITCODE propagation guard is missing.'
}

Write-Host 'ChatGPT exec failure-semantics validation PASSED'
exit 0
