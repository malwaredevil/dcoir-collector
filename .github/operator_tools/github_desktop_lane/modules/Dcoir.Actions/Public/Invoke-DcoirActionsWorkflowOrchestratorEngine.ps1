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
    $repoRoot = Get-DcoirSystemEnvValue -Name 'DCOIR_REPO_ROOT' -Required
    $downloads = Get-DcoirSystemEnvValue -Name 'DCOIR_DOWNLOADS_DIR' -Required
    if (-not (Test-Path -LiteralPath $repoRoot -PathType Container)) { throw "DCOIR_REPO_ROOT Machine/System path does not exist: $repoRoot" }
    if (-not (Test-Path -LiteralPath $downloads -PathType Container)) { throw "DCOIR_DOWNLOADS_DIR Machine/System path does not exist: $downloads" }
    if ([string]::IsNullOrWhiteSpace($ManifestJson) -and $Mode -eq 'manifest') { $ManifestJson = Join-Path $repoRoot 'operator_tools\github_desktop_lane\manifests\actions_workflow_orchestrator.dispatch.sample.json' }
    if ($ManifestJson) { $ManifestJson = Resolve-DcoirPathText -Text $ManifestJson }
    $manifest = @{}
    if ($ManifestJson) {
        if (-not (Test-Path -LiteralPath $ManifestJson -PathType Leaf)) { throw "ManifestJson not found: $ManifestJson" }
        $manifest = ConvertTo-DcoirHashtable -InputObject (Get-Content -LiteralPath $ManifestJson -Raw | ConvertFrom-Json)
        if ($Mode -eq 'manifest') { $Mode = [string](Get-DcoirConfigValue -Map $manifest -Name 'mode' -Default 'dispatch') }
    }
    $outputCfg = Get-DcoirConfigValue -Map $manifest -Name 'output' -Default @{}
    $outputDefault = if (-not [string]::IsNullOrWhiteSpace($OutputBase)) { $OutputBase } else { $downloads }
    $outputFolder = Resolve-DcoirPathText -Text ([string](Get-DcoirConfigValue -Map $outputCfg -Name 'folder' -Default $outputDefault))
    if (-not (Test-Path -LiteralPath $outputFolder -PathType Container)) { New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null }
    $runSetId = [string](Get-DcoirConfigValue -Map $manifest -Name 'run_set_id' -Default ("dcoir_actions_" + (Get-Date -Format 'yyyyMMdd_HHmmss')))
    $runOutputDir = Join-Path $outputFolder ("{0}_{1}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), (ConvertTo-DcoirSafeName -Text $runSetId))
    $debugDir = Join-Path $runOutputDir 'debug'
    $evidenceDir = Join-Path $runOutputDir 'evidence'
    New-Item -ItemType Directory -Force -Path $debugDir,$evidenceDir | Out-Null
    $script:Ctx = [ordered]@{
        Mode=$Mode
        Repo=[string](Get-DcoirConfigValue -Map $manifest -Name 'repo' -Default $Repo)
        DefaultRef=[string](Get-DcoirConfigValue -Map $manifest -Name 'default_ref' -Default $Ref)
        RepoRoot=$repoRoot
        Downloads=$downloads
        PollSeconds=[int](Get-DcoirConfigValue -Map $manifest -Name 'poll_interval_seconds' -Default $PollSeconds)
        TimeoutMinutes=[int](Get-DcoirConfigValue -Map $manifest -Name 'timeout_minutes' -Default $TimeoutMinutes)
        MaxParallel=[int](Get-DcoirConfigValue -Map $manifest -Name 'max_parallel' -Default $MaxParallel)
        DispatchPollSeconds=[int](Get-DcoirConfigValue -Map $manifest -Name 'dispatch_poll_seconds' -Default 5)
        DispatchPollAttempts=[int](Get-DcoirConfigValue -Map $manifest -Name 'dispatch_poll_attempts' -Default 60)
        ManifestDryRun=[bool](Get-DcoirConfigValue -Map $manifest -Name 'dry_run' -Default $true)
        AllowMultipleLiveDispatches=[bool](Get-DcoirConfigValue -Map $manifest -Name 'allow_multiple_live_dispatches' -Default $false)
        MaxDispatchCount=[int](Get-DcoirConfigValue -Map $manifest -Name 'max_dispatch_count' -Default 1)
        FailFast=[bool](Get-DcoirConfigValue -Map $manifest -Name 'fail_fast' -Default $false)
        CleanupOutputFolderAfterZip=[bool](Get-DcoirConfigValue -Map $outputCfg -Name 'cleanup_output_folder_after_zip' -Default (Get-DcoirConfigValue -Map $manifest -Name 'cleanup_output_folder_after_zip' -Default $false))
        RunSetId=$runSetId
        RunOutputDir=$runOutputDir
        DebugDir=$debugDir
        EvidenceDir=$evidenceDir
        LogPath=(Join-Path $runOutputDir 'orchestrator.log.txt')
        DownloadArtifacts=[bool]($DownloadArtifacts -or [bool](Get-DcoirConfigValue -Map $outputCfg -Name 'download_artifacts' -Default $false))
        CreateZip=[bool]($CreateUploadZip -or [bool](Get-DcoirConfigValue -Map $outputCfg -Name 'create_chatgpt_friendly_zip' -Default $false))
        ZipPath=(Join-Path $outputFolder ([string](Get-DcoirConfigValue -Map $outputCfg -Name 'zip_name' -Default ($runSetId + '.chatgpt.zip'))))
        DispatchesStarted=0
        DispatchesSucceeded=0
        DispatchesBlocked=0
        Phase='startup'
        Records=$null
    }
    Set-DcoirToolContext -Context $script:Ctx
    if (Get-Command Set-DcoirGitHubContext -ErrorAction SilentlyContinue) { Set-DcoirGitHubContext -Context $script:Ctx }
    if ($DryRun) { $script:Ctx.ManifestDryRun = $true }
    if ($script:Ctx.MaxParallel -lt 1) { $script:Ctx.MaxParallel = 1 }
    if ($script:Ctx.ManifestDryRun) { $script:Ctx.MaxDispatchCount = [int](Get-DcoirConfigValue -Map $manifest -Name 'max_dispatch_count' -Default 9999) }
    if ($script:Ctx.MaxDispatchCount -lt 1) { $script:Ctx.MaxDispatchCount = 1 }
    Write-DcoirStatus "DCOIR Actions Workflow Orchestrator v$script:DcoirActionsVersion"
    Write-DcoirStatus "Machine DCOIR_REPO_ROOT=$repoRoot"
    Write-DcoirStatus "Machine DCOIR_DOWNLOADS_DIR=$downloads"
    Test-DcoirGhAvailable
    $records = New-Object System.Collections.ArrayList
    $script:Ctx.Records = $records
    if ($Mode -eq 'dispatch') {
        foreach ($r in @(Get-DcoirConfigValue -Map $manifest -Name 'runs' -Default @())) {
            $label = [string](Get-DcoirConfigValue -Map $r -Name 'run_id' -Default (Get-DcoirConfigValue -Map $r -Name 'label' -Default ([guid]::NewGuid().ToString('N'))))
            $wf = [string](Get-DcoirConfigValue -Map $r -Name 'workflow' -Default $null)
            if ([string]::IsNullOrWhiteSpace($wf)) { throw "Dispatch run $label has no workflow." }
            [void]$records.Add((New-DcoirRunRecord -Label $label -WorkflowFile $wf -RefName ([string](Get-DcoirConfigValue -Map $r -Name 'ref' -Default $script:Ctx.DefaultRef)) -Inputs (Get-DcoirConfigValue -Map $r -Name 'inputs' -Default @{}) -Capture (Get-DcoirConfigValue -Map $r -Name 'capture' -Default @{})))
        }
        Write-DcoirExecutionPlan -Records $records -Mode $Mode
        Save-DcoirJson -Path (Join-Path $script:Ctx.RunOutputDir 'dispatch_plan.json') -Object @($records)
        if ($script:Ctx.ManifestDryRun) {
            Write-DcoirPhase -Name 'dry_run' -Message 'Dry run requested. No workflows dispatched.'
            foreach ($rec in $records) { $rec.state = 'dry_run' }
        } else {
            Assert-DcoirLiveDispatchAllowed -Records $records
            if ([bool](Get-DcoirConfigValue -Map $manifest -Name 'require_dispatch_confirmation' -Default $true) -and -not $ConfirmDispatch) { throw 'Dispatch is blocked because require_dispatch_confirmation=true. Re-run with -ConfirmDispatch after reviewing dispatch_plan.json.' }
            Wait-DcoirRunSet -Records $records -DispatchPlanned
        }
    } elseif ($Mode -eq 'watch') {
        $watchCfg = Get-DcoirConfigValue -Map $manifest -Name 'watch' -Default @{}
        Add-DcoirWatchRecords -Records $records -Workflows @(Get-DcoirConfigValue -Map $watchCfg -Name 'workflows' -Default $Workflow) -Ids @(Get-DcoirConfigValue -Map $watchCfg -Name 'run_ids' -Default $RunId) -LimitCount ([int](Get-DcoirConfigValue -Map $watchCfg -Name 'limit' -Default $Limit)) -Branch $script:Ctx.DefaultRef
        Write-DcoirExecutionPlan -Records $records -Mode $Mode
        Wait-DcoirRunSet -Records $records
    } elseif ($Mode -eq 'capture') {
        Add-DcoirWatchRecords -Records $records -Workflows @() -Ids $RunId -LimitCount $Limit -Branch $script:Ctx.DefaultRef
        Write-DcoirExecutionPlan -Records $records -Mode $Mode
    } else {
        throw "Unsupported mode after manifest resolution: $Mode"
    }
    $failedCount = Complete-DcoirRunSet -Records $records
    if ($failedCount -gt 0) { exit 1 }
    exit 0
}
