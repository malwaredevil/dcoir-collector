function Assert-DcoirLiveDispatchAllowed {
    param([System.Collections.ArrayList]$Records)
    if ($script:Ctx.ManifestDryRun) { return }
    $plannedCount = @($Records | Where-Object { $_.state -eq 'planned' }).Count
    if ($plannedCount -gt $script:Ctx.MaxDispatchCount) { $script:Ctx.DispatchesBlocked++; throw ("Live dispatch blocked: manifest has {0} planned runs, max_dispatch_count={1}." -f $plannedCount, $script:Ctx.MaxDispatchCount) }
    if ($plannedCount -gt 1 -and -not $script:Ctx.AllowMultipleLiveDispatches) { $script:Ctx.DispatchesBlocked++; throw ("Live dispatch blocked: manifest has {0} runs. Set allow_multiple_live_dispatches=true only after reviewing the plan." -f $plannedCount) }
}

function Start-DcoirWorkflowRun {
    param($Record)
    if (-not $script:Ctx.ManifestDryRun -and $script:Ctx.DispatchesStarted -ge $script:Ctx.MaxDispatchCount) { $script:Ctx.DispatchesBlocked++; throw ("Dispatch guard blocked additional workflow launch. dispatches_started={0}, max_dispatch_count={1}" -f $script:Ctx.DispatchesStarted, $script:Ctx.MaxDispatchCount) }
    $workflowFile = [string]$Record.workflow
    $refName = [string]$Record.ref
    Write-DcoirPhase -Name 'dispatch' -Message ("Dispatching workflow '{0}' for run label '{1}' on ref '{2}' with inputs: {3}" -f $workflowFile, $Record.label, $refName, (Format-DcoirInputMap -Map $Record.inputs))
    $before = @(Get-DcoirWorkflowRuns -WorkflowFile $workflowFile -Branch $refName -PerPage 50 -Event 'workflow_dispatch')
    $beforeIds = @($before | ForEach-Object { [Int64]$_.id })
    $dispatchStart = (Get-Date).ToUniversalTime().AddMinutes(-2)
    $ghArgs = @('workflow','run',$workflowFile,'-R',$script:Ctx.Repo,'--ref',$refName)
    if ($Record.inputs) { foreach ($key in $Record.inputs.Keys) { $ghArgs += @('-f', ("{0}={1}" -f $key, [string]$Record.inputs[$key])) } }
    $Record.dispatch_started_at = (Get-Date -Format o)
    Invoke-DcoirGhText -GhArgs $ghArgs -DebugName ('dispatch_' + ($Record.label -replace '[^A-Za-z0-9_.-]', '_')) | Out-Null
    $script:Ctx.DispatchesStarted++
    Save-DcoirJson -Path (Join-Path $script:Ctx.RunOutputDir 'dispatch_ledger.json') -Object @{ dispatches_started = $script:Ctx.DispatchesStarted; max_dispatch_count = $script:Ctx.MaxDispatchCount; records = @($script:Ctx.Records) }
    for ($i = 1; $i -le $script:Ctx.DispatchPollAttempts; $i++) {
        Start-Sleep -Seconds $script:Ctx.DispatchPollSeconds
        $after = @(Get-DcoirWorkflowRuns -WorkflowFile $workflowFile -Branch $refName -PerPage 50 -Event 'workflow_dispatch')
        $candidates = @($after | Where-Object { ($beforeIds -notcontains [Int64]$_.id) -and ([DateTime]$_.created_at).ToUniversalTime() -ge $dispatchStart } | Sort-Object { [DateTime]$_.created_at } -Descending)
        if ($candidates.Count -gt 0) {
            $run = $candidates[0]
            $Record.run_id = [Int64]$run.id; $Record.url = [string]$run.html_url; $Record.status = [string]$run.status; $Record.conclusion = [string]$run.conclusion; $Record.created_at = [string]$run.created_at; $Record.updated_at = [string]$run.updated_at; $Record.state = 'active'
            $script:Ctx.DispatchesSucceeded++
            Save-DcoirJson -Path (Join-Path $script:Ctx.RunOutputDir 'dispatch_ledger.json') -Object @{ dispatches_started = $script:Ctx.DispatchesStarted; dispatches_succeeded = $script:Ctx.DispatchesSucceeded; max_dispatch_count = $script:Ctx.MaxDispatchCount; records = @($script:Ctx.Records) }
            Write-DcoirStatus ("Dispatched workflow run: label={0} workflow={1} run_id={2} status={3} url={4}" -f $Record.label, $workflowFile, $Record.run_id, $Record.status, $Record.url)
            return
        }
        Write-DcoirStatus ("Waiting for dispatched run to appear for {0} ({1}/{2}); no retry dispatch will occur during this wait." -f $Record.label, $i, $script:Ctx.DispatchPollAttempts)
    }
    throw "Timed out waiting for dispatched run to appear for $($Record.label). No retry dispatch was attempted."
}
