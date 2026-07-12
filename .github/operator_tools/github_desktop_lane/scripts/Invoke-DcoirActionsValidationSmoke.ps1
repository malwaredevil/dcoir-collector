<#
DCOIR Actions Validation Smoke Runner.

Purpose:
  Set-and-forget harness around Invoke-DcoirActionsWorkflowOrchestrator.ps1.
  The harness creates reviewed JSON manifests and executes the orchestrator.
#>
[CmdletBinding()]
param(
    [ValidateSet('Smoke','DryWatchOnly','LiveOnly')]
    [string]$Mode = 'Smoke',

    [string]$Workflow = 'manual-full-validation.yml',
    [string]$Suite = 'QuickAliases',
    [string]$Ref = 'main',

    [int]$PollIntervalSeconds = 30,
    [int]$TimeoutMinutes = 90,

    [switch]$DownloadArtifacts
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Script:ToolVersion = '2026-05-01.5'

$commonModule = Join-Path $PSScriptRoot '..\modules\Dcoir.Common\Dcoir.Common.psd1'
if (-not (Test-Path -LiteralPath $commonModule -PathType Leaf)) { $commonModule = Join-Path $PSScriptRoot '..\modules\Dcoir.Common\Dcoir.Common.psm1' }
if (-not (Test-Path -LiteralPath $commonModule -PathType Leaf)) { throw "Dcoir.Common module not found: $commonModule" }
Import-Module -Name $commonModule -Force -ErrorAction Stop

function Write-DcoirHarnessStep {
    param([Parameter(Mandatory=$true)][string]$Message)
    if (Get-Command -Name 'Dcoir.Common\Write-DcoirConsoleStep' -ErrorAction SilentlyContinue) {
        Dcoir.Common\Write-DcoirConsoleStep -Message $Message
    } else {
        Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message)
    }
}

function Invoke-DcoirOrchestratorStep {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string]$ScriptPath,
        [Parameter(Mandatory=$true)][string]$ManifestPath,
        [switch]$ConfirmDispatch
    )
    Write-DcoirHarnessStep $Label
    Write-DcoirHarnessStep "Manifest: $ManifestPath"

    if ($ConfirmDispatch) {
        & $ScriptPath -ManifestJson $ManifestPath -ConfirmDispatch
    } else {
        & $ScriptPath -ManifestJson $ManifestPath
    }

    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    if ($exitCode -ne 0) { throw "$Label failed with exit code $exitCode." }
}

$repo = Get-DcoirSystemEnvValue -Name 'DCOIR_REPO_ROOT' -Required
$downloads = Get-DcoirSystemEnvValue -Name 'DCOIR_DOWNLOADS_DIR' -Required

$orchestrator = Join-Path $repo 'operator_tools\github_desktop_lane\scripts\Invoke-DcoirActionsWorkflowOrchestrator.ps1'
if (-not (Test-Path -LiteralPath $orchestrator -PathType Leaf)) { throw "Orchestrator not found: $orchestrator" }

$dryManifest = Join-Path $repo 'operator_tools\github_desktop_lane\manifests\actions_workflow_orchestrator.dispatch.sample.json'
$watchManifest = Join-Path $repo 'operator_tools\github_desktop_lane\manifests\actions_workflow_orchestrator.watch.sample.json'
$liveManifest = Join-Path $downloads 'dcoir_actions_live_dispatch_test.json'

Write-DcoirHarnessStep "DCOIR Actions Validation Smoke Runner v$Script:ToolVersion"
Write-DcoirHarnessStep "Mode=$Mode Workflow=$Workflow Suite=$Suite Ref=$Ref"

if ($Mode -eq 'Smoke' -or $Mode -eq 'DryWatchOnly') {
    Invoke-DcoirOrchestratorStep -Label '[1/3] Running dry-run validation...' -ScriptPath $orchestrator -ManifestPath $dryManifest
    Invoke-DcoirOrchestratorStep -Label '[2/3] Running watch validation...' -ScriptPath $orchestrator -ManifestPath $watchManifest
}

if ($Mode -eq 'Smoke' -or $Mode -eq 'LiveOnly') {
    Write-DcoirHarnessStep '[3/3] Creating guarded live-dispatch manifest...'
    $manifest = [ordered]@{
        run_set_id = 'dcoir-live-dispatch-test'
        mode = 'dispatch'
        repo = 'DCOIR-Collector/dcoir-collector'
        default_ref = $Ref
        dry_run = $false
        require_dispatch_confirmation = $true
        allow_multiple_live_dispatches = $false
        max_dispatch_count = 1
        poll_interval_seconds = $PollIntervalSeconds
        timeout_minutes = $TimeoutMinutes
        max_parallel = 1
        output = [ordered]@{
            folder = '%DCOIR_DOWNLOADS_DIR%'
            create_chatgpt_friendly_zip = $true
            download_artifacts = [bool]$DownloadArtifacts
            zip_name = 'dcoir_actions_live_dispatch_test.chatgpt.zip'
        }
        runs = @(
            [ordered]@{
                run_id = 'collector-quick-validation'
                workflow = $Workflow
                ref = $Ref
                inputs = [ordered]@{ suite = $Suite }
                capture = [ordered]@{
                    summary = $true
                    jobs = $true
                    logs = $true
                    artifacts = [bool]$DownloadArtifacts
                }
            }
        )
    }
    Save-DcoirJson -Path $liveManifest -Object $manifest
    Write-DcoirHarnessStep "Live manifest written: $liveManifest"
    Invoke-DcoirOrchestratorStep -Label '[3/3] Running one guarded live dispatch...' -ScriptPath $orchestrator -ManifestPath $liveManifest -ConfirmDispatch
}

Write-DcoirHarnessStep 'Done. Upload these files if present:'
$expected = @(
    'dcoir_actions_workflow_orchestrator_sample.chatgpt.zip',
    'dcoir_actions_watch_sample.chatgpt.zip',
    'dcoir_actions_live_dispatch_test.chatgpt.zip',
    'dcoir_actions_live_dispatch_test.json'
)
foreach ($name in $expected) {
    $path = Join-Path $downloads $name
    if (Test-Path -LiteralPath $path) { Write-Host "UPLOAD_FILE=$path" }
}
