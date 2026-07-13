Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:DcoirActionsOrchestratorVersion = '2026-05-01.7'

$moduleRoot = Split-Path -Parent $PSScriptRoot
$actionsPath = Join-Path $moduleRoot 'Dcoir.Actions\Dcoir.Actions.psd1'
if (-not (Test-Path -LiteralPath $actionsPath -PathType Leaf)) { $actionsPath = Join-Path $moduleRoot 'Dcoir.Actions\Dcoir.Actions.psm1' }
Import-Module -Name $actionsPath -Force -ErrorAction Stop

function Invoke-DcoirActionsWorkflowOrchestratorEngine {
    [CmdletBinding()]
    param(
        [ValidateSet('manifest','watch','dispatch','capture')][string]$Mode = 'manifest',
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
    Dcoir.Actions\Invoke-DcoirActionsWorkflowOrchestratorEngine @PSBoundParameters
}

Export-ModuleMember -Function Invoke-DcoirActionsWorkflowOrchestratorEngine
