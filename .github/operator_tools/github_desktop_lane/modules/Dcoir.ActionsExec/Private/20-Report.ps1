function Write-DcoirActionsExecReport {
    param(
        [Parameter(Mandatory=$true)][string]$ReportPath,
        [Parameter(Mandatory=$true)][string]$RequestId,
        [Parameter(Mandatory=$true)][string]$Result,
        [Parameter(Mandatory=$true)][string]$Shell,
        [Parameter(Mandatory=$true)][int]$ExitCode,
        [Parameter(Mandatory=$true)][bool]$TimedOut,
        [Parameter(Mandatory=$true)][string]$CommandSha256,
        [Parameter(Mandatory=$true)][string]$ApprovedPreview,
        [Parameter(Mandatory=$true)][string]$CommandSanitized,
        [string]$StdoutPreview = '',
        [string]$StderrPreview = '',
        [string]$ErrorText = '',
        [int]$ArtifactRetentionDays = 3,
        [string]$StartedUtc = '',
        [string]$FinishedUtc = ''
    )
    $reportDir = Split-Path -Parent $ReportPath
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    if ($StdoutPreview.Length -gt 4000) { $StdoutPreview = $StdoutPreview.Substring(0,4000) + "`n[truncated in workflow report; see artifact]" }
    if ($StderrPreview.Length -gt 4000) { $StderrPreview = $StderrPreview.Substring(0,4000) + "`n[truncated in workflow report; see artifact]" }

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# ChatGPT workflow report')
    $lines.Add('')
    $lines.Add('## Result')
    $lines.Add('')
    $lines.Add('- workflow: chatgpt-exec')
    $lines.Add("- result: $Result")
    $lines.Add('- phase: approved-command-execution')
    $lines.Add("- request_id: $RequestId")
    $lines.Add("- shell: $Shell")
    $lines.Add("- exit_code: $ExitCode")
    $lines.Add("- timed_out: $TimedOut")
    $lines.Add("- command_sha256: $CommandSha256")
    $lines.Add("- artifact_name: chatgpt-exec-$RequestId")
    $lines.Add("- artifact_retention_days: $ArtifactRetentionDays")
    if ($StartedUtc) { $lines.Add("- started_utc: $StartedUtc") }
    if ($FinishedUtc) { $lines.Add("- finished_utc: $FinishedUtc") }
    $lines.Add("- report_created_utc: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))")
    if ($ErrorText) {
        $lines.Add('')
        $lines.Add('## Harness error')
        $lines.Add('')
        $lines.Add('```text')
        $lines.Add($ErrorText)
        $lines.Add('```')
    }
    $lines.Add('')
    $lines.Add('## Approved command preview')
    $lines.Add('')
    $lines.Add('```text')
    $lines.Add($ApprovedPreview)
    $lines.Add('```')
    $lines.Add('')
    $lines.Add('## Executed command')
    $lines.Add('')
    $lines.Add('```powershell')
    $lines.Add($CommandSanitized)
    $lines.Add('```')
    $lines.Add('')
    $lines.Add('## Standard output preview')
    $lines.Add('')
    $lines.Add('```text')
    $lines.Add($StdoutPreview)
    $lines.Add('```')
    $lines.Add('')
    $lines.Add('## Standard error preview')
    $lines.Add('')
    $lines.Add('```text')
    $lines.Add($StderrPreview)
    $lines.Add('```')
    $lines.Add('')
    $lines.Add('## Artifact guidance')
    $lines.Add('')
    $lines.Add("Artifact `chatgpt-exec-$RequestId` contains sanitized stdout/stderr, sanitized request, sanitized command, exec_result.json, and any files written under DCOIR_DOWNLOADS_DIR.")
    $lines.Add('')
    $lines.Add('## Cleanup guidance')
    $lines.Add('')
    $lines.Add('The request file is removed automatically when cleanup_request_after_run=true. This status report can be cleaned later with cleanup_status_reports=true after ChatGPT records evidence. GitHub Actions artifacts expire by configured retention.')
    $lines.Add('')
    $lines.Add('## Next ChatGPT action')
    $lines.Add('')
    if ($Result -eq 'success') {
        $lines.Add('Read this report and download the artifact if needed; record evidence and clean the status report when safe.')
    } else {
        $lines.Add('Read this report, inspect the artifact and run log if needed, repair the command or environment, and record the failure and next action in the governed GitHub work item.')
    }
    $lines -join "`n" | Out-File -FilePath $ReportPath -Encoding utf8
}
