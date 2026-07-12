Set-StrictMode -Version 2.0

$privateRoot = Join-Path $PSScriptRoot 'Private'
foreach ($privateScript in @('00-Common.ps1', '10-Process.ps1', '20-Report.ps1')) {
    . (Join-Path $privateRoot $privateScript)
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
