<#
DCOIR GitHub Actions Workflow Orchestrator entrypoint.

Stable public entrypoint. The engine implementation lives in:
  .github/operator_tools/github_desktop_lane/modules/DcoirActionsOrchestrator/DcoirActionsOrchestrator.psm1
#>
[CmdletBinding()]
param(
    [ValidateSet('manifest','watch','dispatch','capture')]
    [string]$Mode = 'manifest',
    [string]$ManifestJson,
    [string]$Repo = 'DCOIR-Collector/dcoir-collector',
    [string]$Ref = 'main',
    [string[]]$Workflow,
    [Int64[]]$RunId,
    [int]$Limit = 5,
    [int]$PollSeconds = 30,
    [int]$TimeoutMinutes = 60,
    [int]$MaxParallel = 1,
    [switch]$DownloadArtifacts,
    [switch]$CreateUploadZip,
    [switch]$ConfirmDispatch,
    [switch]$DryRun,
    [string]$OutputBase
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$modulePath = Join-Path $PSScriptRoot '..\modules\DcoirActionsOrchestrator\DcoirActionsOrchestrator.psm1'
if (-not (Test-Path -LiteralPath $modulePath -PathType Leaf)) {
    throw "DCOIR Actions Orchestrator module not found: $modulePath"
}

Import-Module -Name $modulePath -Force

$engineParams = @{
    Mode = $Mode
    Repo = $Repo
    Ref = $Ref
    Limit = $Limit
    PollSeconds = $PollSeconds
    TimeoutMinutes = $TimeoutMinutes
    MaxParallel = $MaxParallel
}
if ($PSBoundParameters.ContainsKey('ManifestJson')) { $engineParams.ManifestJson = $ManifestJson }
if ($PSBoundParameters.ContainsKey('Workflow')) { $engineParams.Workflow = $Workflow }
if ($PSBoundParameters.ContainsKey('RunId')) { $engineParams.RunId = $RunId }
if ($PSBoundParameters.ContainsKey('OutputBase')) { $engineParams.OutputBase = $OutputBase }
if ($DownloadArtifacts) { $engineParams.DownloadArtifacts = $true }
if ($CreateUploadZip) { $engineParams.CreateUploadZip = $true }
if ($ConfirmDispatch) { $engineParams.ConfirmDispatch = $true }
if ($DryRun) { $engineParams.DryRun = $true }

Invoke-DcoirActionsWorkflowOrchestratorEngine @engineParams
