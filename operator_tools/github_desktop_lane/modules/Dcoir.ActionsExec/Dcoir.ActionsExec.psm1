Set-StrictMode -Version 2.0

function New-DcoirActionsExecSafeName {
    param([Parameter(Mandatory=$true)][string]$Value)
    if ($Value -notmatch '^[A-Za-z0-9._-]+$') {
        throw "Unsafe identifier: $Value"
    }
    return $Value
}

function Get-DcoirActionsExecSha256Text {
    param([Parameter(Mandatory=$true)][string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        $hash = $sha.ComputeHash($bytes)
        return ([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Add-DcoirActionsExecMask {
    param([AllowNull()][string]$Value)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        Write-Host "::add-mask::$Value"
    }
}

function ConvertTo-DcoirActionsExecSanitizedText {
    param(
        [AllowNull()][string]$Text,
        [hashtable]$SecretValuesByName
    )
    if ($null -eq $Text) { return '' }
    $out = [string]$Text
    if ($SecretValuesByName) {
        foreach ($key in $SecretValuesByName.Keys) {
            $value = [string]$SecretValuesByName[$key]
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $out = $out.Replace($value, "[REDACTED:$key]")
            }
        }
    }
    return $out
}

function Get-DcoirActionsExecSecretMap {
    param([string[]]$SecretEnvNames)
    $secretValues = @{}
    foreach ($name in $SecretEnvNames) {
        if ([string]::IsNullOrWhiteSpace($name)) { continue }
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Add-DcoirActionsExecMask -Value $value
            $secretValues[$name] = $value
        }
    }
    return $secretValues
}

function Set-DcoirActionsExecEnvironmentBridge {
    param(
        [Parameter(Mandatory=$true)][hashtable]$GeneratedValues,
        [string[]]$SecretEnvNames = @()
    )
    $secretValues = Get-DcoirActionsExecSecretMap -SecretEnvNames $SecretEnvNames

    foreach ($name in $SecretEnvNames) {
        if ([string]::IsNullOrWhiteSpace($name)) { continue }
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            [Environment]::SetEnvironmentVariable($name, $value, 'Machine')
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }

    foreach ($name in $GeneratedValues.Keys) {
        $value = [string]$GeneratedValues[$name]
        if ([string]::IsNullOrWhiteSpace($value)) { continue }
        [Environment]::SetEnvironmentVariable($name, $value, 'Machine')
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }

    return $secretValues
}

function Invoke-DcoirActionsExecProcess {
    param(
        [Parameter(Mandatory=$true)][string]$Shell,
        [Parameter(Mandatory=$true)][string]$CommandText,
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$RunRoot,
        [int]$TimeoutSeconds = 1800
    )

    if ($TimeoutSeconds -lt 1) { $TimeoutSeconds = 1800 }
    $commandPath = Join-Path $RunRoot 'approved_command.ps1'
    $cmdPath = Join-Path $RunRoot 'approved_command.cmd'
    $stdoutPath = Join-Path $RunRoot 'stdout.raw.txt'
    $stderrPath = Join-Path $RunRoot 'stderr.raw.txt'

    $started = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $timedOut = $false

    switch ($Shell) {
        'powershell_5' {
            $CommandText | Out-File -FilePath $commandPath -Encoding utf8
            $exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
            $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $commandPath)
        }
        'pwsh' {
            $CommandText | Out-File -FilePath $commandPath -Encoding utf8
            $exe = 'pwsh'
            $args = @('-NoProfile', '-File', $commandPath)
        }
        'cmd' {
            $CommandText | Out-File -FilePath $cmdPath -Encoding ascii
            $exe = Join-Path $env:SystemRoot 'System32\cmd.exe'
            $args = @('/d', '/s', '/c', $cmdPath)
        }
        default {
            throw "Unsupported shell '$Shell'. Supported values: powershell_5, pwsh, cmd."
        }
    }

    $p = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -NoNewWindow -PassThru
    if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
        $timedOut = $true
        try { $p.Kill() } catch { }
        $exitCode = 124
    }
    else {
        $exitCode = [int]$p.ExitCode
    }

    $finished = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    return [pscustomobject]@{
        exit_code = $exitCode
        timed_out = $timedOut
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        command_path = $(if ($Shell -eq 'cmd') { $cmdPath } else { $commandPath })
        started_utc = $started
        finished_utc = $finished
    }
}

function Copy-DcoirActionsExecDownloads {
    param(
        [Parameter(Mandatory=$true)][string]$DownloadsDir,
        [Parameter(Mandatory=$true)][string]$ArtifactDir
    )
    if (-not (Test-Path -LiteralPath $DownloadsDir -PathType Container)) { return }
    $items = Get-ChildItem -LiteralPath $DownloadsDir -Force -ErrorAction SilentlyContinue
    if (-not $items) { return }
    $dest = Join-Path $ArtifactDir 'downloads'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
    }
}

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

function Invoke-DcoirActionsExecRequest {
    param(
        [Parameter(Mandatory=$true)][string]$RequestPath,
        [Parameter(Mandatory=$true)][string]$RepoRoot,
        [Parameter(Mandatory=$true)][string]$OutputRoot,
        [string[]]$SecretEnvNames = @('DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID')
    )

    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($request.schema -ne 'dcoir.chatgpt_staging.exec_request.v1') { throw 'exec request schema must be dcoir.chatgpt_staging.exec_request.v1' }
    $requestId = New-DcoirActionsExecSafeName -Value ([string]$request.request_id)
    if ($request.operator_approved -ne $true) { throw 'exec request requires operator_approved=true' }
    $commandText = [string]$request.command
    if ([string]::IsNullOrWhiteSpace($commandText)) { throw 'exec request requires non-empty command' }
    $approvedPreview = [string]$request.approved_command_preview
    if ([string]::IsNullOrWhiteSpace($approvedPreview)) { throw 'exec request requires approved_command_preview' }
    $shell = 'powershell_5'
    if (($request.PSObject.Properties.Name -contains 'shell') -and -not [string]::IsNullOrWhiteSpace([string]$request.shell)) {
        $shell = [string]$request.shell
    }
    $timeoutSeconds = 1800
    if ($request.PSObject.Properties.Name -contains 'timeout_seconds') { $timeoutSeconds = [int]$request.timeout_seconds }
    $retentionDays = 3
    if ($request.PSObject.Properties.Name -contains 'artifact_retention_days') { $retentionDays = [int]$request.artifact_retention_days }
    if ($retentionDays -lt 1) { $retentionDays = 1 }
    if ($retentionDays -gt 30) { $retentionDays = 30 }
    $cleanupRequestAfterRun = $true
    if ($request.PSObject.Properties.Name -contains 'cleanup_request_after_run') { $cleanupRequestAfterRun = [bool]$request.cleanup_request_after_run }

    $runRoot = Join-Path $OutputRoot $requestId
    $downloads = Join-Path $runRoot 'downloads'
    $config = Join-Path $runRoot 'config'
    $artifactDir = Join-Path $runRoot 'artifact'
    $reportDir = Join-Path $RepoRoot (Join-Path 'chatgpt_staging/status_reports/chatgpt-exec' $requestId)
    $reportPath = Join-Path $reportDir 'workflow_report.md'
    New-Item -ItemType Directory -Force -Path $runRoot, $downloads, $config, $artifactDir, $reportDir | Out-Null

    $generated = @{ DCOIR_REPO_ROOT = $RepoRoot; DCOIR_DOWNLOADS_DIR = $downloads; DCOIR_CONFIG_DIR = $config }
    $secretValues = Set-DcoirActionsExecEnvironmentBridge -GeneratedValues $generated -SecretEnvNames $SecretEnvNames
    $commandSha = Get-DcoirActionsExecSha256Text -Text $commandText

    $process = Invoke-DcoirActionsExecProcess -Shell $shell -CommandText $commandText -WorkingDirectory $RepoRoot -RunRoot $runRoot -TimeoutSeconds $timeoutSeconds
    $stdout = ''
    $stderr = ''
    if (Test-Path -LiteralPath $process.stdout_path) { $stdout = Get-Content -LiteralPath $process.stdout_path -Raw -Encoding UTF8 -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $process.stderr_path) { $stderr = Get-Content -LiteralPath $process.stderr_path -Raw -Encoding UTF8 -ErrorAction SilentlyContinue }

    $stdoutSan = ConvertTo-DcoirActionsExecSanitizedText -Text $stdout -SecretValuesByName $secretValues
    $stderrSan = ConvertTo-DcoirActionsExecSanitizedText -Text $stderr -SecretValuesByName $secretValues
    $commandSan = ConvertTo-DcoirActionsExecSanitizedText -Text $commandText -SecretValuesByName $secretValues
    $requestRaw = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8
    $requestSan = ConvertTo-DcoirActionsExecSanitizedText -Text $requestRaw -SecretValuesByName $secretValues

    $stdoutSan | Out-File -FilePath (Join-Path $artifactDir 'stdout.sanitized.txt') -Encoding utf8
    $stderrSan | Out-File -FilePath (Join-Path $artifactDir 'stderr.sanitized.txt') -Encoding utf8
    $commandSan | Out-File -FilePath (Join-Path $artifactDir 'approved_command.sanitized.ps1') -Encoding utf8
    $requestSan | Out-File -FilePath (Join-Path $artifactDir 'request.sanitized.json') -Encoding utf8
    Copy-DcoirActionsExecDownloads -DownloadsDir $downloads -ArtifactDir $artifactDir

    $result = if ($process.exit_code -eq 0 -and -not $process.timed_out) { 'success' } else { 'failure' }
    $resultObj = [ordered]@{
        schema = 'dcoir.chatgpt_staging.exec_result.v1'
        request_id = $requestId
        result = $result
        exit_code = $process.exit_code
        timed_out = $process.timed_out
        shell = $shell
        command_sha256 = $commandSha
        started_utc = $process.started_utc
        finished_utc = $process.finished_utc
        artifact_dir = $artifactDir
        artifact_name = "chatgpt-exec-$requestId"
        artifact_retention_days = $retentionDays
        cleanup_request_after_run = $cleanupRequestAfterRun
        report_path = $reportPath
    }
    ($resultObj | ConvertTo-Json -Depth 8) | Out-File -FilePath (Join-Path $artifactDir 'exec_result.json') -Encoding utf8

    Write-DcoirActionsExecReport -ReportPath $reportPath -RequestId $requestId -Result $result -Shell $shell -ExitCode $process.exit_code -TimedOut $process.timed_out -CommandSha256 $commandSha -ApprovedPreview $approvedPreview -CommandSanitized $commandSan -StdoutPreview $stdoutSan -StderrPreview $stderrSan -ArtifactRetentionDays $retentionDays -StartedUtc $process.started_utc -FinishedUtc $process.finished_utc
    return [pscustomobject]$resultObj
}

Export-ModuleMember -Function Invoke-DcoirActionsExecRequest, Write-DcoirActionsExecReport, Get-DcoirActionsExecSecretMap, ConvertTo-DcoirActionsExecSanitizedText, New-DcoirActionsExecSafeName
