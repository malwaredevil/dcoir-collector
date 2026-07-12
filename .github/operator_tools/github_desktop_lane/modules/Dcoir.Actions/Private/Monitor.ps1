function Update-DcoirRunRecordStatus {
    param($Record)
    if (-not $Record.run_id) { return }
    $run = Get-DcoirRunById -Id ([Int64]$Record.run_id)
    $Record.status = [string]$run.status; $Record.conclusion = [string]$run.conclusion; $Record.url = [string]$run.html_url; $Record.updated_at = [string]$run.updated_at
    if ($run.status -eq 'completed') { $Record.state = 'terminal' } else { $Record.state = 'active' }
}

function Stop-DcoirPlannedRunsForFailFast {
    param([System.Collections.ArrayList]$Records, [string]$Reason)
    foreach ($r in @($Records | Where-Object { $_.state -eq 'planned' })) { $r.state = 'skipped'; $r.skipped_reason = $Reason }
}

function Wait-DcoirRunSet {
    param([System.Collections.ArrayList]$Records, [switch]$DispatchPlanned)
    Write-DcoirPhase -Name 'monitor' -Message ("Monitoring workflow run set with {0} record(s)." -f $Records.Count)
    $deadline = (Get-Date).AddMinutes($script:Ctx.TimeoutMinutes)
    while ($true) {
        if ((Get-Date) -gt $deadline) { foreach ($r in $Records) { if ($r.state -ne 'terminal' -and $r.state -ne 'skipped') { $r.state = 'timed_out'; $r.error = 'Timeout waiting for workflow run completion.' } }; return }
        foreach ($r in @($Records | Where-Object { $_.state -eq 'active' })) {
            Write-DcoirStatus ("Monitoring workflow run {0} ({1}) status={2} conclusion={3}" -f $r.run_id, $r.label, $r.status, $r.conclusion)
            try { Update-DcoirRunRecordStatus -Record $r } catch { $r.error = $_.Exception.Message; Write-DcoirStatus "Status update failed for $($r.label): $($r.error)" }
        }
        if ($script:Ctx.FailFast -and @($Records | Where-Object { Test-DcoirRunRecordNonSuccess $_ }).Count -gt 0) { Stop-DcoirPlannedRunsForFailFast -Records $Records -Reason 'fail_fast_previous_gate_non_success' }
        if ($DispatchPlanned -and (-not ($script:Ctx.FailFast -and @($Records | Where-Object { Test-DcoirRunRecordNonSuccess $_ }).Count -gt 0))) {
            $activeCount = @($Records | Where-Object { $_.state -eq 'active' }).Count
            $slots = [Math]::Max(0, $script:Ctx.MaxParallel - $activeCount)
            if ($slots -gt 0) {
                $planned = @($Records | Where-Object { $_.state -eq 'planned' } | Select-Object -First $slots)
                foreach ($r in $planned) {
                    try { Start-DcoirWorkflowRun -Record $r }
                    catch { $r.error = $_.Exception.Message; if ($r.run_id) { $r.state = 'active'; Write-DcoirStatus "Dispatch tracking issue for $($r.label) after run_id=$($r.run_id): $($r.error)" } else { $r.state = 'terminal'; Write-DcoirStatus "Dispatch failed for $($r.label): $($r.error)" } }
                }
            }
        }
        Save-DcoirJson -Path (Join-Path $script:Ctx.RunOutputDir 'run_set_state.json') -Object @($Records)
        $notDone = @($Records | Where-Object { $_.state -eq 'planned' -or $_.state -eq 'active' })
        $statusLine = @($Records | ForEach-Object { "{0}:{1}/{2}/{3}" -f $_.label, $_.state, $_.status, $_.conclusion }) -join '; '
        Write-DcoirStatus "Run set status: $statusLine"
        if ($notDone.Count -eq 0) { return }
        Start-Sleep -Seconds $script:Ctx.PollSeconds
    }
}
