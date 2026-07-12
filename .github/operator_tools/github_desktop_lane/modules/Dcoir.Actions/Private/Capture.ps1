function Save-DcoirRunEvidence {
    param([Parameter(Mandatory=$true)][Int64]$Id, [string]$Label, $Capture)
    Write-DcoirPhase -Name 'capture' -Message ("Capturing evidence for workflow run {0} ({1})" -f $Id, $Label)
    $safeLabel = ConvertTo-DcoirSafeName -Text $Label
    $runDir = Join-Path $script:Ctx.EvidenceDir ("run_{0}_{1}" -f $Id, $safeLabel)
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    $run = Get-DcoirRunById -Id $Id
    Save-DcoirJson -Path (Join-Path $runDir 'run.json') -Object $run
    $wantJobs = [bool](Get-DcoirConfigValue -Map $Capture -Name 'jobs' -Default $true)
    $wantLogs = [bool](Get-DcoirConfigValue -Map $Capture -Name 'logs' -Default $true)
    $wantArtifacts = [bool](Get-DcoirConfigValue -Map $Capture -Name 'artifacts' -Default $false)
    if ($wantJobs) { Save-DcoirJson -Path (Join-Path $runDir 'jobs.json') -Object (Get-DcoirRunJobs -Id $Id) }
    if ($wantLogs) {
        try { Write-DcoirUtf8Text -Path (Join-Path $runDir 'run.log.txt') -Text (Invoke-DcoirGhText -GhArgs @('run','view', [string]$Id, '-R', $script:Ctx.Repo, '--log') -DebugName "log_$Id") }
        catch { Write-DcoirUtf8Text -Path (Join-Path $runDir 'run.log.error.txt') -Text $_.Exception.Message }
    }
    if ($wantArtifacts -or $script:Ctx.DownloadArtifacts) {
        $artifactDir = Join-Path $runDir 'artifacts'
        New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
        try { Invoke-DcoirGhText -GhArgs @('run','download', [string]$Id, '-R', $script:Ctx.Repo, '-D', $artifactDir) -DebugName "artifacts_$Id" | Out-Null }
        catch { Write-DcoirUtf8Text -Path (Join-Path $runDir 'artifacts.error.txt') -Text $_.Exception.Message }
    }
    return $run
}

function Add-DcoirWatchRecords {
    param([System.Collections.ArrayList]$Records, [string[]]$Workflows, [Int64[]]$Ids, [int]$LimitCount, [string]$Branch)
    if ($Ids) {
        foreach ($id in $Ids) {
            $run = Get-DcoirRunById -Id $id
            $rec = New-DcoirRunRecord -Label ("run_$id") -WorkflowFile ([string]$run.workflow_id) -RefName $Branch -Inputs @{} -Capture @{ summary=$true; logs=$true; artifacts=$script:Ctx.DownloadArtifacts; jobs=$true }
            $rec.run_id=[Int64]$run.id; $rec.url=[string]$run.html_url; $rec.status=[string]$run.status; $rec.conclusion=[string]$run.conclusion; $rec.created_at=[string]$run.created_at; $rec.updated_at=[string]$run.updated_at
            if ($run.status -eq 'completed') { $rec.state='terminal' } else { $rec.state='active' }
            [void]$Records.Add($rec)
        }
    }
    if ($Workflows) {
        foreach ($wf in $Workflows) {
            foreach ($run in @(Get-DcoirWorkflowRuns -WorkflowFile $wf -Branch $Branch -PerPage $LimitCount)) {
                $rec = New-DcoirRunRecord -Label ("{0}_{1}" -f ($wf -replace '[^A-Za-z0-9_.-]', '_'), $run.id) -WorkflowFile $wf -RefName $Branch -Inputs @{} -Capture @{ summary=$true; logs=$true; artifacts=$script:Ctx.DownloadArtifacts; jobs=$true }
                $rec.run_id=[Int64]$run.id; $rec.url=[string]$run.html_url; $rec.status=[string]$run.status; $rec.conclusion=[string]$run.conclusion; $rec.created_at=[string]$run.created_at; $rec.updated_at=[string]$run.updated_at
                if ($run.status -eq 'completed') { $rec.state='terminal' } else { $rec.state='active' }
                [void]$Records.Add($rec)
            }
        }
    }
}
