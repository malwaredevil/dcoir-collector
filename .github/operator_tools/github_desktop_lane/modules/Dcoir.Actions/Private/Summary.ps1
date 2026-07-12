function Write-DcoirExecutionPlan {
    param([System.Collections.ArrayList]$Records, [string]$Mode)
    Write-DcoirPhase -Name 'plan' -Message 'Execution plan resolved.'
    Write-DcoirStatus ("Mode={0}; Repo={1}; Ref={2}; DryRun={3}; MaxParallel={4}; MaxDispatchCount={5}; AllowMultipleLiveDispatches={6}; FailFast={7}; CleanupAfterZip={8}" -f $Mode, $script:Ctx.Repo, $script:Ctx.DefaultRef, $script:Ctx.ManifestDryRun, $script:Ctx.MaxParallel, $script:Ctx.MaxDispatchCount, $script:Ctx.AllowMultipleLiveDispatches, $script:Ctx.FailFast, $script:Ctx.CleanupOutputFolderAfterZip)
    Write-DcoirStatus ("Run set id={0}; output_dir={1}" -f $script:Ctx.RunSetId, $script:Ctx.RunOutputDir)
    $i = 0
    foreach ($r in $Records) {
        $i++
        Write-DcoirStatus ("Plan[{0}]: label={1}; workflow={2}; ref={3}; state={4}; inputs={5}" -f $i, $r.label, $r.workflow, $r.ref, $r.state, (Format-DcoirInputMap -Map $r.inputs))
    }
}

function Complete-DcoirRunSet {
    param([System.Collections.ArrayList]$Records)
    Write-DcoirPhase -Name 'summary' -Message 'Writing run-set summary and packaging evidence.'
    foreach ($r in @($Records | Where-Object { $_.run_id })) {
        try { Save-DcoirRunEvidence -Id ([Int64]$r.run_id) -Label ([string]$r.label) -Capture $r.capture | Out-Null }
        catch { $r.error = "Evidence capture failed: $($_.Exception.Message)" }
    }
    $failed = @($Records | Where-Object { Test-DcoirRunRecordNonSuccess $_ })
    $summary = [ordered]@{
        tool='Invoke-DcoirActionsWorkflowOrchestrator.ps1'
        engine_module='Dcoir.Actions'
        facade_module='DcoirActionsOrchestrator.psm1'
        tool_version=$script:DcoirActionsVersion
        run_set_id=$script:Ctx.RunSetId
        repo=$script:Ctx.Repo
        default_ref=$script:Ctx.DefaultRef
        mode=$script:Ctx.Mode
        dry_run=$script:Ctx.ManifestDryRun
        max_parallel=$script:Ctx.MaxParallel
        fail_fast=$script:Ctx.FailFast
        cleanup_output_folder_after_zip=$script:Ctx.CleanupOutputFolderAfterZip
        dispatches_started=$script:Ctx.DispatchesStarted
        dispatches_succeeded=$script:Ctx.DispatchesSucceeded
        dispatches_blocked=$script:Ctx.DispatchesBlocked
        failed_or_non_success_count=$failed.Count
        output_dir=$script:Ctx.RunOutputDir
        zip_path=$script:Ctx.ZipPath
        records=@($Records)
    }
    Save-DcoirJson -Path (Join-Path $script:Ctx.RunOutputDir 'orchestrator_summary.json') -Object $summary
    Write-DcoirUtf8Text -Path (Join-Path $script:Ctx.RunOutputDir 'orchestrator_summary.md') -Text ("# DCOIR Actions Orchestrator Summary`n`nRun set: $($script:Ctx.RunSetId)`nFailed/non-success: $($failed.Count)`n")
    $zipCreated = $false
    if ($script:Ctx.CreateZip) {
        Write-DcoirPhase -Name 'zip' -Message ("Creating ChatGPT-friendly ZIP: {0}" -f $script:Ctx.ZipPath)
        Invoke-DcoirChatGPTFriendlyZip -SourceFolder $script:Ctx.RunOutputDir -OutputZip $script:Ctx.ZipPath -RepoRoot $script:Ctx.RepoRoot -NormalizeTextEncoding | Out-Null
        $zipCreated = $true
        Write-DcoirStatus "Created ChatGPT-friendly ZIP: $($script:Ctx.ZipPath)"
    }
    if ($zipCreated -and $script:Ctx.CleanupOutputFolderAfterZip) {
        Write-DcoirPhase -Name 'cleanup' -Message ("Deleting expanded run output folder after successful ZIP: {0}" -f $script:Ctx.RunOutputDir)
        Remove-Item -LiteralPath $script:Ctx.RunOutputDir -Recurse -Force
    }
    if ($zipCreated) { Write-Host "UPLOAD_FILE=$($script:Ctx.ZipPath)" } else { Write-Host "UPLOAD_FOLDER=$($script:Ctx.RunOutputDir)" }
    return $failed.Count
}
