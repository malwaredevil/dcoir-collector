Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirActionsVersion = '2026-05-01.1'
$script:Ctx = $null

$moduleRoot = Split-Path -Parent $PSScriptRoot
foreach ($dep in @('Dcoir.Common','Dcoir.GitHub','Dcoir.Packaging')) {
    $depPath = Join-Path $moduleRoot ("$dep\$dep.psd1")
    if (-not (Test-Path -LiteralPath $depPath -PathType Leaf)) { $depPath = Join-Path $moduleRoot ("$dep\$dep.psm1") }
    Import-Module -Name $depPath -Force -ErrorAction Stop
}

$privatePath = Join-Path $PSScriptRoot 'Private'
$publicPath = Join-Path $PSScriptRoot 'Public'
foreach ($path in @($privatePath,$publicPath)) {
    if (Test-Path -LiteralPath $path -PathType Container) {
        Get-ChildItem -LiteralPath $path -Filter '*.ps1' | Sort-Object Name | ForEach-Object { . $_.FullName }
    }
}

Export-ModuleMember -Function Invoke-DcoirActionsWorkflowOrchestratorEngine
